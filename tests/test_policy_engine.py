"""
Comprehensive Deterministic Policy Engine Test Suite for RecoverAI.
Covers 20 required policy evaluation test scenarios, boundary conditions, and safety invariants.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.session import Base
from backend.models import (
    Customer,
    Transaction,
    RecoveryCase,
    RecoveryAction,
    PolicyDecision,
    AuditEvent,
    RecoveryCaseStatus,
    TransactionStatus,
    StrategyType,
    PolicyDecisionType,
    CustomerType,
)
from backend.services.policy_config import PolicyConfig
from backend.services.policy_engine import PolicyEngine, PolicyEvaluationResult
from backend.services.authorization import ActionAuthorizationService, ActionAuthorizationError
from backend.services.state_machine import StateMachineService

@pytest.fixture
def db_session():
    """Fixture creating an isolated in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

def create_mock_case(
    amount_paise: int = 150000, # ₹1,500.00
    status: str = RecoveryCaseStatus.POLICY_APPROVED.value,
    is_terminal: bool = False,
    attempt_count: int = 0,
    contacts_24h: int = 0,
    customer_type: str = CustomerType.NEW.value,
    failed_transactions: int = 0,
    recoverability_score: float = 0.85,
) -> tuple[Customer, Transaction, RecoveryCase]:
    """Helper to build consistent case context graphs for testing."""
    cust = Customer(
        name="Test Customer",
        email="cust@example.com",
        customer_type=customer_type,
        contacts_count_24h=contacts_24h,
        failed_transactions=failed_transactions,
    )
    txn = Transaction(
        amount_paise=amount_paise,
        status=TransactionStatus.FAILED.value,
        customer=cust,
    )
    case = RecoveryCase(
        transaction=txn,
        customer=cust,
        status=status,
        is_terminal=is_terminal,
        attempt_count=attempt_count,
        recoverability_score=recoverability_score,
    )
    return cust, txn, case

# 9 AM IST = 3:30 AM UTC
SAFE_IST_TIME_UTC = datetime(2026, 9, 4, 3, 30, tzinfo=timezone.utc)
# 8 AM IST = 2:30 AM UTC (outside 9 AM - 9 PM IST window)
OUTSIDE_IST_TIME_UTC = datetime(2026, 9, 4, 2, 30, tzinfo=timezone.utc)


# --- 1. Safe Case -> APPROVE ---
def test_1_safe_case_approves(db_session):
    _, _, case = create_mock_case()
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res.decision == PolicyDecisionType.APPROVE.value
    assert res.can_execute_action is True
    assert res.requires_human is False


# --- 2. Retry Limit Exceeded -> DENY ---
def test_2_retry_limit_exceeded_denies(db_session):
    _, _, case = create_mock_case(attempt_count=2) # Default max = 2
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res.decision == PolicyDecisionType.DENY.value
    assert res.blocking_rule == "MAX_RETRIES"
    assert res.can_execute_action is False


# --- 3. Contact Limit Exceeded -> DENY ---
def test_3_contact_limit_exceeded_denies(db_session):
    _, _, case = create_mock_case(contacts_24h=3) # Default max = 3
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res.decision == PolicyDecisionType.DENY.value
    assert res.blocking_rule == "MAX_CONTACTS_24H"


# --- 4. Cooldown Active -> DENY ---
def test_4_cooldown_active_denies(db_session):
    _, _, case = create_mock_case()
    recent_action = RecoveryAction(
        recovery_case_id=case.id,
        action_type=StrategyType.RETRY.value,
        executed_at=SAFE_IST_TIME_UTC - timedelta(minutes=15), # Only 15m ago (cooldown = 60m)
    )
    case.actions.append(recent_action)
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}

    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res.decision == PolicyDecisionType.DENY.value
    assert res.blocking_rule == "COOLDOWN_ACTIVE"


# --- 5. Outside Contact Hours -> DENY ---
def test_5_outside_contact_hours_denies(db_session):
    _, _, case = create_mock_case()
    ctx = {"current_time_utc": OUTSIDE_IST_TIME_UTC} # 8 AM IST (before 9 AM start)
    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res.decision == PolicyDecisionType.DENY.value
    assert res.blocking_rule == "CONTACT_HOURS"


