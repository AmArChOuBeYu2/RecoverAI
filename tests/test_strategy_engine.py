"""
Unit and Integration Test Suite for Milestone 12 — AI Diagnosis & Strategy Engine
Validates DiagnosisService, abandoned checkout detection, StrategyEngine synthesis rules,
RecoveryDecision persistence, decision idempotency, state transitions, and REST API endpoints.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

import backend.models  # noqa: F401 - Register models
from backend.database.session import Base, get_db
from backend.main import app
from backend.services.detection import DetectionEngine
from backend.services.context_builder import ContextBuilder
from backend.services.eligibility import EligibilityChecker
from backend.services.segmentation import SegmentationService
from backend.services.diagnosis import DiagnosisService
from backend.services.strategy_engine import StrategyEngine
from backend.models.recovery_case import RecoveryCase
from backend.models.transaction import Transaction
from backend.models.customer import Customer
from backend.models.recovery_decision import RecoveryDecision
from backend.models.strategy_outcome import StrategyOutcome
from backend.models.audit_event import AuditEvent
from backend.models.enums import (
    FailureCategory,
    RecoveryCaseStatus,
    TransactionStatus,
    StrategyType,
    DataCategory,
)
from backend.integrations.llm.router import LLMRouter
from backend.integrations.llm.deterministic_provider import DeterministicFallbackProvider
from backend.integrations.llm.schemas import RecoveryDiagnosis
from backend.integrations.llm.base import LLMProvider

# Setup test DB engine with StaticPool
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

# Mock LLM Provider for controlled strategy recommendations
class CustomMockLLMProvider(LLMProvider):
    def __init__(self, recommended_strategy: str = "PAYMENT_LINK", failure_category: str = "AUTHENTICATION_FAILURE"):
        self._strat = recommended_strategy
        self._cat = failure_category

    @property
    def name(self) -> str:
        return "mock_ai"

    @property
    def model_name(self) -> str:
        return "mock-ai-v1"

    def diagnose(self, context: dict) -> tuple:
        diag = RecoveryDiagnosis(
            failure_category=self._cat,
            diagnosis="Mock LLM diagnosis explanation",
            recoverability_score=0.85,
            confidence=0.90,
            recommended_strategy=self._strat,
            reasoning_summary="Mock reasoning summary",
        )
        metadata = {"latency_ms": 50, "prompt_tokens": 10, "completion_tokens": 5}
        return diag, metadata

# -----------------------------------------------------------------------------
# 1. DiagnosisService Tests
# -----------------------------------------------------------------------------

def test_diagnosis_service_execution(db_session: Session):
    """Verify DiagnosisService builds context, calls LLMRouter, updates score, and logs CASE_DIAGNOSED."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    cust = Customer(email="diag_user@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_diag_1", customer_id=cust.id, amount_paise=200000, status="FAILED", failure_category="AUTHENTICATION_FAILURE", created_at=now)
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.DETECTED.value, attempt_count=0)
    db_session.add(case)
    db_session.flush()

    SegmentationService.assign_segment_to_case(db_session, case)

    mock_router = LLMRouter(providers=[CustomMockLLMProvider("PAYMENT_LINK")])
    diag, ctx = DiagnosisService.diagnose_case(db_session, case, router=mock_router, as_of_time=now)

    assert diag.recommended_strategy == "PAYMENT_LINK"
    assert case.recoverability_score == 0.85

    audit = db_session.query(AuditEvent).filter_by(recovery_case_id=case.id, event_type="CASE_DIAGNOSED").first()
    assert audit is not None
    assert audit.details["ai_recommended_strategy"] == "PAYMENT_LINK"

# -----------------------------------------------------------------------------
# 2. Abandoned Checkout Detection Tests
# -----------------------------------------------------------------------------

