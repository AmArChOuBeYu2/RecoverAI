"""
Unit and Integration Test Suite for Milestone 17 — Orchestrator (Main Agent Loop)
Validates batch run creation, full end-to-end pipeline execution, idempotency,
terminal case skipping, per-case fault tolerance, and batch metric reporting.
"""

import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

import backend.models  # noqa: F401
from backend.database.session import Base
from backend.models.customer import Customer
from backend.models.transaction import Transaction
from backend.models.recovery_case import RecoveryCase
from backend.models.batch_run import BatchRun
from backend.models.enums import TransactionStatus, FailureCategory, RecoveryCaseStatus
from backend.services.orchestrator import OrchestratorService

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=test_engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(autouse=True)
def mock_razorpay_for_orchestrator_tests():
    """Ensure orchestrator unit tests don't hit external Razorpay API rate limits."""
    from unittest.mock import patch, MagicMock
    from backend.integrations.razorpay import RazorpayPaymentLinkResponse
    with patch("backend.services.executor.RazorpayPaymentLinkService") as mock_cls:
        mock_inst = MagicMock()
        mock_inst.create_payment_link.side_effect = lambda req: RazorpayPaymentLinkResponse(
            id=f"plink_orch_{uuid.uuid4().hex[:8]}",
            amount=req.amount_paise,
            currency="INR",
            status="created",
            short_url="https://rzp.io/i/orch_test",
            reference_id=req.reference_id,
            created_at=int(datetime.now(timezone.utc).timestamp()),
        )
        mock_cls.return_value = mock_inst
        yield mock_inst

