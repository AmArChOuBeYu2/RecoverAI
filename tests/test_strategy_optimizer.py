"""
Unit and Integration Test Suite for Milestone 13 — Strategy Optimizer & Strategy Performance REST API
Validates portfolio aggregation, attempt-weighted rates, integer paise sums, sample size tiers,
zero evidence handling, evidence provenance preservation, canonical segment comparison, and REST API endpoints.
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

import backend.models  # noqa: F401 - Register models
from backend.database.session import Base, get_db
from backend.main import app
from backend.models.segment import Segment
from backend.models.recovery_case import RecoveryCase
from backend.models.transaction import Transaction
from backend.models.customer import Customer
from backend.models.strategy_outcome import StrategyOutcome
from backend.models.enums import FailureCategory, StrategyType, DataCategory, EvidenceProvenance
from backend.services.strategy_optimizer import StrategyOptimizer
from backend.services.segmentation import SegmentationService

# Setup test DB engine
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

# -----------------------------------------------------------------------------
# 1. Portfolio Aggregation & Mathematical Precision Tests
# -----------------------------------------------------------------------------

def test_portfolio_attempt_weighted_aggregation(db_session: Session):
    """
    Verify portfolio-wide recovery rate is calculated as total_successes / total_attempts,
    NOT as a simple unweighted average of strategy recovery rates.
    """
    cust = Customer(email="agg_user@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_agg_1", customer_id=cust.id, amount_paise=100000, status="FAILED", failure_category="AUTHENTICATION_FAILURE")
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status="SEGMENTED", attempt_count=0)
    db_session.add(case)
    db_session.flush()
    SegmentationService.assign_segment_to_case(db_session, case)

    # Strategy 1: 10 attempts, 2 recoveries (20% rate)
    for i in range(10):
        so = StrategyOutcome(
            recovery_case_id=case.id,
            strategy_type="PAYMENT_LINK",
            segment_id=case.segment_id,
            outcome="RECOVERED" if i < 2 else "UNRECOVERED",
            amount_recovered_paise=100000 if i < 2 else 0,
            outcome_source="SIMULATED",
        )
        db_session.add(so)

    # Strategy 2: 2 attempts, 2 recoveries (100% rate)
    for i in range(2):
        so = StrategyOutcome(
            recovery_case_id=case.id,
            strategy_type="METHOD_SWITCH",
            segment_id=case.segment_id,
            outcome="RECOVERED",
            amount_recovered_paise=100000,
            outcome_source="SIMULATED",
        )
        db_session.add(so)

    db_session.flush()

    summary = StrategyOptimizer.get_strategy_performance_summary(db_session)
    metrics = summary["portfolio_metrics"]

    # Total attempts = 12, total successes = 4
    # Attempt-weighted rate = 4/12 = 0.3333 (33.33%)
    # Simple average would be (20% + 100%)/2 = 60% (INCORRECT!)
    assert metrics["total_attempts"] == 12
    assert metrics["total_successes"] == 4
    assert metrics["total_recovered_paise"] == 400000
    assert metrics["total_recovered_rupees"] == 4000.0
    assert round(metrics["portfolio_recovery_rate"], 4) == 0.3333

# -----------------------------------------------------------------------------
# 2. Sample Size Tiers & Zero Evidence Tests
# -----------------------------------------------------------------------------

def test_zero_evidence_sample_tier(db_session: Session):
    """Verify zero attempts strategy stays INSUFFICIENT tier and is NOT treated as poor performance."""
    summary = StrategyOptimizer.get_strategy_performance_summary(db_session)
    strats = {s["strategy_type"]: s for s in summary["strategies"]}

    p_link = strats["PAYMENT_LINK"]
    assert p_link["attempt_count"] == 0
    assert p_link["sample_size_tier"] == "INSUFFICIENT"
    assert p_link["sample_size_sufficient"] is False
    assert p_link["recovery_rate"] == 0.0

# -----------------------------------------------------------------------------
# 3. Evidence Category & Provenance Preservation Tests
# -----------------------------------------------------------------------------

def test_verified_evidence_provenance_preservation(db_session: Session):
    """Verify TEST_MODE_VERIFIED outcomes preserve VERIFIED category and RAZORPAY_TEST_MODE provenance."""
    cust = Customer(email="ver_prov@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_ver_prov", customer_id=cust.id, amount_paise=100000, status="FAILED", failure_category="AUTHENTICATION_FAILURE")
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status="SEGMENTED", attempt_count=0)
    db_session.add(case)
    db_session.flush()
    SegmentationService.assign_segment_to_case(db_session, case)

    so = StrategyOutcome(
        recovery_case_id=case.id,
        strategy_type="PAYMENT_LINK",
        segment_id=case.segment_id,
        outcome="RECOVERED",
        amount_recovered_paise=100000,
        outcome_source="TEST_MODE_VERIFIED",
    )
    db_session.add(so)
    db_session.flush()

    summary = StrategyOptimizer.get_strategy_performance_summary(db_session)
    strats = {s["strategy_type"]: s for s in summary["strategies"]}
    p_link = strats["PAYMENT_LINK"]

    assert p_link["evidence_category"] == DataCategory.VERIFIED.value
    assert p_link["evidence_provenance"] == EvidenceProvenance.RAZORPAY_TEST_MODE.value

# -----------------------------------------------------------------------------
# 4. Segment Lookup & Comparison Tests
# -----------------------------------------------------------------------------

def test_get_segment_strategy_performance_nonexistent(db_session: Session):
    """Verify non-existent segment_id returns None (maps to 404)."""
    res = StrategyOptimizer.get_segment_strategy_performance(db_session, "non_existent_id_999")
    assert res is None

def test_compare_strategies_canonical_resolution(db_session: Session):
    """Verify compare_strategies resolves canonical segment and returns candidate comparison matrix."""
    res = StrategyOptimizer.compare_strategies(
        db=db_session,
        failure_category="AUTHENTICATION_FAILURE",
        payment_method="card",
        amount_range="MID",
        customer_type="NEW",
    )
    assert res["failure_category"] == "AUTHENTICATION_FAILURE"
    assert res["segment_name"] == "authentication_failure_card_mid_new"
    assert len(res["ranked_strategies"]) == 5

# -----------------------------------------------------------------------------
# 5. REST API Endpoints Tests
# -----------------------------------------------------------------------------

def test_api_get_strategies_summary(db_session: Session):
    response = client.get("/api/strategies")
    assert response.status_code == 200
    data = response.json()
    assert "portfolio_metrics" in data
    assert "strategies" in data

def test_api_get_strategies_filtered(db_session: Session):
    response = client.get("/api/strategies?failure_category=AUTHENTICATION_FAILURE&payment_method=card")
    assert response.status_code == 200
    data = response.json()
    assert data["filters"]["failure_category"] == "AUTHENTICATION_FAILURE"
    assert data["filters"]["payment_method"] == "card"

def test_api_get_strategies_invalid_filter_400():
    response = client.get("/api/strategies?failure_category=INVALID_CAT")
    assert response.status_code == 400

def test_api_compare_strategies(db_session: Session):
    response = client.get("/api/strategies/compare?failure_category=AUTHENTICATION_FAILURE&payment_method=card&amount_range=MID")
    assert response.status_code == 200
    data = response.json()
    assert data["failure_category"] == "AUTHENTICATION_FAILURE"
    assert data["segment_name"] == "authentication_failure_card_mid_new"
    assert "ranked_strategies" in data

def test_api_compare_strategies_invalid_category_400():
    response = client.get("/api/strategies/compare?failure_category=INVALID_CAT")
    assert response.status_code == 400

def test_api_segment_detail_404():
    response = client.get("/api/strategies/segment/invalid_id_999")
    assert response.status_code == 404
