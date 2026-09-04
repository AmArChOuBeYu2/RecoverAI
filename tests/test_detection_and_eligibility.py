"""
Unit and Integration Test Suite for Milestone 10 — Detection, Context & Eligibility
Validates DetectionEngine, ContextBuilder, EligibilityChecker rules, state machine transitions,
and Recovery REST API endpoints.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

import backend.models  # noqa: F401 - Register all models with Base.metadata
from backend.database.session import Base, get_db
from backend.main import app
from backend.services.detection import DetectionEngine
from backend.services.context_builder import ContextBuilder
from backend.services.eligibility import EligibilityChecker
from backend.services.segmentation import SegmentationService
from backend.models.segment import Segment
from backend.models.recovery_case import RecoveryCase
from backend.models.transaction import Transaction
from backend.models.customer import Customer
from backend.models.recovery_action import RecoveryAction
from backend.models.audit_event import AuditEvent
from backend.models.enums import (
    FailureCategory,
    AmountRange,
    CustomerType,
    RecoveryCaseStatus,
    TransactionStatus,
    DataCategory,
)

# Shared in-memory engine across test connections using StaticPool
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
    """Fixture returning a clean test database session connected to FastAPI app dependency."""
    session = TestingSessionLocal()
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()

# -----------------------------------------------------------------------------
# 1. DetectionEngine Tests
# -----------------------------------------------------------------------------

def test_detection_engine_unhandled_failures(db_session: Session):
    """Verify DetectionEngine finds unhandled failed transactions and advances them to SEGMENTED."""
    cust = Customer(email="det_test@example.com", phone="+919876543210", name="Detection User", customer_type="RETURNING")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(
        razorpay_payment_id="pay_det_101",
        customer_id=cust.id,
        amount_paise=150000,
        currency="INR",
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.AUTHENTICATION_FAILURE.value,
        payment_method="card",
        data_source=DataCategory.OBSERVED.value,
    )
    db_session.add(txn)
    db_session.flush()

    cases = DetectionEngine.detect_unhandled_failures(db_session)
    assert len(cases) >= 1
    case = next(c for c in cases if c.transaction_id == txn.id)

    assert case.transaction_id == txn.id
    assert case.status == RecoveryCaseStatus.SEGMENTED.value
    assert case.segment_id is not None
    assert case.segment.name == "authentication_failure_card_mid_returning"

    # Verify audit log
    audit = db_session.query(AuditEvent).filter_by(recovery_case_id=case.id, event_type="CASE_DETECTED").first()
    assert audit is not None

# -----------------------------------------------------------------------------
# 2. ContextBuilder Tests
# -----------------------------------------------------------------------------

def test_context_builder_assembly(db_session: Session):
    """Verify ContextBuilder assembles structured context for transaction, customer, segment, and history."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    created_time = now - timedelta(hours=5)

    cust = Customer(
        email="ctx_user@example.com",
        phone="+919999988888",
        name="Context User",
        customer_type="RETURNING",
        contacts_count_24h=1,
        total_transactions=5,
        successful_transactions=3,
        failed_transactions=2,
    )
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(
        razorpay_payment_id="pay_ctx_101",
        customer_id=cust.id,
        amount_paise=250000, # ₹2,500
        currency="INR",
        status="FAILED",
        failure_category=FailureCategory.BANK_TIMEOUT.value,
        error_code="BAD_REQUEST_ERROR",
        error_description="Bank gateway timeout",
        payment_method="upi",
        created_at=created_time,
    )
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(
        transaction_id=txn.id,
        customer_id=cust.id,
        status=RecoveryCaseStatus.DETECTED.value,
        attempt_count=0,
    )
    db_session.add(case)
    db_session.flush()

    SegmentationService.assign_segment_to_case(db_session, case)
    db_session.flush()

    ctx = ContextBuilder.assemble_case_context(db_session, case, as_of_time=now)

    assert ctx["case"]["id"] == case.id
    assert ctx["transaction"]["amount_paise"] == 250000
    assert ctx["transaction"]["amount_rupees"] == 2500.0
    assert ctx["transaction"]["age_hours"] == 5.0
    assert ctx["customer"]["email"] == "ctx_user@example.com"
    assert ctx["customer"]["customer_type"] == "RETURNING"
    assert ctx["segment"]["name"] == "bank_timeout_upi_mid_returning"
    assert ctx["recovery_history"]["attempt_count"] == 0

# -----------------------------------------------------------------------------
# 3. EligibilityChecker Rule & State Machine Tests
# -----------------------------------------------------------------------------