def test_abandoned_checkout_detection_age_boundaries(db_session: Session):
    """Verify abandoned checkout detection logic for >15m (detected), <=15m (not detected)."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    cust = Customer(email="ac_user@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    # Txn 1: Created 20m ago (should be detected)
    txn_20m = Transaction(razorpay_order_id="order_20m", customer_id=cust.id, amount_paise=100000, status=TransactionStatus.CREATED.value, failure_category="UNKNOWN", created_at=now - timedelta(minutes=20))
    # Txn 2: Created 10m ago (should NOT be detected)
    txn_10m = Transaction(razorpay_order_id="order_10m", customer_id=cust.id, amount_paise=100000, status=TransactionStatus.CREATED.value, failure_category="UNKNOWN", created_at=now - timedelta(minutes=10))

    db_session.add_all([txn_20m, txn_10m])
    db_session.flush()

    cases = DetectionEngine.detect_abandoned_checkouts(db_session, min_age_minutes=15, as_of_time=now)

    assert len(cases) == 1
    detected_case = cases[0]
    assert detected_case.transaction_id == txn_20m.id
    assert detected_case.status == RecoveryCaseStatus.SEGMENTED.value
    assert txn_20m.failure_category == FailureCategory.CHECKOUT_ABANDONMENT.value

    # Verify audit event with inferred_condition=True
    audit = db_session.query(AuditEvent).filter_by(recovery_case_id=detected_case.id, event_type="ABANDONED_CHECKOUT_DETECTED").first()
    assert audit is not None
    assert audit.details["inferred_condition"] is True

def test_abandoned_checkout_idempotency(db_session: Session):
    """Verify repeat abandoned checkout detection scans do not duplicate cases."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    cust = Customer(email="ac_idemp@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_order_id="order_idemp", customer_id=cust.id, amount_paise=100000, status=TransactionStatus.CREATED.value, created_at=now - timedelta(minutes=30))
    db_session.add(txn)
    db_session.flush()

    cases_run_1 = DetectionEngine.detect_abandoned_checkouts(db_session, min_age_minutes=15, as_of_time=now)
    assert len(cases_run_1) == 1

    cases_run_2 = DetectionEngine.detect_abandoned_checkouts(db_session, min_age_minutes=15, as_of_time=now)
    assert len(cases_run_2) == 0

# -----------------------------------------------------------------------------
# 3. Strategy Engine Synthesis & Evidence Tests
# -----------------------------------------------------------------------------

def test_synthesis_sufficient_sample_empirical_override(db_session: Session):
    """Verify that sufficient empirical sample size (>=10) overrides a conflicting AI recommendation."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    cust = Customer(email="override_user@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_override", customer_id=cust.id, amount_paise=150000, status="FAILED", failure_category="AUTHENTICATION_FAILURE", payment_method="card", created_at=now)
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.DETECTED.value, attempt_count=0)
    db_session.add(case)
    db_session.flush()
    SegmentationService.assign_segment_to_case(db_session, case)
    EligibilityChecker.evaluate_eligibility(db_session, case, as_of_time=now)
    assert case.status == RecoveryCaseStatus.ELIGIBLE.value

    # Seed 15 historical outcomes for DELAYED_RETRY with high recovery rate (12/15 = 80%)
    for i in range(15):
        outcome_status = "RECOVERED" if i < 12 else "UNRECOVERED"
        so = StrategyOutcome(
            recovery_case_id=case.id,
            strategy_type="DELAYED_RETRY",
            segment_id=case.segment_id,
            outcome=outcome_status,
            amount_recovered_paise=150000 if outcome_status == "RECOVERED" else 0,
            outcome_source="TEST_MODE_VERIFIED",
        )
        db_session.add(so)
    db_session.flush()

    # AI recommends PAYMENT_LINK, but empirical evidence strongly supports DELAYED_RETRY (>= 10 sample size)
    mock_router = LLMRouter(providers=[CustomMockLLMProvider("PAYMENT_LINK")])
    decision = StrategyEngine.evaluate_case_strategies(db_session, case, as_of_time=now, router=mock_router)

    assert decision.selected_strategy == "DELAYED_RETRY"
    assert decision.ai_recommended_strategy == "PAYMENT_LINK"
    assert "EMPIRICAL_OVERRIDE" in decision.reasoning_summary
    assert case.status == RecoveryCaseStatus.STRATEGIES_EVALUATED.value

def test_synthesis_insufficient_sample_ai_guided(db_session: Session):
    """Verify that insufficient sample size (<10) adopts valid AI recommendation."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    cust = Customer(email="ai_guided@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_ai_guided", customer_id=cust.id, amount_paise=150000, status="FAILED", failure_category="AUTHENTICATION_FAILURE", payment_method="card", created_at=now)
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.DETECTED.value, attempt_count=0)
    db_session.add(case)
    db_session.flush()
    SegmentationService.assign_segment_to_case(db_session, case)
    EligibilityChecker.evaluate_eligibility(db_session, case, as_of_time=now)

    # Only 2 historical outcomes (insufficient sample < 10)
    for i in range(2):
        so = StrategyOutcome(recovery_case_id=case.id, strategy_type="METHOD_SWITCH", segment_id=case.segment_id, outcome="RECOVERED", amount_recovered_paise=150000, outcome_source="SIMULATED")
        db_session.add(so)
    db_session.flush()

    mock_router = LLMRouter(providers=[CustomMockLLMProvider("PAYMENT_LINK")])
    decision = StrategyEngine.evaluate_case_strategies(db_session, case, as_of_time=now, router=mock_router)

    assert decision.selected_strategy == "PAYMENT_LINK"
    assert "AI_GUIDED_LOW_SAMPLE" in decision.reasoning_summary

