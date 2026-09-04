"""
Unit and Integration Tests for Verification & Outcome Attribution — Milestone 15
Tests VerificationService, OutcomeAttributionService, Razorpay API verification (VERIFIED),
segment conversion rates (SIMULATED), feedback loop strategy performance updates,
state machine terminal transitions, and REST API verification route.
"""

import pytest
import uuid
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.session import Base, get_db
from backend.models.customer import Customer
from backend.models.transaction import Transaction
from backend.models.segment import Segment
from backend.models.recovery_case import RecoveryCase
from backend.models.recovery_decision import RecoveryDecision
from backend.models.recovery_action import RecoveryAction
from backend.models.recovery_strategy import RecoveryStrategy
from backend.models.strategy_outcome import StrategyOutcome
from backend.models.audit_event import AuditEvent
from backend.models.enums import (
    TransactionStatus,
    FailureCategory,
    RecoveryCaseStatus,
    StrategyType,
    ActionExecutionMode,
    OutcomeSource,
    ConfidenceLevel,
)
from backend.services.verification import VerificationService, VerificationResult
from backend.services.outcome_attribution import OutcomeAttributionService
from backend.integrations.razorpay.schemas import RazorpayPaymentLinkResponse

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

def create_sample_action_for_verification(
    db_session,
    execution_mode: str = ActionExecutionMode.REAL_TEST_MODE.value,
    strategy_type: str = StrategyType.PAYMENT_LINK.value,
    failure_category: str = FailureCategory.AUTHENTICATION_FAILURE.value,
    razorpay_payment_link_id: Optional[str] = None,
):
    """Helper to create Customer, Transaction, Segment, RecoveryCase, and RecoveryAction for verification testing."""
    plink_id = razorpay_payment_link_id or f"plink_test_{uuid.uuid4().hex[:10]}"
    seg = Segment(
        name=f"seg_{uuid.uuid4().hex[:6]}",
        failure_category=failure_category,
        payment_method="card",
        amount_range="MID",
        customer_type="NEW",
    )
    db_session.add(seg)
    db_session.flush()

    cust = Customer(name="Verify User", email=f"verify_{uuid.uuid4().hex[:6]}@example.com")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(
        razorpay_payment_id=f"pay_{uuid.uuid4().hex[:10]}",
        customer_id=cust.id,
        amount_paise=200000,
        currency="INR",
        status=TransactionStatus.FAILED.value,
        failure_category=failure_category,
        payment_method="card",
    )
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(
        transaction_id=txn.id,
        customer_id=cust.id,
        segment_id=seg.id,
        status=RecoveryCaseStatus.AWAITING_VERIFICATION.value,
        attempt_count=1,
    )
    db_session.add(case)
    db_session.flush()

    action = RecoveryAction(
        recovery_case_id=case.id,
        action_type=strategy_type,
        execution_mode=execution_mode,
        razorpay_payment_link_id=plink_id,
        payment_link_url=f"https://rzp.io/i/{plink_id}",
        status="SENT",
    )
    db_session.add(action)
    db_session.flush()

    return case, action, seg


def test_real_action_verification_paid(db_session):
    """Test verification of REAL_TEST_MODE action when Razorpay returns status='paid' (VERIFIED outcome)."""
    case, action, seg = create_sample_action_for_verification(
        db_session, execution_mode=ActionExecutionMode.REAL_TEST_MODE.value, razorpay_payment_link_id="plink_paid_123"
    )

    mock_service = MagicMock()
    mock_service.fetch_payment_link.return_value = RazorpayPaymentLinkResponse(
        id="plink_paid_123",
        amount=200000,
        currency="INR",
        status="paid",
        short_url="https://rzp.io/i/paid_123",
        created_at=int(datetime.now(timezone.utc).timestamp()),
    )

    verification_service = VerificationService(payment_link_service=mock_service)
    v_res = verification_service.verify_action_outcome(db_session, case, action)

    assert v_res.outcome == "RECOVERED"
    assert v_res.outcome_source == OutcomeSource.VERIFIED.value
    assert v_res.amount_recovered_paise == 200000

    attr_res = OutcomeAttributionService.attribute_verification_result(db_session, case, action, v_res)

    assert attr_res["attributed"] is True
    assert attr_res["status"] == RecoveryCaseStatus.RECOVERED.value
    assert attr_res["outcome_source"] == OutcomeSource.VERIFIED.value
    assert case.status == RecoveryCaseStatus.RECOVERED.value
    assert case.is_terminal is True

    # Verify StrategyOutcome database record
    outcome = db_session.query(StrategyOutcome).filter_by(recovery_case_id=case.id).first()
    assert outcome is not None
    assert outcome.outcome == "RECOVERED"
    assert outcome.outcome_source == OutcomeSource.VERIFIED.value
    assert outcome.amount_recovered_paise == 200000

    # Verify RecoveryStrategy metrics updated
    strat = db_session.query(RecoveryStrategy).filter_by(segment_id=seg.id, strategy_type=action.action_type).first()
    assert strat is not None
    assert strat.attempt_count == 1
    assert strat.success_count == 1
    assert strat.recovery_rate == 1.0
    assert strat.total_recovered_paise == 200000