@pytest.fixture
def db_session():
    """Clean in-memory DB session for orchestrator testing."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

def create_sample_failed_transactions(db_session: Session, count: int = 5) -> List[Transaction]:
    """Helper to populate sample failed transactions."""
    cust = Customer(name="Orchestrator Test User", email=f"orch_{uuid.uuid4().hex[:6]}@example.com")
    db_session.add(cust)
    db_session.flush()

    txns = []
    categories = [
        FailureCategory.AUTHENTICATION_FAILURE.value,
        FailureCategory.BANK_TIMEOUT.value,
        FailureCategory.INSUFFICIENT_FUNDS.value,
        FailureCategory.CHECKOUT_ABANDONMENT.value,
    ]
    for i in range(count):
        cat = categories[i % len(categories)]
        t = Transaction(
            razorpay_payment_id=f"pay_orch_{uuid.uuid4().hex[:8]}",
            customer_id=cust.id,
            amount_paise=150000 + (i * 20000), # ₹1,500 to ₹2,300
            currency="INR",
            status=TransactionStatus.FAILED.value,
            failure_category=cat,
            payment_method="card",
        )
        db_session.add(t)
        txns.append(t)
    db_session.flush()
    return txns


def test_orchestrator_run_batch_basic(db_session: Session):
    """Test standard batch run processing across failed transactions."""
    create_sample_failed_transactions(db_session, count=4)

    res = OrchestratorService.run_batch(db_session, batch_run_name="test_batch_1", limit=10)

    assert res["status"] == "COMPLETED"
    assert res["total_target_transactions"] == 4
    assert res["total_processed"] == 4
    assert res["error_count"] == 0
    assert len(res["case_summaries"]) == 4

    # Verify BatchRun record in DB
    batch_record = db_session.query(BatchRun).filter_by(id=res["batch_run_id"]).first()
    assert batch_record is not None
    assert batch_record.total_processed == 4
    assert batch_record.status == "COMPLETED"


def test_orchestrator_idempotency_terminal_cases(db_session: Session):
    """Test that running batch processing again skips cases already in terminal state."""
    create_sample_failed_transactions(db_session, count=3)

    # First run processes transactions
    res1 = OrchestratorService.run_batch(db_session, batch_run_name="run_1", limit=10)
    assert res1["total_processed"] == 3

    # Second run should detect terminal cases and skip re-execution
    res2 = OrchestratorService.run_batch(db_session, batch_run_name="run_2", limit=10)
    assert res2["total_processed"] == 3
    for case_sum in res2["case_summaries"]:
        assert case_sum.get("skipped") is True
        assert "terminal" in case_sum.get("reason", "").lower()


def test_orchestrator_unrecoverable_category_handling(db_session: Session):
    """Test that transactions with unrecoverable failure category transition to INELIGIBLE."""
    cust = Customer(name="Unrecoverable User", email="unrecov@example.com")
    db_session.add(cust)
    db_session.flush()

    t = Transaction(
        razorpay_payment_id=f"pay_unrecov_{uuid.uuid4().hex[:6]}",
        customer_id=cust.id,
        amount_paise=200000,
        currency="INR",
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.BUSINESS_ERROR.value,
        payment_method="card",
    )
    db_session.add(t)
    db_session.flush()

    res = OrchestratorService.run_batch(db_session, transaction_ids=[t.id])
    assert res["total_processed"] == 1
    summary = res["case_summaries"][0]
    assert summary["status"] == RecoveryCaseStatus.INELIGIBLE.value
    assert summary["skipped"] is True


def test_orchestrator_fault_tolerance_per_case_error(db_session: Session, monkeypatch):
    """Test that an exception in one case is caught, logged, and does not crash the batch run."""
    txns = create_sample_failed_transactions(db_session, count=3)

    # Monkeypatch EligibilityChecker to throw an error on the second transaction
    target_txn_id = txns[1].id
    orig_eval = OrchestratorService._process_single_transaction

    def mock_process(db, transaction, batch_run_id=None, force_reprocess=False):
        if transaction.id == target_txn_id:
            raise RuntimeError("Simulated processing crash on case")
        return orig_eval(db, transaction, batch_run_id, force_reprocess)

    monkeypatch.setattr(OrchestratorService, "_process_single_transaction", mock_process)

    res = OrchestratorService.run_batch(db_session, batch_run_name="fault_test_batch")

    assert res["status"] == "COMPLETED_WITH_ERRORS"
    assert res["total_processed"] == 3
    assert res["error_count"] == 1

    error_summaries = [c for c in res["case_summaries"] if c.get("status") == "ERROR"]
    assert len(error_summaries) == 1
    assert error_summaries[0]["transaction_id"] == target_txn_id


def test_orchestrator_process_single_case(db_session: Session):
    """Test processing a specific single RecoveryCase end-to-end via process_single_case."""
    txns = create_sample_failed_transactions(db_session, count=1)
    txn = txns[0]

    # Create RecoveryCase
    case = RecoveryCase(transaction_id=txn.id, customer_id=txn.customer_id, status=RecoveryCaseStatus.DETECTED.value)
    db_session.add(case)
    db_session.flush()

    res = OrchestratorService.process_single_case(db_session, case_id=case.id)

    assert res["case_id"] == case.id
    assert res["transaction_id"] == txn.id
    assert res["executed"] is True
    assert "verification_status" in res


def test_payment_link_lifecycle_leaves_awaiting_verification(db_session: Session):
    """REGRESSION: Payment Link creation must leave case in AWAITING_VERIFICATION (not RECOVERED or UNRECOVERED)."""
    from unittest.mock import MagicMock
    from backend.models.enums import OutcomeSource
    from backend.integrations.razorpay.schemas import RazorpayPaymentLinkResponse
    from backend.services.executor import ActionExecutor

    txns = create_sample_failed_transactions(db_session, count=1)
    txn = txns[0]

    # Mock Razorpay API returning status='created' (unpaid payment link)
    mock_service = MagicMock()
    mock_service.fetch_payment_link.return_value = RazorpayPaymentLinkResponse(
        id="plink_unpaid_test",
        amount=txn.amount_paise,
        currency="INR",
        status="created",
        short_url="https://rzp.io/i/unpaid_test",
        created_at=int(datetime.now(timezone.utc).timestamp()),
    )
    mock_service.create_payment_link.return_value = RazorpayPaymentLinkResponse(
        id="plink_unpaid_test",
        amount=txn.amount_paise,
        currency="INR",
        status="created",
        short_url="https://rzp.io/i/unpaid_test",
        created_at=int(datetime.now(timezone.utc).timestamp()),
    )

    with pytest.MonkeyPatch.context() as mp:
        from backend.services.verification import VerificationService
        mp.setattr(VerificationService, "__init__", lambda self, payment_link_service=None: setattr(self, "payment_link_service", mock_service))
        mp.setattr(ActionExecutor, "__init__", lambda self, payment_link_service=None: setattr(self, "payment_link_service", mock_service))
        mp.setattr(ActionExecutor, "determine_execution_mode", lambda self, db, action_type: ("REAL_TEST_MODE", "RAZORPAY_TEST"))

        res = OrchestratorService.run_batch(db_session, transaction_ids=[txn.id])

    summary = res["case_summaries"][0]
    case = db_session.query(RecoveryCase).filter_by(id=summary["case_id"]).first()

    assert case.status == RecoveryCaseStatus.AWAITING_VERIFICATION.value
    assert case.is_terminal is False
    assert summary["recovered"] is False
    assert summary["amount_recovered_paise"] == 0
    assert res["success_count"] == 0
    assert res["total_recovered_paise"] == 0


def test_force_reprocess_safety_invariants(db_session: Session):
    """REGRESSION: force_reprocess=True MUST NOT rerun RECOVERED or UNRECOVERED terminal cases."""
    txns = create_sample_failed_transactions(db_session, count=2)

    case1 = RecoveryCase(transaction_id=txns[0].id, customer_id=txns[0].customer_id, status=RecoveryCaseStatus.RECOVERED.value, is_terminal=True)
    case2 = RecoveryCase(transaction_id=txns[1].id, customer_id=txns[1].customer_id, status=RecoveryCaseStatus.UNRECOVERED.value, is_terminal=True)
    db_session.add_all([case1, case2])
    db_session.flush()

    res = OrchestratorService.run_batch(db_session, transaction_ids=[txns[0].id, txns[1].id], force_reprocess=True)

    assert res["total_processed"] == 2
    for sum_item in res["case_summaries"]:
        assert sum_item.get("skipped") is True
        assert "terminal state" in sum_item.get("reason", "").lower()

    # Verify states remain untouched
    assert case1.status == RecoveryCaseStatus.RECOVERED.value
    assert case2.status == RecoveryCaseStatus.UNRECOVERED.value


def test_single_policy_decision_per_intent(db_session: Session):
    """REGRESSION: Exactly one PolicyDecision DB record must be created per execution intent."""
    from backend.models.policy_decision import PolicyDecision

    txns = create_sample_failed_transactions(db_session, count=1)
    res = OrchestratorService.run_batch(db_session, transaction_ids=[txns[0].id])

    case_id = res["case_summaries"][0]["case_id"]
    decisions = db_session.query(PolicyDecision).filter_by(recovery_case_id=case_id).all()

    assert len(decisions) == 1


def test_per_case_transaction_isolation_savepoint(db_session: Session, monkeypatch):
    """REGRESSION: Exception in Case A rolls back to savepoint and does not poison Case B's session."""
    txns = create_sample_failed_transactions(db_session, count=2)

    orig_process = OrchestratorService._process_single_transaction
    fail_first = True

    def mock_process_fail_first(db, transaction, batch_run_id=None, force_reprocess=False):
        nonlocal fail_first
        if transaction.id == txns[0].id and fail_first:
            # Simulate partial DB work followed by a crash
            db.add(RecoveryCase(transaction_id=transaction.id, customer_id=transaction.customer_id, status="TEST_CRASH"))
            db.flush()
            raise RuntimeError("Database flush error simulation on Case A")
        return orig_process(db, transaction, batch_run_id, force_reprocess)

    monkeypatch.setattr(OrchestratorService, "_process_single_transaction", mock_process_fail_first)

    res = OrchestratorService.run_batch(db_session, transaction_ids=[txns[0].id, txns[1].id])

    assert res["status"] == "COMPLETED_WITH_ERRORS"
    assert res["total_processed"] == 2
    assert res["error_count"] == 1

    sum0 = next(s for s in res["case_summaries"] if s["transaction_id"] == txns[0].id)
    sum1 = next(s for s in res["case_summaries"] if s["transaction_id"] == txns[1].id)

    assert sum0["status"] == "ERROR"
    assert sum1["executed"] is True


