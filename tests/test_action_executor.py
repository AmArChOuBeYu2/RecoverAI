"""
Unit and Integration Tests for ActionExecutor — Milestone 14
Tests ActionExecutor routing, REAL vs SIMULATED mode caps (MAX_REAL_PAYMENT_LINKS),
Razorpay Payment Links integration, state machine transitions, authorization safety guards,
and REST API execution endpoint.
"""

import pytest
import uuid
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from backend.config import settings
from backend.models.customer import Customer
from backend.models.transaction import Transaction
from backend.models.recovery_case import RecoveryCase
from backend.models.recovery_decision import RecoveryDecision
from backend.models.recovery_action import RecoveryAction
from backend.models.audit_event import AuditEvent
from backend.models.enums import (
    TransactionStatus,
    FailureCategory,
    RecoveryCaseStatus,
    StrategyType,
    ActionExecutionMode,
    PolicyDecisionType,
)
from backend.services.executor import ActionExecutor, ActionExecutionError
from backend.services.authorization import ActionAuthorizationError
from backend.integrations.razorpay.schemas import RazorpayPaymentLinkResponse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from backend.database.session import Base, get_db

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=test_engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

client = TestClient(app)

@pytest.fixture
def db_session():
    """Clean in-memory DB session connected to FastAPI app dependency."""
    session = TestingSessionLocal()
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()

@pytest.fixture(autouse=True)
def bypass_contact_hours_restriction():
    """Ensure contact hours restriction (9 AM - 9 PM IST) does not block automated tests running at night."""
    from backend.services.policy_config import PolicyConfig
    open_config = PolicyConfig(contact_start_hour=0, contact_end_hour=24)
    with patch("backend.services.policy_config.PolicyConfig.from_settings", return_value=open_config):
        yield




def create_sample_case_with_decision(
    db_session,
    strategy_type: str = StrategyType.PAYMENT_LINK.value,
    status: str = RecoveryCaseStatus.POLICY_APPROVED.value,
    policy_decision: str = PolicyDecisionType.APPROVE.value,
    amount_paise: int = 150000,
):
    """Helper to create a Customer, Transaction, RecoveryCase, and RecoveryDecision in DB."""
    cust = Customer(
        name="Test Customer",
        email=f"user_{uuid.uuid4().hex[:6]}@example.com",
        phone="+919876543210",
    )
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(
        razorpay_payment_id=f"pay_{uuid.uuid4().hex[:12]}",
        customer_id=cust.id,
        amount_paise=amount_paise,
        currency="INR",
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.AUTHENTICATION_FAILURE.value,
        payment_method="card",
    )
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(
        transaction_id=txn.id,
        customer_id=cust.id,
        status=status,
        attempt_count=0,
    )
    db_session.add(case)
    db_session.flush()

    decision = RecoveryDecision(
        recovery_case_id=case.id,
        selected_strategy=strategy_type,
        ai_recommended_strategy=strategy_type,
        ai_confidence=0.85,
        ai_diagnosis="Authentication failure detected during 3DS",
        reasoning_summary="Payment link recommended for customer self-serve authentication retry.",
        llm_provider="openai:gpt-4o",
        competing_strategies=[{"strategy": strategy_type, "score": 0.85}],
        strategy_evidence={"sample_tier": "MEDIUM", "wilson_lower_bound": 0.45},
    )
    db_session.add(decision)
    db_session.flush()

    return case, decision

def test_payment_link_real_test_mode_under_cap(db_session):
    """Test PAYMENT_LINK execution in REAL_TEST_MODE when under MAX_REAL_PAYMENT_LINKS cap."""
    case, decision = create_sample_case_with_decision(
        db_session, strategy_type=StrategyType.PAYMENT_LINK.value, amount_paise=250000
    )

    mock_plink_service = MagicMock()
    mock_plink_service.create_payment_link.return_value = RazorpayPaymentLinkResponse(
        id="plink_test_12345",
        amount=250000,
        currency="INR",
        status="created",
        short_url="https://rzp.io/i/test_12345",
        reference_id=case.id,
        description=f"RecoverAI Payment Link for Case {case.id[:8]}",
        created_at=int(datetime.now(timezone.utc).timestamp()),
        raw_payload={"id": "plink_test_12345", "status": "created"},
    )


    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_key"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "rzp_test_secret"):

        executor = ActionExecutor(payment_link_service=mock_plink_service)
        action = executor.execute(db_session, case, decision)

        assert action is not None
        assert action.action_type == StrategyType.PAYMENT_LINK.value
        assert action.execution_mode == ActionExecutionMode.REAL_TEST_MODE.value
        assert action.razorpay_payment_link_id == "plink_test_12345"
        assert action.payment_link_url == "https://rzp.io/i/test_12345"
        assert action.status == "SENT"
        assert action.payload["notification_mode"] == "RAZORPAY_TEST"
        assert action.payload["amount_paise"] == 250000

        # Verify state machine transition to AWAITING_VERIFICATION
        assert case.status == RecoveryCaseStatus.AWAITING_VERIFICATION.value
        assert case.attempt_count == 1

        # Verify audit event
        audit = db_session.query(AuditEvent).filter_by(recovery_case_id=case.id, event_type="ACTION_EXECUTED").first()
        assert audit is not None
        assert "plink_test_12345" in audit.description or audit.details.get("razorpay_payment_link_id") == "plink_test_12345"