def test_real_action_verification_expired(db_session):
    """Test verification of REAL_TEST_MODE action when Razorpay returns status='expired' (VERIFIED outcome)."""
    case, action, seg = create_sample_action_for_verification(
        db_session, execution_mode=ActionExecutionMode.REAL_TEST_MODE.value, razorpay_payment_link_id="plink_exp_123"
    )

    mock_service = MagicMock()
    mock_service.fetch_payment_link.return_value = RazorpayPaymentLinkResponse(
        id="plink_exp_123",
        amount=200000,
        currency="INR",
        status="expired",
        short_url="https://rzp.io/i/exp_123",
        created_at=int(datetime.now(timezone.utc).timestamp()),
    )

    verification_service = VerificationService(payment_link_service=mock_service)
    v_res = verification_service.verify_action_outcome(db_session, case, action)

    assert v_res.outcome == "NOT_RECOVERED"
    assert v_res.outcome_source == OutcomeSource.VERIFIED.value
    assert v_res.amount_recovered_paise == 0

    attr_res = OutcomeAttributionService.attribute_verification_result(db_session, case, action, v_res)

    assert attr_res["status"] == RecoveryCaseStatus.UNRECOVERED.value
    assert case.status == RecoveryCaseStatus.UNRECOVERED.value
    assert case.is_terminal is True

def test_simulated_action_verification(db_session):
    """Test verification of SIMULATED action applies conversion rates and sets outcome_source='SIMULATED'."""
    case, action, seg = create_sample_action_for_verification(
        db_session,
        execution_mode=ActionExecutionMode.SIMULATED.value,
        failure_category=FailureCategory.BANK_TIMEOUT.value,
    )

    verification_service = VerificationService()
    v_res = verification_service.verify_action_outcome(db_session, case, action)

    assert v_res.outcome in ("RECOVERED", "NOT_RECOVERED")
    assert v_res.outcome_source == OutcomeSource.SIMULATED.value

    attr_res = OutcomeAttributionService.attribute_verification_result(db_session, case, action, v_res)

    assert attr_res["attributed"] is True
    assert case.status in (RecoveryCaseStatus.RECOVERED.value, RecoveryCaseStatus.UNRECOVERED.value)

    outcome = db_session.query(StrategyOutcome).filter_by(recovery_case_id=case.id).first()
    assert outcome is not None
    assert outcome.outcome_source == OutcomeSource.SIMULATED.value

def test_evidence_provenance_separation(db_session):
    """Verify that VERIFIED and SIMULATED outcome sources remain explicitly distinct."""
    case_real, act_real, seg_real = create_sample_action_for_verification(db_session, execution_mode=ActionExecutionMode.REAL_TEST_MODE.value)
    case_sim, act_sim, seg_sim = create_sample_action_for_verification(db_session, execution_mode=ActionExecutionMode.SIMULATED.value)

    mock_service = MagicMock()
    mock_service.fetch_payment_link.return_value = RazorpayPaymentLinkResponse(
        id=act_real.razorpay_payment_link_id,
        amount=200000,
        currency="INR",
        status="paid",
        short_url="https://rzp.io/i/test_prov",
        created_at=int(datetime.now(timezone.utc).timestamp()),
    )

    v_service = VerificationService(payment_link_service=mock_service)
    v_real = v_service.verify_action_outcome(db_session, case_real, act_real)
    v_sim = v_service.verify_action_outcome(db_session, case_sim, act_sim)

    OutcomeAttributionService.attribute_verification_result(db_session, case_real, act_real, v_real)
    OutcomeAttributionService.attribute_verification_result(db_session, case_sim, act_sim, v_sim)

    out_real = db_session.query(StrategyOutcome).filter_by(recovery_case_id=case_real.id).first()
    out_sim = db_session.query(StrategyOutcome).filter_by(recovery_case_id=case_sim.id).first()

    assert out_real.outcome_source == OutcomeSource.VERIFIED.value
    assert out_sim.outcome_source == OutcomeSource.SIMULATED.value

def test_feedback_loop_updates_strategy_performance(db_session):
    """Verify that recurring outcome attributions update RecoveryStrategy metrics and sample size sufficiency."""
    case, action, seg = create_sample_action_for_verification(db_session)

    # Attribute 10 successful outcomes for this segment + strategy
    for i in range(10):
        c, a, s = create_sample_action_for_verification(db_session)
        c.segment_id = seg.id
        v_res = VerificationResult(
            case_id=c.id,
            action_id=a.id,
            outcome="RECOVERED",
            amount_recovered_paise=100000,
            outcome_source=OutcomeSource.VERIFIED.value,
            details={},
        )
        OutcomeAttributionService.attribute_verification_result(db_session, c, a, v_res)

    strat = db_session.query(RecoveryStrategy).filter_by(segment_id=seg.id, strategy_type=action.action_type).first()
    assert strat is not None
    assert strat.attempt_count == 10
    assert strat.success_count == 10
    assert strat.recovery_rate == 1.0
    assert strat.sample_size_sufficient is True
    assert strat.confidence_level == ConfidenceLevel.LOW.value
    assert strat.wilson_lower_bound > 0.60

def test_api_verify_endpoint(db_session):
    """Test POST /api/recovery/{case_id}/verify endpoint."""
    case, action, seg = create_sample_action_for_verification(
        db_session, execution_mode=ActionExecutionMode.SIMULATED.value
    )
    db_session.commit()

    res = client.post(f"/api/recovery/{case.id}/verify")
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["case_id"] == case.id
    assert data["attributed"] is True
    assert data["status"] in (RecoveryCaseStatus.RECOVERED.value, RecoveryCaseStatus.UNRECOVERED.value)
    assert data["outcome_source"] == OutcomeSource.SIMULATED.value
    assert data["outcome_id"] is not None

def test_api_verify_endpoint_nonexistent_case():
    """Test POST /api/recovery/nonexistent_id/verify returns 404."""
    res = client.post("/api/recovery/nonexistent_case_99999/verify")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]
