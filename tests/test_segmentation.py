"""
Unit and Integration Test Suite for Milestone 9 — Segmentation Engine
Validates 4D segment derivation, amount range boundaries, database initialization,
case assignment with state machine transitions, and Segments REST API routes.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

import backend.models  # noqa: F401 - Register all models with Base.metadata
from backend.database.session import Base, get_db
from backend.main import app
from backend.services.segmentation import SegmentationService
from backend.models.segment import Segment
from backend.models.recovery_case import RecoveryCase
from backend.models.transaction import Transaction
from backend.models.customer import Customer
from backend.models.recovery_strategy import RecoveryStrategy
from backend.models.audit_event import AuditEvent
from backend.models.enums import (
    FailureCategory,
    AmountRange,
    CustomerType,
    RecoveryCaseStatus,
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

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture
def db_session():
    """Fixture returning a clean test database session."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

# -----------------------------------------------------------------------------
# 1. 4D Segment Derivation & Boundary Tests
# -----------------------------------------------------------------------------

def test_derive_amount_range_boundaries():
    """Verify exact integer paise boundaries for AmountRange mapping."""
    # LOW: < ₹500 (< 50,000 paise)
    assert SegmentationService.derive_amount_range(0) == AmountRange.LOW.value
    assert SegmentationService.derive_amount_range(49999) == AmountRange.LOW.value

    # MID: ₹500 - ₹5,000 (50,000 - 500,000 paise)
    assert SegmentationService.derive_amount_range(50000) == AmountRange.MID.value
    assert SegmentationService.derive_amount_range(500000) == AmountRange.MID.value

    # HIGH: ₹5,000 - ₹50,000 (500,001 - 5,000,000 paise)
    assert SegmentationService.derive_amount_range(500001) == AmountRange.HIGH.value
    assert SegmentationService.derive_amount_range(5000000) == AmountRange.HIGH.value

    # PREMIUM: > ₹50,000 (> 5,000,000 paise)
    assert SegmentationService.derive_amount_range(5000001) == AmountRange.PREMIUM.value
    assert SegmentationService.derive_amount_range(10000000) == AmountRange.PREMIUM.value

def test_derive_canonical_segment_name():
    """Verify canonical 4D string construction: {category}_{method}_{amount}_{customer}."""
    name1 = SegmentationService.derive_canonical_segment_name(
        "AUTHENTICATION_FAILURE", "card", "MID", "RETURNING"
    )
    assert name1 == "authentication_failure_card_mid_returning"

    name2 = SegmentationService.derive_canonical_segment_name(
        "BANK_TIMEOUT", "upi", 600000, "FATIGUED"
    )
    assert name2 == "bank_timeout_upi_high_fatigued"

    # Default fallback handling
    name_default = SegmentationService.derive_canonical_segment_name(
        None, None, None, None
    )
    assert name_default == "unknown_unknown_mid_new"

# -----------------------------------------------------------------------------
# 2. Database Creation & Seeding Tests
# -----------------------------------------------------------------------------

def test_get_or_create_segment(db_session: Session):
    """Verify Segment auto-creation, strategy tracking initialization, and idempotency."""
    seg1 = SegmentationService.get_or_create_segment(
        db_session,
        failure_category="AUTHENTICATION_FAILURE",
        payment_method="card",
        amount_range_or_paise=150000, # MID
        customer_type="RETURNING",
    )
    db_session.commit()
    assert seg1.id is not None
    assert seg1.name == "authentication_failure_card_mid_returning"

    # Verify strategy tracking entries created
    strats = db_session.query(RecoveryStrategy).filter_by(segment_id=seg1.id).all()
    assert len(strats) == 7

    # Repeat lookup should return same segment object (idempotent)
    seg2 = SegmentationService.get_or_create_segment(
        db_session,
        failure_category="AUTHENTICATION_FAILURE",
        payment_method="card",
        amount_range_or_paise="MID",
        customer_type="RETURNING",
    )
    assert seg2.id == seg1.id

def test_seed_all_canonical_segments(db_session: Session):
    """Verify seeding all 336 canonical 4D segments in database."""
    segments = SegmentationService.seed_all_canonical_segments(db_session)
    assert len(segments) == 336
    count_db = db_session.query(Segment).count()
    assert count_db >= 336

# -----------------------------------------------------------------------------
# 3. Case Assignment & State Machine Transition Tests
# -----------------------------------------------------------------------------

def test_assign_segment_to_case(db_session: Session):
    """Verify RecoveryCase segmentation, state machine transition (DETECTED -> ANALYZED -> SEGMENTED), and audit log."""
    cust = Customer(email="test_seg@example.com", phone="+919876543210", name="Seg User", customer_type="FATIGUED")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(
        razorpay_payment_id="pay_seg_test_101",
        customer_id=cust.id,
        amount_paise=600000, # HIGH
        currency="INR",
        status="FAILED",
        failure_category=FailureCategory.BANK_TIMEOUT.value,
        payment_method="upi",
        data_source=DataCategory.OBSERVED.value,
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

    seg = SegmentationService.assign_segment_to_case(db_session, case)
    db_session.commit()

    assert case.segment_id == seg.id
    assert case.status == RecoveryCaseStatus.SEGMENTED.value
    assert seg.name == "bank_timeout_upi_high_fatigued"

    # Verify audit event recorded
    audit = db_session.query(AuditEvent).filter_by(recovery_case_id=case.id, event_type="CASE_SEGMENTED").first()
    assert audit is not None
    assert audit.details["segment_name"] == "bank_timeout_upi_high_fatigued"

# -----------------------------------------------------------------------------
# 4. REST API Endpoint Tests
# -----------------------------------------------------------------------------

def test_api_list_segments(db_session: Session):
    SegmentationService.get_or_create_segment(
        db_session, "AUTHENTICATION_FAILURE", "card", "MID", "NEW"
    )
    db_session.commit()

    response = client.get("/api/segments?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "total_count" in data
    assert "segments" in data
    assert data["total_count"] >= 1

def test_api_lookup_segment(db_session: Session):
    params = {
        "failure_category": "AUTHENTICATION_FAILURE",
        "payment_method": "card",
        "amount_range": "MID",
        "customer_type": "NEW",
    }
    response = client.get("/api/segments/lookup", params=params)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "authentication_failure_card_mid_new"
    assert "strategies" in data

def test_api_get_segment_detail(db_session: Session):
    seg = SegmentationService.get_or_create_segment(
        db_session, "INSUFFICIENT_FUNDS", "upi", "HIGH", "RETURNING"
    )
    db_session.commit()

    detail_resp = client.get(f"/api/segments/{seg.id}")
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert data["id"] == seg.id
    assert "strategies" in data

def test_api_get_segment_detail_404():
    response = client.get("/api/segments/invalid_segment_id_999")
    assert response.status_code == 404
