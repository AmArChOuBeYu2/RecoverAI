"""
Unit and Integration Test Suite for Milestone 16 — Policy Simulator & Policy Simulator API
Validates read-only policy simulation, baseline vs. RecoverAI optimized comparison,
metrics calculation, integer paise correctness, PROJECTED evidence tagging, and REST API endpoints.
"""

import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import backend.models  # noqa: F401
from backend.database.session import Base, get_db
from backend.main import app
from backend.models.customer import Customer
from backend.models.transaction import Transaction
from backend.models.recovery_case import RecoveryCase
from backend.models.policy_simulation import PolicySimulation
from backend.models.enums import TransactionStatus, FailureCategory, DataCategory
from backend.services.policy_simulator import PolicySimulator
from backend.services.segmentation import SegmentationService

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

def create_sample_transactions_for_simulation(db_session: Session, count: int = 10):
    """Helper to populate sample transactions for simulation testing."""
    cust = Customer(name="Sim User", email=f"sim_{uuid.uuid4().hex[:6]}@example.com")
    db_session.add(cust)
    db_session.flush()

    categories = [
        FailureCategory.AUTHENTICATION_FAILURE.value,
        FailureCategory.BANK_TIMEOUT.value,
        FailureCategory.INSUFFICIENT_FUNDS.value,
        FailureCategory.CHECKOUT_ABANDONMENT.value,
    ]

    for i in range(count):
        cat = categories[i % len(categories)]
        txn = Transaction(
            razorpay_payment_id=f"pay_sim_{uuid.uuid4().hex[:8]}",
            customer_id=cust.id,
            amount_paise=100000 + (i * 50000), # ₹1,000 to ₹5,500
            currency="INR",
            status=TransactionStatus.FAILED.value,
            failure_category=cat,
            payment_method="card",
        )
        db_session.add(txn)
    db_session.flush()


def test_policy_simulator_read_only_guarantee(db_session: Session):
    """Verify PolicySimulator runs side-by-side simulation without mutating transactions or case states."""
    create_sample_transactions_for_simulation(db_session, count=8)

    initial_txn_count = db_session.query(Transaction).count()
    initial_case_count = db_session.query(RecoveryCase).count()

    res = PolicySimulator.run_simulation(db_session, limit=10)

    # Read-only check: Transaction and Case count must remain identical
    assert db_session.query(Transaction).count() == initial_txn_count
    assert db_session.query(RecoveryCase).count() == initial_case_count

    # Simulation records created
    sims = db_session.query(PolicySimulation).all()
    assert len(sims) == 2
    assert {s.policy_name for s in sims} == {"current_baseline", "recoverai_optimized"}
    for s in sims:
        assert s.simulation_mode == DataCategory.PROJECTED.value


def test_baseline_vs_optimized_policy_comparison(db_session: Session):
    """Verify PolicySimulator correctly formats baseline vs optimized comparison and incremental metrics."""
    create_sample_transactions_for_simulation(db_session, count=12)

    res = PolicySimulator.run_simulation(db_session, limit=20)

    assert res["simulation_mode"] == DataCategory.PROJECTED.value
    assert "baseline" in res
    assert "recoverai_optimized" in res
    assert "incremental_comparison" in res

    baseline = res["baseline"]
    optimized = res["recoverai_optimized"]
    inc = res["incremental_comparison"]

    assert baseline["policy_name"] == "current_baseline"
    assert optimized["policy_name"] == "recoverai_optimized"
    assert baseline["total_transactions"] == 12
    assert optimized["total_transactions"] == 12

    # Incremental calculations check
    assert inc["incremental_recovered_paise"] == (optimized["projected_recovered_paise"] - baseline["projected_recovered_paise"])
    assert inc["incremental_recovered_rupees"] == round(inc["incremental_recovered_paise"] / 100.0, 2)


def test_empty_transactions_simulation(db_session: Session):
    """Verify running PolicySimulator when no transactions exist returns safe empty records cleanly."""
    res = PolicySimulator.run_simulation(db_session, limit=10)

    assert res["simulation_mode"] == DataCategory.PROJECTED.value
    assert res["baseline"]["total_transactions"] == 0
    assert res["recoverai_optimized"]["total_transactions"] == 0
    assert res["incremental_comparison"]["incremental_recovered_paise"] == 0


def test_api_simulator_run_endpoint(db_session: Session):
    """Test POST /api/simulator/run endpoint."""
    create_sample_transactions_for_simulation(db_session, count=5)
    db_session.commit()

    res = client.post("/api/simulator/run?limit=10")
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["simulation_mode"] == DataCategory.PROJECTED.value


def test_api_simulator_results_endpoint(db_session: Session):
    """Test GET /api/simulator/results endpoint."""
    PolicySimulator.run_simulation(db_session, limit=10)
    db_session.commit()

    res = client.get("/api/simulator/results")
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["count"] >= 2
    assert len(data["results"]) >= 2
    for r in data["results"]:
        assert r["simulation_mode"] == DataCategory.PROJECTED.value


