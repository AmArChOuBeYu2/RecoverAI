"""
Automated Test Suite for API Routes — RecoverAI Milestone 20
Tests FastAPI REST endpoints across health, dashboard, transactions, recovery, segments,
strategies, simulator, audit, batch, intelligence, and error handling middleware.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.database.session import Base, get_db
from backend.models.customer import Customer
from backend.models.transaction import Transaction
from backend.models.recovery_case import RecoveryCase
from backend.models.enums import TransactionStatus, FailureCategory, RecoveryCaseStatus
from backend.services.segmentation import SegmentationService
from backend.services.audit import AuditService, EVENT_TYPE_DETECTED, ACTOR_SYSTEM

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=test_engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield

@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()

def seed_sample_case(session: Session):
    from backend.seed.generator import seed_default_segments
    seed_default_segments(session)

    cust = Customer(name="API Test User", email=f"api_{uuid.uuid4().hex[:6]}@example.com")
    session.add(cust)
    session.flush()

    txn = Transaction(
        razorpay_payment_id=f"pay_api_{uuid.uuid4().hex[:6]}",
        customer_id=cust.id,
        amount_paise=150000,
        currency="INR",
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.AUTHENTICATION_FAILURE.value,
        payment_method="card",
    )
    session.add(txn)
    session.flush()

    segment = SegmentationService.get_or_create_segment(
        db=session,
        failure_category=FailureCategory.AUTHENTICATION_FAILURE.value,
        payment_method="card",
        amount_range_or_paise=150000,
        customer_type="NEW",
    )
    session.flush()

    case = RecoveryCase(
        transaction_id=txn.id,
        customer_id=cust.id,
        segment_id=segment.id,
        status=RecoveryCaseStatus.DETECTED.value,
    )
    session.add(case)
    session.flush()

    AuditService.log_event(
        db=session,
        event_type=EVENT_TYPE_DETECTED,
        description="API test case created",
        recovery_case_id=case.id,
        actor=ACTOR_SYSTEM,
    )
    session.commit()
    return case.id, txn.id, segment.id

def test_health_endpoint(db_session: Session):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "components" in data
    assert data["components"]["database"] == "healthy"

def test_dashboard_summary_endpoint(db_session: Session):
    seed_sample_case(db_session)
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert "total_transaction_count" in data
    assert "total_revenue_at_risk_paise" in data

def test_dashboard_failure_breakdown_endpoint(db_session: Session):
    seed_sample_case(db_session)
    res = client.get("/api/dashboard/failure-breakdown")
    assert res.status_code == 200
    data = res.json()
    assert "breakdown_by_failure_category" in data

def test_transactions_endpoints(db_session: Session):
    _, txn_id, _ = seed_sample_case(db_session)
    
    # List transactions
    res = client.get("/api/transactions")
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] >= 1
    assert len(data["transactions"]) >= 1

    # Single transaction detail
    res_detail = client.get(f"/api/transactions/{txn_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["id"] == txn_id
    assert detail["amount_paise"] == 150000

    # 404 for missing transaction
    res_404 = client.get("/api/transactions/non_existent_id_999")
    assert res_404.status_code == 404

def test_recovery_endpoints(db_session: Session):
    case_id, _, _ = seed_sample_case(db_session)

    # List cases
    res = client.get("/api/recovery/cases")
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] >= 1

    # Get case detail context
    res_detail = client.get(f"/api/recovery/cases/{case_id}")
    assert res_detail.status_code == 200

    # Detect endpoint
    res_detect = client.post("/api/recovery/detect?limit=10")
    assert res_detect.status_code == 200

    # Run batch endpoint
    res_run = client.post("/api/recovery/run?limit=10")
    assert res_run.status_code == 200
    assert "batch_run_id" in res_run.json()

def test_segments_endpoints(db_session: Session):
    _, _, segment_id = seed_sample_case(db_session)

    # List segments
    res = client.get("/api/segments")
    assert res.status_code == 200
    assert res.json()["total_count"] >= 1

    # Segment detail
    res_detail = client.get(f"/api/segments/{segment_id}")
    assert res_detail.status_code == 200

    # Lookup segment
    res_lookup = client.get("/api/segments/lookup?failure_category=AUTHENTICATION_FAILURE&payment_method=card&amount_range=MID")
    assert res_lookup.status_code == 200
    assert res_lookup.json()["failure_category"] == "AUTHENTICATION_FAILURE"

def test_strategies_endpoints(db_session: Session):
    _, _, segment_id = seed_sample_case(db_session)

    # List strategy performance
    res = client.get("/api/strategies")
    assert res.status_code == 200

    # Compare candidate strategies
    res_comp = client.get("/api/strategies/compare?failure_category=AUTHENTICATION_FAILURE&payment_method=card&amount_range=MID")
    assert res_comp.status_code == 200

    # Segment strategy performance
    res_seg = client.get(f"/api/strategies/segment/{segment_id}")
    assert res_seg.status_code == 200

def test_simulator_endpoints(db_session: Session):
    seed_sample_case(db_session)

    # Run simulation
    res_run = client.post("/api/simulator/run?limit=50")
    assert res_run.status_code == 200
    data = res_run.json()
    assert "baseline" in data
    assert "recoverai_optimized" in data

    # Results list
    res_list = client.get("/api/simulator/results")
    assert res_list.status_code == 200

    # Compare
    res_comp = client.get("/api/simulator/compare?limit=50")
    assert res_comp.status_code == 200

def test_audit_endpoints(db_session: Session):
    case_id, _, _ = seed_sample_case(db_session)

    # Query events
    res_events = client.get("/api/audit/events")
    assert res_events.status_code == 200
    assert res_events.json()["count"] >= 1

    # Events for specific case
    res_case_events = client.get(f"/api/audit/events/{case_id}")
    assert res_case_events.status_code == 200

    # Case timeline
    res_timeline = client.get(f"/api/audit/timeline/{case_id}")
    assert res_timeline.status_code == 200
    assert res_timeline.json()["case_id"] == case_id

def test_batch_endpoints(db_session: Session):
    seed_sample_case(db_session)
    res_run = client.post("/api/recovery/run?limit=10")
    assert res_run.status_code == 200

    # List batch runs
    res_runs = client.get("/api/batch/runs")
    assert res_runs.status_code == 200
    data = res_runs.json()
    assert data["total_count"] >= 1

    run_id = data["runs"][0]["id"]
    res_detail = client.get(f"/api/batch/runs/{run_id}")
    assert res_detail.status_code == 200
    assert res_detail.json()["id"] == run_id

def test_recovery_seed_endpoint(db_session: Session):
    res = client.post("/api/recovery/seed?count=15")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "seeded"
    assert data["transactions_created"] > 0

def test_cors_middleware_headers():
    """Verify CORS middleware headers allow wildcard origin for cross-origin browser requests when allow_credentials=False."""
    res = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "*"

def test_health_privacy_no_credential_leakage():
    """Verify GET /api/health does not reveal secret environment strings or API keys."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    res_str = str(data)
    assert "sk_" not in res_str
    assert "secret_" not in res_str
    assert "key_secret" not in res_str

def test_integer_paise_monetary_contract(db_session: Session):
    """Verify financial API endpoints return integer paise amounts and derived rupee floats."""
    seed_sample_case(db_session)
    res = client.get("/api/transactions")
    assert res.status_code == 200
    tx = res.json()["transactions"][0]
    assert isinstance(tx["amount_paise"], int)
    assert isinstance(tx["amount_rupees"], float)
    assert tx["amount_paise"] == 150000
    assert tx["amount_rupees"] == 1500.00

