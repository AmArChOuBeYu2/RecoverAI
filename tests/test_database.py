"""
Comprehensive Database Model Test Suite for RecoverAI.
Verifies table creation, relationships, constraints, uniqueness, cascade behaviors, and persistence.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from backend.database.session import Base
from backend.models import (
    Customer,
    Transaction,
    Segment,
    RecoveryCase,
    RecoveryStrategy,
    StrategyOutcome,
    RecoveryDecision,
    RecoveryAction,
    PolicyDecision,
    PolicySimulation,
    AuditEvent,
    BatchRun,
    LLMInvocation,
    TransactionStatus,
    FailureCategory,
    RecoveryCaseStatus,
    StrategyType,
    DataCategory,
    OutcomeSource,
    ActionExecutionMode,
    PolicyDecisionType,
    AmountRange,
    CustomerType,
)
from backend.seed.generator import seed_default_segments

@pytest.fixture
def db_session():
    """Fixture that creates an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

def test_init_db_creates_all_tables(db_session):
    """Verify all 13 core models map to database tables properly."""
    table_names = Base.metadata.tables.keys()
    expected_tables = {
        "customers",
        "transactions",
        "segments",
        "recovery_cases",
        "recovery_strategies",
        "strategy_outcomes",
        "recovery_decisions",
        "recovery_actions",
        "policy_decisions",
        "policy_simulations",
        "audit_events",
        "batch_runs",
        "llm_invocations",
    }
    assert expected_tables.issubset(set(table_names))

def test_customer_transaction_relationship(db_session):
    """Verify Customer creation, Transaction persistence, and relationship navigation."""
    customer = Customer(
        email="test@example.com",
        phone="+919876543210",
        name="Aarav Sharma",
        customer_type=CustomerType.NEW.value,
    )
    db_session.add(customer)
    db_session.commit()

    transaction = Transaction(
        razorpay_payment_id="pay_TestPayment123",
        razorpay_order_id="order_TestOrder123",
        customer_id=customer.id,
        amount_paise=150000, # ₹1,500.00
        currency="INR",
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.AUTHENTICATION_FAILURE.value,
        data_source=DataCategory.SIMULATED.value,
    )
    db_session.add(transaction)
    db_session.commit()

    assert transaction.id is not None
    assert transaction.customer.email == "test@example.com"
    assert len(customer.transactions) == 1
    assert customer.transactions[0].amount_paise == 150000