def test_payment_link_simulated_mode_when_over_cap(db_session):
    """Test PAYMENT_LINK falls back to SIMULATED mode when MAX_REAL_PAYMENT_LINKS limit is reached."""
    with patch.object(settings, "MAX_REAL_PAYMENT_LINKS", 2), \
         patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_key"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "rzp_test_secret"):

        # Insert 2 existing REAL_TEST_MODE payment link actions to reach cap of 2
        for _ in range(2):
            c, d = create_sample_case_with_decision(db_session)
            act = RecoveryAction(
                recovery_case_id=c.id,
                action_type=StrategyType.PAYMENT_LINK.value,
                execution_mode=ActionExecutionMode.REAL_TEST_MODE.value,
                razorpay_payment_link_id=f"plink_existing_{uuid.uuid4().hex[:6]}",
                status="SENT",
            )
            db_session.add(act)
        db_session.flush()

        # Now execute third case
        case3, decision3 = create_sample_case_with_decision(db_session)
        executor = ActionExecutor()
        action = executor.execute(db_session, case3, decision3)

        assert action.execution_mode == ActionExecutionMode.SIMULATED.value
        assert action.razorpay_payment_link_id.startswith("plink_sim_")
        assert "simulated_" in action.payment_link_url
        assert action.payload["notification_mode"] == "SIMULATED"
        assert case3.status == RecoveryCaseStatus.AWAITING_VERIFICATION.value

def test_action_authorization_boundary_rejection(db_session):
    """Test ActionAuthorizationError is raised when case is not in valid non-terminal state or Policy is not APPROVE."""
    case, decision = create_sample_case_with_decision(db_session, status=RecoveryCaseStatus.POLICY_APPROVED.value)

    from backend.services.policy_engine import PolicyEvaluationResult

    mock_denied_result = PolicyEvaluationResult(
        policy_version="v1.0",
        decision=PolicyDecisionType.DENY.value,
        strategy=decision.selected_strategy,
        rules_evaluated=[],
        failed_rules=[],
        blocking_rule="MAX_RETRIES",
        reason="Blocked by MAX_RETRIES safety rule",
        requires_human=False,
        can_execute_action=False,
    )

    with patch("backend.services.policy_engine.PolicyEngine.evaluate", return_value=mock_denied_result):
        executor = ActionExecutor()
        with pytest.raises(ActionAuthorizationError) as exc_info:
            executor.execute(db_session, case, decision)

        assert "Action execution rejected by authorization boundary" in str(exc_info.value)
        assert exc_info.value.decision == PolicyDecisionType.DENY.value


def test_strategy_handlers(db_session):
    """Test execution routing for REMINDER, DELAYED_RETRY, ESCALATION, HUMAN_REVIEW, and NO_ACTION."""
    executor = ActionExecutor()

    # 1. REMINDER
    c_rem, d_rem = create_sample_case_with_decision(db_session, strategy_type=StrategyType.REMINDER.value)
    act_rem = executor.execute(db_session, c_rem, d_rem)
    assert act_rem.action_type == StrategyType.REMINDER.value
    assert act_rem.execution_mode == ActionExecutionMode.SIMULATED.value
    assert act_rem.status == "SENT"
    assert c_rem.status == RecoveryCaseStatus.AWAITING_VERIFICATION.value

    # 2. DELAYED_RETRY
    c_del, d_del = create_sample_case_with_decision(db_session, strategy_type=StrategyType.DELAYED_RETRY.value)
    act_del = executor.execute(db_session, c_del, d_del)
    assert act_del.action_type == StrategyType.DELAYED_RETRY.value
    assert act_del.status == "SCHEDULED"
    assert act_del.expires_at is not None
    assert c_del.status == RecoveryCaseStatus.AWAITING_VERIFICATION.value

    # 3. ESCALATION & HUMAN_REVIEW (Must be rejected by authorization boundary because Policy returns ESCALATE)
    c_esc, d_esc = create_sample_case_with_decision(db_session, strategy_type=StrategyType.ESCALATION.value)
    with pytest.raises(ActionAuthorizationError) as exc_esc:
        executor.execute(db_session, c_esc, d_esc)
    assert exc_esc.value.decision == PolicyDecisionType.ESCALATE.value

    c_hr, d_hr = create_sample_case_with_decision(db_session, strategy_type=StrategyType.HUMAN_REVIEW.value)
    with pytest.raises(ActionAuthorizationError) as exc_hr:
        executor.execute(db_session, c_hr, d_hr)
    assert exc_hr.value.decision == PolicyDecisionType.ESCALATE.value

    # 4. NO_ACTION
    c_na, d_na = create_sample_case_with_decision(db_session, strategy_type=StrategyType.NO_ACTION.value)
    act_na = executor.execute(db_session, c_na, d_na)
    assert act_na.action_type == StrategyType.NO_ACTION.value
    assert act_na.status == "COMPLETED"
    assert c_na.status == RecoveryCaseStatus.AWAITING_VERIFICATION.value


def test_api_execute_endpoint(db_session):
    """Test POST /api/recovery/{case_id}/execute endpoint."""
    case, decision = create_sample_case_with_decision(
        db_session,
        strategy_type=StrategyType.PAYMENT_LINK.value,
        status=RecoveryCaseStatus.STRATEGIES_EVALUATED.value, # Will trigger policy evaluation -> APPROVE -> execute
    )
    db_session.commit()

    res = client.post(f"/api/recovery/{case.id}/execute")
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["case_id"] == case.id
    assert data["case_status"] == RecoveryCaseStatus.AWAITING_VERIFICATION.value
    assert data["action_type"] == StrategyType.PAYMENT_LINK.value
    assert data["execution_mode"] in (ActionExecutionMode.REAL_TEST_MODE.value, ActionExecutionMode.SIMULATED.value)
    assert data["action_id"] is not None

def test_api_execute_endpoint_nonexistent_case():
    """Test POST /api/recovery/nonexistent_id/execute returns 404."""
    res = client.post("/api/recovery/nonexistent_case_12345/execute")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]