# -----------------------------------------------------------------------------
# 4. Decision Idempotency Tests
# -----------------------------------------------------------------------------

def test_decision_idempotency(db_session: Session):
    """Verify repeated strategy evaluation on an evaluated case returns existing decision."""
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    cust = Customer(email="idemp_dec@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_idemp_dec", customer_id=cust.id, amount_paise=100000, status="FAILED", failure_category="AUTHENTICATION_FAILURE", created_at=now)
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.DETECTED.value, attempt_count=0)
    db_session.add(case)
    db_session.flush()
    SegmentationService.assign_segment_to_case(db_session, case)
    EligibilityChecker.evaluate_eligibility(db_session, case, as_of_time=now)

    mock_router = LLMRouter(providers=[CustomMockLLMProvider("PAYMENT_LINK")])
    dec_1 = StrategyEngine.evaluate_case_strategies(db_session, case, as_of_time=now, router=mock_router)

    # Second evaluation call without force_reevaluate
    dec_2 = StrategyEngine.evaluate_case_strategies(db_session, case, as_of_time=now, router=mock_router)

    assert dec_1.id == dec_2.id
    total_decisions = db_session.query(RecoveryDecision).filter_by(recovery_case_id=case.id).count()
    assert total_decisions == 1

# -----------------------------------------------------------------------------
# 5. REST API Endpoint Tests
# -----------------------------------------------------------------------------

def test_api_recovery_evaluate(db_session: Session):
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    cust = Customer(email="api_eval@example.com", customer_type="NEW")
    db_session.add(cust)
    db_session.flush()

    txn = Transaction(razorpay_payment_id="pay_api_eval", customer_id=cust.id, amount_paise=100000, status="FAILED", failure_category="AUTHENTICATION_FAILURE", created_at=now)
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(transaction_id=txn.id, customer_id=cust.id, status=RecoveryCaseStatus.DETECTED.value, attempt_count=0)
    db_session.add(case)
    db_session.flush()
    SegmentationService.assign_segment_to_case(db_session, case)
    EligibilityChecker.evaluate_eligibility(db_session, case, as_of_time=now)

    c_id = case.id
    response = client.post(f"/api/recovery/evaluate/{c_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == c_id
    assert data["status"] == "STRATEGIES_EVALUATED"
    assert "selected_strategy" in data
    assert "strategy_evidence" in data

    # Test GET decision endpoint
    dec_resp = client.get(f"/api/recovery/decisions/{c_id}")
    assert dec_resp.status_code == 200
    dec_data = dec_resp.json()
    assert dec_data["case_id"] == c_id
    assert dec_data["selected_strategy"] == data["selected_strategy"]
