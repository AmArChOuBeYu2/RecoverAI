"""
Unit and Integration Tests for AuditService — Milestone 19
Validates centralized audit event logging, chronological case timeline generation,
correlation tracking (case_id and batch_run_id), paginated event querying,
and webhook idempotency.
"""

import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError

from backend.database.session import Base
from backend.models.customer import Customer
from backend.models.transaction import Transaction
from backend.models.recovery_case import RecoveryCase
from backend.models.audit_event import AuditEvent
from backend.models.enums import TransactionStatus, FailureCategory, RecoveryCaseStatus
from backend.services.audit import (
    AuditService,
    EVENT_TYPE_DETECTED,
    EVENT_TYPE_SEGMENTED,
    EVENT_TYPE_POLICY_APPROVED,
    EVENT_TYPE_ACTION_EXECUTED,
    ACTOR_SYSTEM,
    ACTOR_POLICY,
    ACTOR_RAZORPAY,
)

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=test_engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture
def db_session():
    """Clean in-memory DB session for audit service testing."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

def create_sample_case(db_session: Session) -> RecoveryCase:
    """Helper to create Customer, Transaction, and RecoveryCase."""
    cust = Customer(name="Audit User", email=f"audit_{uuid.uuid4().hex[:6]}@example.com")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(
        razorpay_payment_id=f"pay_audit_{uuid.uuid4().hex[:6]}",
        customer_id=cust.id,
        amount_paise=250000,
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
        status=RecoveryCaseStatus.DETECTED.value,
    )
    db_session.add(case)
    db_session.flush()
    return case


def test_audit_log_event_creation(db_session: Session):
    """Test central AuditService.log_event creates a valid AuditEvent record."""
    case = create_sample_case(db_session)

    event = AuditService.log_event(
        db=db_session,
        recovery_case_id=case.id,
        event_type=EVENT_TYPE_DETECTED,
        description="Payment failure detected and recovery case initialized",
        actor=ACTOR_SYSTEM,
        details={"failure_category": "AUTHENTICATION_FAILURE", "amount_paise": 250000},
        batch_run_id="batch_test_123",
    )

    assert event.id is not None
    assert event.recovery_case_id == case.id
    assert event.event_type == EVENT_TYPE_DETECTED
    assert event.actor == ACTOR_SYSTEM
    assert event.description == "Payment failure detected and recovery case initialized"
    assert event.details["batch_run_id"] == "batch_test_123"
    assert event.details["amount_paise"] == 250000


def test_get_events_for_case(db_session: Session):
    """Test retrieving chronological audit events for a specific case."""
    case = create_sample_case(db_session)

    AuditService.log_event(db_session, EVENT_TYPE_DETECTED, "Case detected", recovery_case_id=case.id)
    AuditService.log_event(db_session, EVENT_TYPE_SEGMENTED, "Assigned segment", recovery_case_id=case.id)
    AuditService.log_event(db_session, EVENT_TYPE_POLICY_APPROVED, "Policy approved", recovery_case_id=case.id, actor=ACTOR_POLICY)

    events = AuditService.get_events_for_case(db_session, case.id)

    assert len(events) == 3
    assert events[0].event_type == EVENT_TYPE_DETECTED
    assert events[1].event_type == EVENT_TYPE_SEGMENTED
    assert events[2].event_type == EVENT_TYPE_POLICY_APPROVED


def test_get_timeline_for_case(db_session: Session):
    """Test generating a structured timeline for a case."""
    case = create_sample_case(db_session)

    AuditService.log_event(db_session, EVENT_TYPE_DETECTED, "Payment failure detected", recovery_case_id=case.id)
    AuditService.log_event(db_session, EVENT_TYPE_ACTION_EXECUTED, "Payment link generated", recovery_case_id=case.id, actor=ACTOR_RAZORPAY)

    timeline = AuditService.get_timeline_for_case(db_session, case.id)

    assert timeline["case_id"] == case.id
    assert timeline["transaction_id"] == case.transaction_id
    assert timeline["status"] == RecoveryCaseStatus.DETECTED.value
    assert timeline["total_events"] == 2
    assert len(timeline["timeline"]) == 2
    assert timeline["timeline"][0]["event_type"] == EVENT_TYPE_DETECTED
    assert timeline["timeline"][1]["actor"] == ACTOR_RAZORPAY


def test_query_events_with_filters(db_session: Session):
    """Test querying audit events with filter parameters."""
    case = create_sample_case(db_session)

    AuditService.log_event(
        db=db_session,
        event_type=EVENT_TYPE_ACTION_EXECUTED,
        description="Action executed",
        recovery_case_id=case.id,
        actor=ACTOR_RAZORPAY,
        batch_run_id="batch_abc_456",
    )

    results = AuditService.query_events(
        db=db_session,
        recovery_case_id=case.id,
        event_type=EVENT_TYPE_ACTION_EXECUTED,
        actor=ACTOR_RAZORPAY,
        batch_run_id="batch_abc_456",
    )

    assert len(results) == 1
    assert results[0].recovery_case_id == case.id
    assert results[0].actor == ACTOR_RAZORPAY


def test_webhook_idempotency_via_audit_event_id(db_session: Session):
    """Test database-enforced unique constraint on event_id for webhook idempotency."""
    evt_id = f"evt_webhook_{uuid.uuid4().hex[:8]}"

    AuditService.log_event(
        db=db_session,
        event_type="WEBHOOK_RECEIVED",
        description="Webhook received first time",
        event_id=evt_id,
    )

    # Attempting duplicate event_id insertion must raise IntegrityError
    with pytest.raises(IntegrityError):
        AuditService.log_event(
            db=db_session,
            event_type="WEBHOOK_RECEIVED",
            description="Webhook duplicate attempt",
            event_id=evt_id,
        )
    db_session.rollback()