def test_transaction_razorpay_payment_id_uniqueness(db_session):
    """Verify duplicate razorpay_payment_id raises IntegrityError."""
    t1 = Transaction(
        razorpay_payment_id="pay_DUPLICATE_ID",
        amount_paise=50000,
        status=TransactionStatus.FAILED.value,
    )
    db_session.add(t1)
    db_session.commit()

    t2 = Transaction(
        razorpay_payment_id="pay_DUPLICATE_ID",
        amount_paise=75000,
        status=TransactionStatus.FAILED.value,
    )
    db_session.add(t2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_audit_event_idempotency_constraint(db_session):
    """Verify duplicate event_id in AuditEvent raises IntegrityError (webhook idempotency)."""
    e1 = AuditEvent(
        event_type="WEBHOOK_RECEIVED",
        event_id="evt_razorpay_webhook_9999",
        description="Payment failed event received",
    )
    db_session.add(e1)
    db_session.commit()

    e2 = AuditEvent(
        event_type="WEBHOOK_RECEIVED",
        event_id="evt_razorpay_webhook_9999", # Same webhook event_id
        description="Duplicate webhook payload",
    )
    db_session.add(e2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_segment_strategy_uniqueness(db_session):
    """Verify (segment_id, strategy_type) unique constraint on RecoveryStrategy."""
    segment = Segment(
        name="auth_failure_card_mid_value",
        failure_category=FailureCategory.AUTHENTICATION_FAILURE.value,
        payment_method="card",
        amount_range=AmountRange.MID.value,
    )
    db_session.add(segment)
    db_session.commit()

    s1 = RecoveryStrategy(
        segment_id=segment.id,
        strategy_type=StrategyType.PAYMENT_LINK.value,
        data_source=DataCategory.OBSERVED.value,
    )
    db_session.add(s1)
    db_session.commit()

    s2 = RecoveryStrategy(
        segment_id=segment.id,
        strategy_type=StrategyType.PAYMENT_LINK.value, # Duplicate for same segment
        data_source=DataCategory.OBSERVED.value,
    )
    db_session.add(s2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_recovery_case_cascade_delete(db_session):
    """Verify deleting a RecoveryCase cascades to decisions, actions, and policy decisions."""
    t = Transaction(amount_paise=200000, status=TransactionStatus.FAILED.value)
    db_session.add(t)
    db_session.commit()

    case = RecoveryCase(
        transaction_id=t.id,
        status=RecoveryCaseStatus.DETECTED.value,
    )
    db_session.add(case)
    db_session.commit()

    decision = RecoveryDecision(
        recovery_case_id=case.id,
        selected_strategy=StrategyType.PAYMENT_LINK.value,
        reasoning_summary="Auth failure on mid-value card transaction",
    )
    action = RecoveryAction(
        recovery_case_id=case.id,
        action_type=StrategyType.PAYMENT_LINK.value,
        execution_mode=ActionExecutionMode.SIMULATED.value,
    )
    policy = PolicyDecision(
        recovery_case_id=case.id,
        decision=PolicyDecisionType.APPROVE.value,
    )
    db_session.add_all([decision, action, policy])
    db_session.commit()

    # Verify children exist
    assert db_session.query(RecoveryDecision).count() == 1
    assert db_session.query(RecoveryAction).count() == 1
    assert db_session.query(PolicyDecision).count() == 1

    # Delete recovery case
    db_session.delete(case)
    db_session.commit()

    # Verify children were cascade-deleted
    assert db_session.query(RecoveryDecision).count() == 0
    assert db_session.query(RecoveryAction).count() == 0
    assert db_session.query(PolicyDecision).count() == 0

def test_full_recovery_persistence_and_evidence_categories(db_session):
    """Verify complete entity graph persistence with explicit evidence categories."""
    batch = BatchRun(run_name="Demo Evaluation Batch 001", total_processed=1)
    db_session.add(batch)
    db_session.commit()

    cust = Customer(name="Priya Patel", email="priya@example.com")
    db_session.add(cust)
    db_session.commit()

    txn = Transaction(
        razorpay_payment_id="pay_LIVE_TEST_101",
        customer_id=cust.id,
        amount_paise=350000,
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.BANK_TIMEOUT.value,
        data_source=DataCategory.OBSERVED.value,
    )
    db_session.add(txn)
    db_session.commit()

    seg = Segment(
        name="bank_timeout_upi_mid_value",
        failure_category=FailureCategory.BANK_TIMEOUT.value,
        amount_range=AmountRange.MID.value,
    )
    db_session.add(seg)
    db_session.commit()

    case = RecoveryCase(
        transaction_id=txn.id,
        customer_id=cust.id,
        segment_id=seg.id,
        status=RecoveryCaseStatus.RECOVERED.value,
        recoverability_score=0.85,
        is_eligible=True,
    )
    db_session.add(case)
    db_session.commit()

    strat = RecoveryStrategy(
        segment_id=seg.id,
        strategy_type=StrategyType.PAYMENT_LINK.value,
        attempt_count=10,
        success_count=6,
        total_recovered_paise=2100000,
        recovery_rate=0.60,
        data_source=DataCategory.OBSERVED.value,
    )
    db_session.add(strat)
    db_session.commit()

    outcome = StrategyOutcome(
        recovery_case_id=case.id,
        recovery_strategy_id=strat.id,
        segment_id=seg.id,
        strategy_type=StrategyType.PAYMENT_LINK.value,
        outcome="RECOVERED",
        amount_recovered_paise=350000,
        outcome_source=OutcomeSource.VERIFIED.value, # VERIFIED recovery via Razorpay API
        attributed_at=datetime.now(timezone.utc),
    )
    db_session.add(outcome)

    audit = AuditEvent(
        recovery_case_id=case.id,
        event_type="RECOVERY_COMPLETED",
        event_id="evt_test_verified_101",
        description="Payment link paid in Razorpay Test Mode",
    )
    db_session.add(audit)

    llm = LLMInvocation(
        recovery_case_id=case.id,
        batch_run_id=batch.id,
        provider="openai",
        model="gpt-4o",
        latency_ms=320,
        prompt_tokens=450,
        completion_tokens=120,
        success=True,
    )
    db_session.add(llm)
    db_session.commit()

    # Query and verify graph integrity
    retrieved_case = db_session.query(RecoveryCase).filter_by(id=case.id).first()
    assert retrieved_case is not None
    assert retrieved_case.transaction.razorpay_payment_id == "pay_LIVE_TEST_101"
    assert retrieved_case.segment.name == "bank_timeout_upi_mid_value"
    assert len(retrieved_case.outcomes) == 1
    assert retrieved_case.outcomes[0].outcome_source == "VERIFIED"
    assert retrieved_case.outcomes[0].amount_recovered_paise == 350000
    assert len(retrieved_case.audit_events) == 1
    assert len(retrieved_case.llm_invocations) == 1
    assert retrieved_case.llm_invocations[0].provider == "openai"

def test_seed_default_segments(db_session):
    """Verify seed_default_segments creates standard segments and strategy templates idempotently."""
    segments = seed_default_segments(db_session)
    assert len(segments) == 5
    assert db_session.query(Segment).count() == 5
    # 5 segments x 3 strategy templates each = 15 recovery strategy templates
    assert db_session.query(RecoveryStrategy).count() == 15

    # Run second time to verify idempotency
    segments_again = seed_default_segments(db_session)
    assert db_session.query(Segment).count() == 5
    assert db_session.query(RecoveryStrategy).count() == 15
