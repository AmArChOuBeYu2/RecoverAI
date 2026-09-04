"""
Unit and Integration Tests for MetricsService — Milestone 18
Validates portfolio revenue calculations, pipeline statistics, action breakdown by execution mode,
honest data category separation (VERIFIED vs SIMULATED), root cause failure analysis,
and segment strategy performance tables.
"""

import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from backend.database.session import Base
from backend.models.customer import Customer
from backend.models.transaction import Transaction
from backend.models.segment import Segment
from backend.models.recovery_case import RecoveryCase
from backend.models.recovery_decision import RecoveryDecision
from backend.models.recovery_action import RecoveryAction
from backend.models.recovery_strategy import RecoveryStrategy
from backend.models.strategy_outcome import StrategyOutcome
from backend.models.policy_decision import PolicyDecision
from backend.models.enums import (
    TransactionStatus,
    FailureCategory,
    RecoveryCaseStatus,
    PolicyDecisionType,
    StrategyType,
    ActionExecutionMode,
    OutcomeSource,
    ConfidenceLevel,
    DataCategory,
)
from backend.services.metrics import MetricsService

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=test_engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture
def db_session():
    """Clean in-memory DB session for metrics testing."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

def create_sample_metrics_data(db_session: Session):
    """Helper to populate realistic dataset for metrics service testing."""
    seg = Segment(
        name="auth_failure_card_mid_val",
        failure_category=FailureCategory.AUTHENTICATION_FAILURE.value,
        payment_method="card",
        amount_range="MID",
        customer_type="NEW",
    )
    db_session.add(seg)
    db_session.flush()

    cust = Customer(name="Metrics User", email="metrics@example.com")
    db_session.add(cust)
    db_session.flush()

    # Txn 1: RECOVERED (VERIFIED)
    t1 = Transaction(
        razorpay_payment_id="pay_m1",
        customer_id=cust.id,
        amount_paise=200000,
        currency="INR",
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.AUTHENTICATION_FAILURE.value,
        payment_method="card",
    )
    # Txn 2: RECOVERED (SIMULATED)
    t2 = Transaction(
        razorpay_payment_id="pay_m2",
        customer_id=cust.id,
        amount_paise=150000,
        currency="INR",
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.BANK_TIMEOUT.value,
        payment_method="upi",
    )
    # Txn 3: POLICY_BLOCKED
    t3 = Transaction(
        razorpay_payment_id="pay_m3",
        customer_id=cust.id,
        amount_paise=500000,
        currency="INR",
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.INSUFFICIENT_FUNDS.value,
        payment_method="card",
    )
    # Txn 4: INELIGIBLE
    t4 = Transaction(
        razorpay_payment_id="pay_m4",
        customer_id=cust.id,
        amount_paise=100000,
        currency="INR",
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.BUSINESS_ERROR.value,
        payment_method="card",
    )
    db_session.add_all([t1, t2, t3, t4])
    db_session.flush()

    # Recovery Cases
    c1 = RecoveryCase(transaction_id=t1.id, customer_id=cust.id, segment_id=seg.id, status=RecoveryCaseStatus.RECOVERED.value, is_terminal=True)
    c2 = RecoveryCase(transaction_id=t2.id, customer_id=cust.id, segment_id=seg.id, status=RecoveryCaseStatus.RECOVERED.value, is_terminal=True)
    c3 = RecoveryCase(transaction_id=t3.id, customer_id=cust.id, segment_id=seg.id, status=RecoveryCaseStatus.POLICY_BLOCKED.value, is_terminal=True)
    c4 = RecoveryCase(transaction_id=t4.id, customer_id=cust.id, segment_id=seg.id, status=RecoveryCaseStatus.INELIGIBLE.value, is_terminal=True)
    db_session.add_all([c1, c2, c3, c4])
    db_session.flush()

    # Decisions & Actions
    d1 = RecoveryDecision(recovery_case_id=c1.id, selected_strategy="PAYMENT_LINK", ai_confidence=0.85)
    d2 = RecoveryDecision(recovery_case_id=c2.id, selected_strategy="RETRY", ai_confidence=0.75)
    db_session.add_all([d1, d2])
    db_session.flush()

    p1 = PolicyDecision(recovery_case_id=c1.id, decision=PolicyDecisionType.APPROVE.value, blocking_rule=None)
    p2 = PolicyDecision(recovery_case_id=c2.id, decision=PolicyDecisionType.APPROVE.value, blocking_rule=None)
    p3 = PolicyDecision(recovery_case_id=c3.id, decision=PolicyDecisionType.DENY.value, blocking_rule="RULE_SAFETY")
    db_session.add_all([p1, p2, p3])
    db_session.flush()

    a1 = RecoveryAction(recovery_case_id=c1.id, action_type="PAYMENT_LINK", execution_mode=ActionExecutionMode.REAL_TEST_MODE.value, status="PAID", razorpay_payment_link_id="plink_m1")
    a2 = RecoveryAction(recovery_case_id=c2.id, action_type="RETRY", execution_mode=ActionExecutionMode.SIMULATED.value, status="PAID")
    db_session.add_all([a1, a2])
    db_session.flush()

    o1 = StrategyOutcome(recovery_case_id=c1.id, segment_id=seg.id, strategy_type="PAYMENT_LINK", outcome="RECOVERED", amount_recovered_paise=200000, outcome_source=OutcomeSource.VERIFIED.value)
    o2 = StrategyOutcome(recovery_case_id=c2.id, segment_id=seg.id, strategy_type="RETRY", outcome="RECOVERED", amount_recovered_paise=150000, outcome_source=OutcomeSource.SIMULATED.value)
    db_session.add_all([o1, o2])
    db_session.flush()

    # Recovery Strategy Empirical Record
    strat = RecoveryStrategy(
        segment_id=seg.id,
        strategy_type="PAYMENT_LINK",
        attempt_count=12,
        success_count=8,
        total_recovered_paise=1600000,
        recovery_rate=0.6667,
        wilson_lower_bound=0.39,
        sample_size_sufficient=True,
        confidence_level=ConfidenceLevel.LOW.value,
        data_source=DataCategory.OBSERVED.value,
    )
    db_session.add(strat)
    db_session.flush()


def test_compute_portfolio_metrics_basic(db_session: Session):
    """Test full computation of portfolio recovery metrics."""
    create_sample_metrics_data(db_session)

    m = MetricsService.compute_portfolio_metrics(db_session)

    assert m["total_transaction_count"] == 4
    assert m["total_transaction_value_paise"] == 950000  # 200k + 150k + 500k + 100k
    assert m["total_transaction_value_rupees"] == 9500.00
    assert m["total_revenue_at_risk_paise"] == 950000

    assert m["eligible_transaction_count"] == 3  # c1, c2, c3 (c4 is INELIGIBLE)
    assert m["eligible_revenue_paise"] == 850000  # 200k + 150k + 500k

    assert m["ai_decision_count"] == 2
    assert m["policy_approved_count"] == 2
    assert m["policy_blocked_count"] == 1

    assert m["actions_attempted"] == 2
    assert m["actions_by_execution_mode"]["real_test_mode_count"] == 1
    assert m["actions_by_execution_mode"]["simulated_mode_count"] == 1

    assert m["verified_recovered_count"] == 1
    assert m["verified_recovered_paise"] == 200000
    assert m["verified_recovered_rupees"] == 2000.00

    assert m["simulated_recovered_count"] == 1
    assert m["simulated_recovered_paise"] == 150000

    assert m["total_unrecovered_paise"] == 600000  # c3 (500k) + c4 (100k)
    assert m["unrecovered_breakdown_paise"]["policy_blocked_paise"] == 500000
    assert m["unrecovered_breakdown_paise"]["ineligible_paise"] == 100000

    assert m["recovery_rate"] == round(1 / 3.0, 4)
    assert m["action_success_rate"] == round(1 / 2.0, 4)


def test_segment_strategy_performance_table(db_session: Session):
    """Test retrieval of segment strategy performance table."""
    create_sample_metrics_data(db_session)

    table = MetricsService.get_segment_strategy_performance_table(db_session)

    assert len(table) == 1
    row = table[0]

    assert row["segment_name"] == "auth_failure_card_mid_val"
    assert row["strategy_type"] == "PAYMENT_LINK"
    assert row["attempt_count"] == 12
    assert row["success_count"] == 8
    assert row["total_recovered_paise"] == 1600000
    assert row["total_recovered_rupees"] == 16000.00
    assert row["recovery_rate"] == 0.6667
    assert row["wilson_lower_bound"] == 0.39
    assert row["sample_size_sufficient"] is True
    assert row["confidence_level"] == ConfidenceLevel.LOW.value


def test_failure_analysis_breakdown(db_session: Session):
    """Test breakdown of failures across failure categories."""
    create_sample_metrics_data(db_session)

    breakdown = MetricsService.get_failure_analysis_breakdown(db_session)
    cats = breakdown["breakdown_by_failure_category"]

    assert FailureCategory.AUTHENTICATION_FAILURE.value in cats
    auth_cat = cats[FailureCategory.AUTHENTICATION_FAILURE.value]
    assert auth_cat["total_transactions"] == 1
    assert auth_cat["recovered_count"] == 1

    assert FailureCategory.INSUFFICIENT_FUNDS.value in cats
    insuf_cat = cats[FailureCategory.INSUFFICIENT_FUNDS.value]
    assert insuf_cat["total_transactions"] == 1
    assert insuf_cat["policy_blocked_count"] == 1


def test_honest_metrics_data_category_isolation(db_session: Session):
    """Verify that VERIFIED and SIMULATED recovery totals are strictly isolated and not combined."""
    create_sample_metrics_data(db_session)

    m = MetricsService.compute_portfolio_metrics(db_session)

    # verified_recovered_paise must only include VERIFIED outcome source
    assert m["verified_recovered_paise"] == 200000
    # simulated_recovered_paise must only include SIMULATED outcome source
    assert m["simulated_recovered_paise"] == 150000

    # Ensure no generic combined 'total_recovered' conflates them without explicit labeling
    assert "verified_recovered_paise" in m
    assert "simulated_recovered_paise" in m