# --- 6. Duplicate Active Action -> DENY ---
def test_6_duplicate_active_action_denies(db_session):
    _, _, case = create_mock_case()
    active_link = RecoveryAction(
        recovery_case_id=case.id,
        action_type=StrategyType.PAYMENT_LINK.value,
        razorpay_payment_link_id="plink_ACTIVE_123",
        status="SENT",
        executed_at=SAFE_IST_TIME_UTC - timedelta(hours=2),
    )
    case.actions.append(active_link)
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}

    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res.decision == PolicyDecisionType.DENY.value
    assert res.blocking_rule == "ACTIVE_PAYMENT_LINK"


# --- 7. Already Recovered -> DENY ---
def test_7_already_recovered_denies(db_session):
    _, _, case = create_mock_case(status=RecoveryCaseStatus.RECOVERED.value, is_terminal=True)
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res.decision == PolicyDecisionType.DENY.value
    assert res.blocking_rule == "TERMINAL_STATE"


# --- 8. High Value -> ESCALATE ---
def test_8_high_value_escalates(db_session):
    _, _, case = create_mock_case(amount_paise=1500000) # ₹15,000 (exceeds ₹10,000 threshold)
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res.decision == PolicyDecisionType.ESCALATE.value
    assert res.blocking_rule == "HIGH_VALUE"
    assert res.requires_human is True
    assert res.can_execute_action is False


# --- 9. Low Confidence -> ESCALATE ---
def test_9_low_confidence_escalates(db_session):
    _, _, case = create_mock_case()
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.45, context=ctx) # Below 0.60
    assert res.decision == PolicyDecisionType.ESCALATE.value
    assert res.blocking_rule == "LOW_CONFIDENCE"


# --- 10. Insufficient Evidence / Strategy Constraints ---
def test_10_human_review_strategy_escalates(db_session):
    _, _, case = create_mock_case()
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res = PolicyEngine.evaluate(case, StrategyType.HUMAN_REVIEW.value, ai_confidence=0.90, context=ctx)
    assert res.decision == PolicyDecisionType.ESCALATE.value
    assert res.blocking_rule == "STRATEGY_CONSTRAINTS"


# --- 11. Suspicious Pattern -> DENY ---
def test_11_suspicious_pattern_denies(db_session):
    cust, _, case = create_mock_case(customer_type=CustomerType.FATIGUED.value)
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res.decision == PolicyDecisionType.DENY.value
    assert res.blocking_rule == "TRUST_GATE_SUSPICIOUS"


# --- 12. Terminal State -> DENY ---
def test_12_terminal_state_denies(db_session):
    _, _, case = create_mock_case(status=RecoveryCaseStatus.POLICY_BLOCKED.value, is_terminal=True)
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res.decision == PolicyDecisionType.DENY.value
    assert res.blocking_rule == "TERMINAL_STATE"


# --- 13. Unsupported Strategy -> DENY ---
def test_13_unsupported_strategy_denies(db_session):
    _, _, case = create_mock_case()
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res = PolicyEngine.evaluate(case, "INVALID_UNSUPPORTED_STRATEGY", ai_confidence=0.90, context=ctx)
    assert res.decision == PolicyDecisionType.DENY.value
    assert res.blocking_rule == "UNSUPPORTED_STRATEGY"


# --- 14. Max Automated Action Amount Exceeded -> DENY ---
def test_14_max_automated_amount_exceeded_denies(db_session):
    _, _, case = create_mock_case(amount_paise=6000000) # ₹60,000 (exceeds ₹50,000 max auto limit)
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res.decision == PolicyDecisionType.DENY.value
    assert res.blocking_rule == "MAX_AUTOMATED_AMOUNT"