def test_eligibility_all_checks_pass(db_session: Session):
    """Verify eligible case transitions SEGMENTED -> ELIGIBLE."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)

    cust = Customer(email="elig_ok@example.com", phone="+919876543210", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(
        razorpay_payment_id="pay_elig_ok",
        customer_id=cust.id,
        amount_paise=100000,
        status="FAILED",
        failure_category=FailureCategory.AUTHENTICATION_FAILURE.value,
        payment_method="card",
        created_at=now - timedelta(hours=2),
    )
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.DETECTED.value, attempt_count=0)
    db_session.add(case)
    db_session.flush()

    SegmentationService.assign_segment_to_case(db_session, case)
    db_session.flush()

    res = EligibilityChecker.evaluate_eligibility(db_session, case, as_of_time=now)

    assert res.is_eligible is True
    assert res.status == RecoveryCaseStatus.ELIGIBLE.value
    assert case.status == RecoveryCaseStatus.ELIGIBLE.value
    assert res.primary_blocking_reason is None

def test_eligibility_zero_amount_rejected(db_session: Session):
    """Verify 0 amount transaction is marked INELIGIBLE."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)

    cust = Customer(email="zero_amt@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_zero", customer_id=cust.id, amount_paise=0, status="FAILED", failure_category="AUTHENTICATION_FAILURE", created_at=now)
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.DETECTED.value, attempt_count=0)
    db_session.add(case)
    db_session.flush()

    SegmentationService.assign_segment_to_case(db_session, case)
    db_session.flush()

    res = EligibilityChecker.evaluate_eligibility(db_session, case, as_of_time=now)

    assert res.is_eligible is False
    assert res.status == RecoveryCaseStatus.INELIGIBLE.value
    assert case.status == RecoveryCaseStatus.INELIGIBLE.value
    assert case.is_terminal is True
    assert "Transaction amount must be > 0" in res.primary_blocking_reason

def test_eligibility_expired_age_rejected(db_session: Session):
    """Verify transaction older than 72h is marked INELIGIBLE."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    old_time = now - timedelta(hours=80)

    cust = Customer(email="old_tx@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_old", customer_id=cust.id, amount_paise=100000, status="FAILED", failure_category="AUTHENTICATION_FAILURE", created_at=old_time)
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.DETECTED.value, attempt_count=0)
    db_session.add(case)
    db_session.flush()

    SegmentationService.assign_segment_to_case(db_session, case)
    db_session.flush()

    res = EligibilityChecker.evaluate_eligibility(db_session, case, as_of_time=now)

    assert res.is_eligible is False
    assert res.status == RecoveryCaseStatus.INELIGIBLE.value
    assert "exceeds max allowed 72" in res.primary_blocking_reason

def test_eligibility_missing_contact_rejected(db_session: Session):
    """Verify transaction with no customer email or phone is marked INELIGIBLE."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)

    cust = Customer(email=None, phone=None, name="No Contact User", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_no_contact", customer_id=cust.id, amount_paise=100000, status="FAILED", failure_category="AUTHENTICATION_FAILURE", created_at=now)
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.DETECTED.value, attempt_count=0)
    db_session.add(case)
    db_session.flush()

    SegmentationService.assign_segment_to_case(db_session, case)
    db_session.flush()

    res = EligibilityChecker.evaluate_eligibility(db_session, case, as_of_time=now)

    assert res.is_eligible is False
    assert res.status == RecoveryCaseStatus.INELIGIBLE.value
    assert "No customer contact information" in res.primary_blocking_reason

def test_eligibility_retry_limit_rejected(db_session: Session):
    """Verify case with attempt_count >= 2 is marked INELIGIBLE."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)

    cust = Customer(email="retry_user@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_retry_max", customer_id=cust.id, amount_paise=100000, status="FAILED", failure_category="AUTHENTICATION_FAILURE", created_at=now)
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.DETECTED.value, attempt_count=2)
    db_session.add(case)
    db_session.flush()

    SegmentationService.assign_segment_to_case(db_session, case)
    db_session.flush()

    res = EligibilityChecker.evaluate_eligibility(db_session, case, as_of_time=now)

    assert res.is_eligible is False
    assert res.status == RecoveryCaseStatus.INELIGIBLE.value
    assert "Attempt count 2 reached maximum allowed 2" in res.primary_blocking_reason

# -----------------------------------------------------------------------------
# 4. REST API Endpoint Tests
# -----------------------------------------------------------------------------

def test_api_recovery_detect(db_session: Session):
    cust = Customer(email="api_det@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_api_det_101", customer_id=cust.id, amount_paise=100000, status="FAILED", failure_category="AUTHENTICATION_FAILURE", payment_method="card")
    db_session.add(txn)
    db_session.flush()

    response = client.post("/api/recovery/detect?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["detected_count"] >= 1

def test_api_recovery_cases_list(db_session: Session):
    response = client.get("/api/recovery/cases?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "total_count" in data
    assert "cases" in data

def test_api_recovery_context(db_session: Session):
    cust = Customer(email="api_ctx@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_api_ctx_101", customer_id=cust.id, amount_paise=100000, status="FAILED", failure_category="AUTHENTICATION_FAILURE", payment_method="card")
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.DETECTED.value, attempt_count=0)
    db_session.add(case)
    db_session.flush()

    c_id = case.id
    response = client.get(f"/api/recovery/context/{c_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["transaction"]["amount_paise"] == 100000

def test_api_recovery_eligibility_evaluate(db_session: Session):
    cust = Customer(email="api_elg@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_api_elg_101", customer_id=cust.id, amount_paise=100000, status="FAILED", failure_category="AUTHENTICATION_FAILURE", payment_method="card")
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.DETECTED.value, attempt_count=0)
    db_session.add(case)
    db_session.flush()

    c_id = case.id
    response = client.post(f"/api/recovery/eligibility/{c_id}")
    assert response.status_code == 200
    data = response.json()
    assert "is_eligible" in data
    assert data["status"] in ("ELIGIBLE", "INELIGIBLE")
