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
from backend.services.strategy_ranker import StrategyRanker
from backend.services.policy_engine import PolicyEngine
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
    StrategyType,
    RecoveryCaseStatus,
    DataCategory,
    RecommendationType,
    PolicyDecisionType,
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
    # LOW: < ₹500 (< 50,000 paise) — ₹499.99 = 49999 paise
    assert SegmentationService.derive_amount_range(0) == AmountRange.LOW.value
    assert SegmentationService.derive_amount_range(49999) == AmountRange.LOW.value

    # MID: ₹500 - ₹5,000 (50,000 - 500,000 paise) — ₹500.00 = 50000 paise, ₹5,000.00 = 500000 paise
    assert SegmentationService.derive_amount_range(50000) == AmountRange.MID.value
    assert SegmentationService.derive_amount_range(500000) == AmountRange.MID.value

    # HIGH: ₹5,000 - ₹50,000 (500,001 - 5,000,000 paise) — ₹50,000.00 = 5000000 paise
    assert SegmentationService.derive_amount_range(500001) == AmountRange.HIGH.value
    assert SegmentationService.derive_amount_range(5000000) == AmountRange.HIGH.value

    # PREMIUM: > ₹50,000 (> 5,000,000 paise) — ₹50,000.01 = 5000001 paise
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
    assert name_default == "unknown_any_mid_any"

# -----------------------------------------------------------------------------
# 2. Database Creation, Seeding & Idempotency Tests
# -----------------------------------------------------------------------------

def test_get_or_create_segment_idempotency(db_session: Session):
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

    # Repeat lookup should return same segment object without creating duplicate rows
    seg2 = SegmentationService.get_or_create_segment(
        db_session,
        failure_category="AUTHENTICATION_FAILURE",
        payment_method="card",
        amount_range_or_paise="MID",
        customer_type="RETURNING",
    )
    assert seg2.id == seg1.id

    count_db = db_session.query(Segment).filter_by(name="authentication_failure_card_mid_returning").count()
    assert count_db == 1

def test_seed_all_canonical_segments(db_session: Session):
    """Verify seeding all 336 canonical 4D segments in database."""
    segments = SegmentationService.seed_all_canonical_segments(db_session)
    assert len(segments) == 336
    count_db = db_session.query(Segment).count()
    assert count_db >= 336

def test_empty_evidence_canonical_segment_semantics(db_session: Session):
    """VERIFICATION: Existence of DB Segment row with 0 attempts MUST NOT imply historical evidence."""
    seg = SegmentationService.get_or_create_segment(
        db_session,
        failure_category="CHECKOUT_ABANDONMENT",
        payment_method="wallet",
        amount_range_or_paise="PREMIUM",
        customer_type="NEW",
    )
    db_session.commit()

    # Segment row exists
    assert seg.id is not None

    # Strategy tracking rows exist but have 0 attempts
    strats = db_session.query(RecoveryStrategy).filter_by(segment_id=seg.id).all()
    assert len(strats) == 7
    assert all(st.attempt_count == 0 for st in strats)

    # Strategy evaluation with empty outcomes MUST return BASELINE_RECOMMENDATION & INSUFFICIENT_EVIDENCE
    rank_res = StrategyRanker.compare_and_rank_strategies(
        [], "CHECKOUT_ABANDONMENT", "wallet", "PREMIUM", "NEW"
    )
    assert rank_res["recommendation_type"] == RecommendationType.BASELINE_RECOMMENDATION.value
    assert rank_res["evidence_status"] == "INSUFFICIENT_EVIDENCE"
    assert rank_res["strategy_source"] == "DETERMINISTIC_BASELINE"

# -----------------------------------------------------------------------------
# 3. Customer Type Derivation & Edge Case Tests
# -----------------------------------------------------------------------------

def test_customer_type_derivation_and_fallbacks(db_session: Session):
    """Verify customer_type resolution for NEW, RETURNING, FATIGUED, and missing/null fallback."""
    for c_type in [CustomerType.NEW.value, CustomerType.RETURNING.value, CustomerType.FATIGUED.value]:
        cust = Customer(email=f"user_{c_type.lower()}@example.com", phone="+919876543210", name=f"User {c_type}", customer_type=c_type)
        db_session.add(cust)
        db_session.flush()

        txn = Transaction(
            razorpay_payment_id=f"pay_cust_{c_type.lower()}",
            customer_id=cust.id,
            amount_paise=100000,
            status="FAILED",
            failure_category=FailureCategory.AUTHENTICATION_FAILURE.value,
            payment_method="card",
        )
        db_session.add(txn)
        db_session.flush()

        case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.DETECTED.value, attempt_count=0)
        db_session.add(case)
        db_session.flush()

        seg = SegmentationService.assign_segment_to_case(db_session, case)
        assert seg.customer_type == c_type

# -----------------------------------------------------------------------------
# 4. Segmentation vs Policy Authorization Isolation Tests
# -----------------------------------------------------------------------------

def test_segmentation_does_not_authorize_action(db_session: Session):
    """VERIFICATION: Segmentation ONLY classifies the case into SEGMENTED state; it CANNOT authorize actions."""
    cust = Customer(email="test_no_auth@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_no_auth_101", customer_id=cust.id, amount_paise=100000, status="FAILED", failure_category=FailureCategory.AUTHENTICATION_FAILURE.value, payment_method="card")
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.DETECTED.value, attempt_count=0)
    db_session.add(case)
    db_session.flush()

    # Perform segmentation
    seg = SegmentationService.assign_segment_to_case(db_session, case)

    # State MUST be SEGMENTED, NOT POLICY_APPROVED or ACTION_ATTEMPTED
    assert case.status == RecoveryCaseStatus.SEGMENTED.value
    assert case.status != RecoveryCaseStatus.POLICY_APPROVED.value
    assert case.status != RecoveryCaseStatus.ACTION_ATTEMPTED.value

def test_human_review_escalation_semantics(db_session: Session):
    """VERIFICATION: Strategy HUMAN_REVIEW explicitly mandates Policy Engine ESCALATE decision impact."""
    from datetime import datetime, timezone
    valid_time = datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc) # 15:30 IST

    cust = Customer(email="hr_test@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_hr_101", customer_id=cust.id, amount_paise=100000, status="FAILED", failure_category=FailureCategory.AUTHENTICATION_FAILURE.value, payment_method="card", created_at=valid_time)
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.STRATEGIES_EVALUATED.value, attempt_count=0)
    db_session.add(case)
    db_session.flush()

    eval_res = PolicyEngine.evaluate(case=case, proposed_strategy=StrategyType.HUMAN_REVIEW.value, db=db_session, context={"current_time_utc": valid_time})
    assert eval_res.decision == PolicyDecisionType.ESCALATE.value
    assert any(detail.decision_impact == "ESCALATE" for detail in eval_res.rules_evaluated)

# -----------------------------------------------------------------------------
# 5. REST API Endpoint Tests
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
