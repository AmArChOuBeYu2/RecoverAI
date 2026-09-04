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