# --- 15. Conflicting Rules Precedence ---
def test_15_conflicting_rules_precedence(db_session):
    """Verify precedence order: TERMINAL_STATE > HIGH_VALUE."""
    _, _, case = create_mock_case(
        amount_paise=1500000, # High value
        status=RecoveryCaseStatus.RECOVERED.value,
        is_terminal=True, # Terminal state
    )
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res.decision == PolicyDecisionType.DENY.value
    assert res.blocking_rule == "TERMINAL_STATE" # Terminal state precedes high value


# --- 16, 17, 18. Policy Version, Decision & Audit Persistence ---
def test_16_17_18_policy_persistence(db_session):
    cust, txn, case = create_mock_case()
    db_session.add_all([cust, txn, case])
    db_session.commit()

    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res = PolicyEngine.evaluate(
        case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx, db=db_session, persist_decision=True
    )
    db_session.commit()

    # Verify PolicyDecision table persistence
    record = db_session.query(PolicyDecision).filter_by(recovery_case_id=case.id).first()
    assert record is not None
    assert record.decision == "APPROVE"

    # Verify AuditEvent persistence with policy version
    audit = db_session.query(AuditEvent).filter_by(recovery_case_id=case.id, event_type="POLICY_EVALUATED").first()
    assert audit is not None
    assert audit.details["policy_version"] == "v1.0"


# --- 19. Changing Configuration Changes Decision Deterministically ---
def test_19_changing_configuration_changes_decision(db_session):
    _, _, case = create_mock_case(amount_paise=1500000) # ₹15,000
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}

    # Default config (high_value = ₹10,000) -> ESCALATE
    res1 = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res1.decision == PolicyDecisionType.ESCALATE.value

    # Override config (high_value = ₹20,000) -> APPROVE
    custom_cfg = PolicyConfig(high_value_threshold_paise=2000000)
    res2 = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx, config_override=custom_cfg)
    assert res2.decision == PolicyDecisionType.APPROVE.value


# --- 20. Same Input Produces Same Output (Repeatability) ---
def test_20_repeatability_and_determinism(db_session):
    _, _, case = create_mock_case()
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res1 = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    res2 = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res1.decision == res2.decision
    assert res1.blocking_rule == res2.blocking_rule


# --- Boundary Values Testing ---
@pytest.mark.parametrize(
    "amount,expected_decision",
    [
        (1000000, PolicyDecisionType.APPROVE.value), # Exactly ₹10,000.00 -> APPROVE
        (1000001, PolicyDecisionType.ESCALATE.value), # ₹10,000.01 -> ESCALATE
        (5000000, PolicyDecisionType.ESCALATE.value), # Exactly ₹50,000.00 -> ESCALATE
        (5000001, PolicyDecisionType.DENY.value), # ₹50,000.01 -> DENY (Max auto exceeded)
    ]
)
def test_boundary_amounts(db_session, amount, expected_decision):
    _, _, case = create_mock_case(amount_paise=amount)
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)
    assert res.decision == expected_decision


# --- Property & Authorization Invariants ---
def test_invariant_deny_and_escalate_never_execute_action(db_session):
    """PROPERTY INVARIANT: DENY and ESCALATE strictly reject action authorization."""
    _, _, case = create_mock_case(amount_paise=1500000) # High value -> ESCALATE
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}
    policy_res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=0.90, context=ctx)

    assert policy_res.decision == PolicyDecisionType.ESCALATE.value
    assert policy_res.can_execute_action is False

    with pytest.raises(ActionAuthorizationError) as exc_info:
        ActionAuthorizationService.authorize_action(case, policy_res)
    assert exc_info.value.decision == PolicyDecisionType.ESCALATE.value

def test_invariant_llm_cannot_bypass_policy(db_session):
    """PROPERTY INVARIANT: Changing LLM confidence or prompt cannot bypass policy rules."""
    _, _, case = create_mock_case(attempt_count=2) # Max retries exceeded
    ctx = {"current_time_utc": SAFE_IST_TIME_UTC}

    # Even if LLM has 100% confidence, policy DENIES execution
    res = PolicyEngine.evaluate(case, StrategyType.PAYMENT_LINK.value, ai_confidence=1.00, context=ctx)
    assert res.decision == PolicyDecisionType.DENY.value
    assert res.can_execute_action is False