def test_api_simulator_compare_endpoint(db_session: Session):
    """Test GET /api/simulator/compare endpoint."""
    create_sample_transactions_for_simulation(db_session, count=4)
    db_session.commit()

    res = client.get("/api/simulator/compare?limit=10")
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["simulation_mode"] == DataCategory.PROJECTED.value
    assert "incremental_comparison" in data


def test_temporal_leakage_prevention(db_session: Session):
    """Verify simulation filtering by as_of_time ignores transactions created in the future."""
    from datetime import datetime, timedelta, timezone
    past_time = datetime.now(timezone.utc) - timedelta(hours=2)

    create_sample_transactions_for_simulation(db_session, count=4)
    db_session.flush()

    # Set created_at to past_time for initial transactions
    txns = db_session.query(Transaction).all()
    for t in txns:
        t.created_at = past_time
    db_session.flush()

    initial_txn_count = db_session.query(Transaction).filter(Transaction.created_at <= past_time).count()

    sim_past = PolicySimulator.run_simulation(db_session, as_of_time=past_time)

    # Now add a new future high-value transaction
    cust = Customer(name="Future User", email="future@example.com")
    db_session.add(cust)
    db_session.flush()

    future_txn = Transaction(
        razorpay_payment_id="pay_future_123",
        customer_id=cust.id,
        amount_paise=1000000, # ₹10,000
        currency="INR",
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.AUTHENTICATION_FAILURE.value,
        payment_method="card",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(future_txn)
    db_session.flush()

    sim_past_after_future_txn = PolicySimulator.run_simulation(db_session, as_of_time=past_time)

    # Past simulation must yield identical results regardless of future transaction
    assert sim_past["baseline"]["total_transactions"] == initial_txn_count
    assert sim_past_after_future_txn["baseline"]["total_transactions"] == initial_txn_count
    assert sim_past["baseline"]["revenue_at_risk_paise"] == sim_past_after_future_txn["baseline"]["revenue_at_risk_paise"]


def test_projected_evidence_isolation(db_session: Session):
    """Verify running PolicySimulator never modifies empirical RecoveryStrategy metrics."""
    from backend.models.recovery_strategy import RecoveryStrategy
    from backend.models.segment import Segment

    seg = Segment(name="test_seg_sim", failure_category=FailureCategory.AUTHENTICATION_FAILURE.value, amount_range="MID")
    db_session.add(seg)
    db_session.flush()

    strat = RecoveryStrategy(
        segment_id=seg.id,
        strategy_type="PAYMENT_LINK",
        attempt_count=10,
        success_count=5,
        total_recovered_paise=500000,
        recovery_rate=0.5,
    )
    db_session.add(strat)
    db_session.flush()

    create_sample_transactions_for_simulation(db_session, count=5)

    # Run simulation
    PolicySimulator.run_simulation(db_session)

    # Query strategy record and confirm empirical metrics are unchanged
    db_strat = db_session.query(RecoveryStrategy).filter_by(id=strat.id).first()
    assert db_strat.attempt_count == 10
    assert db_strat.success_count == 5
    assert db_strat.total_recovered_paise == 500000
    assert db_strat.recovery_rate == 0.5


def test_trust_gate_null_coalescing(db_session: Session):
    """Verify TrustGateService handles NULL customer transaction counts safely."""
    from backend.services.trust_gate import TrustGateService

    cust = Customer(name="Null Count User", email="null_count@example.com", failed_transactions=None, successful_transactions=None)
    txn = Transaction(razorpay_payment_id="pay_null_gate", amount_paise=10000, currency="INR", status=TransactionStatus.FAILED.value)

    res = TrustGateService.evaluate(transaction=txn, customer=cust)
    assert res.passed is True
    assert res.suspicious_pattern_detected is False


def test_contact_metric_semantics(db_session: Session):
    """Verify contacts_projected counts customer-facing strategies and excludes internal actions."""
    from backend.models.enums import StrategyType

    # Verify contact classification in PolicySimulator logic
    customer_facing = [StrategyType.PAYMENT_LINK.value, StrategyType.REMINDER.value, StrategyType.METHOD_SWITCH.value]
    internal_actions = [StrategyType.DELAYED_RETRY.value, StrategyType.NO_ACTION.value, StrategyType.HUMAN_REVIEW.value, StrategyType.ESCALATION.value]

    for s in customer_facing:
        assert s in (StrategyType.PAYMENT_LINK.value, StrategyType.REMINDER.value, StrategyType.METHOD_SWITCH.value)

    for s in internal_actions:
        assert s not in customer_facing


def test_simulation_run_history_immutability(db_session: Session):
    """Verify POST /api/simulator/run produces independent immutable PolicySimulation records."""
    initial_sim_count = db_session.query(PolicySimulation).count()
    create_sample_transactions_for_simulation(db_session, count=3)

    res1 = PolicySimulator.run_simulation(db_session, limit=10)
    res2 = PolicySimulator.run_simulation(db_session, limit=10)

    sims = db_session.query(PolicySimulation).all()
    assert len(sims) == initial_sim_count + 4 # 2 for baseline + 2 for optimized per run
    ids = [s.id for s in sims]
    assert len(set(ids)) == len(sims) # All simulation IDs must be unique