def test_batch_success_and_revenue_semantics(db_session: Session):
    """REGRESSION: success_count and total_recovered_paise count ONLY authoritative VERIFIED recoveries."""
    txns = create_sample_failed_transactions(db_session, count=1)
    txn = txns[0]

    res = OrchestratorService.run_batch(db_session, transaction_ids=[txn.id])

    # Default simulated/creation actions do NOT count as authoritative recovered revenue
    assert res["success_count"] == 0
    assert res["total_recovered_paise"] == 0


def test_interrupted_batch_resume_idempotency(db_session: Session):
    """REGRESSION: Interrupted batch resume skips RECOVERED, reuses active RecoveryAction, and processes new case."""
    from backend.models.recovery_action import RecoveryAction
    from backend.models.strategy_outcome import StrategyOutcome

    txns = create_sample_failed_transactions(db_session, count=3)

    # Case A is RECOVERED
    case_a = RecoveryCase(transaction_id=txns[0].id, customer_id=txns[0].customer_id, status=RecoveryCaseStatus.RECOVERED.value, is_terminal=True)
    db_session.add(case_a)

    # Case B has active RecoveryAction in AWAITING_VERIFICATION
    case_b = RecoveryCase(transaction_id=txns[1].id, customer_id=txns[1].customer_id, status=RecoveryCaseStatus.AWAITING_VERIFICATION.value)
    db_session.add(case_b)
    db_session.flush()

    action_b = RecoveryAction(recovery_case_id=case_b.id, action_type="PAYMENT_LINK", execution_mode="SIMULATED", status="SENT")
    db_session.add(action_b)
    db_session.flush()

    # Case C is unprocessed (no case record yet)

    res = OrchestratorService.run_batch(db_session, transaction_ids=[t.id for t in txns])

    assert res["total_processed"] == 3

    # Case A skipped
    sum_a = next(s for s in res["case_summaries"] if s["transaction_id"] == txns[0].id)
    assert sum_a.get("skipped") is True

    # Case B did not create duplicate action
    actions_b = db_session.query(RecoveryAction).filter_by(recovery_case_id=case_b.id).all()
    assert len(actions_b) == 1

    # Case C processed
    sum_c = next(s for s in res["case_summaries"] if s["transaction_id"] == txns[2].id)
    assert sum_c["executed"] is True

