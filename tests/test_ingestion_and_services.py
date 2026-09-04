"""
Milestone 5 Ingestion & Services Acceptance Test Suite
Comprehensive testing for webhook ingestion, database-enforced idempotency, concurrency,
causal attribution invariants, state machine enforcement, security controls, and transaction rollbacks.
"""

import os
import json
import hmac
import hashlib
import pytest
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.session import Base
from backend.models import (
    Customer,
    Transaction,
    RecoveryCase,
    RecoveryAction,
    RecoveryStrategy,
    StrategyOutcome,
    AuditEvent,
    RecoveryCaseStatus,
    TransactionStatus,
    DataCategory,
    OutcomeSource,
    StrategyType,
)
from backend.services.state_machine import StateMachineService, InvalidStateTransitionError
from backend.services.recovery_service import RecoveryService
from backend.services.ingestion import IngestionService
from backend.services.sanitization import sanitize_payload
from backend.integrations.razorpay import RazorpayWebhookSignatureError

TEST_WEBHOOK_SECRET = "test_secret_key_12345"

@pytest.fixture
def db_session():
    """Fixture creating an isolated in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

def generate_signed_payload(payload_dict: dict, secret: str = TEST_WEBHOOK_SECRET) -> tuple[bytes, str]:
    """Helper to serialize payload dict to raw bytes and compute HMAC-SHA256 signature."""
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
    return raw_bytes, sig


# --- 1. Invalid Webhook Signatures ---
def test_1_invalid_webhook_signature():
    client = TestClient(app)
    raw_payload = {"event": "payment.failed", "event_id": "evt_SIG_FAIL_001"}
    
    with pytest.MonkeyPatch.context() as m:
        m.setattr("backend.config.settings.RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        response = client.post(
            "/api/webhooks/razorpay",
            json=raw_payload,
            headers={"X-Razorpay-Signature": "invalid_signature_hash"},
        )
        assert response.status_code == 400
        assert "signature verification failed" in response.json()["detail"].lower()


# --- 2. Replayed Events & Database-Enforced Idempotency ---
def test_2_replayed_events_and_db_idempotency(db_session):
    ingestion_service = IngestionService()
    payload_dict = {
        "event": "payment.failed",
        "event_id": "evt_REPLAY_100",
        "created_at": 1700000000,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_REPLAY_100",
                    "amount": 200000,
                    "currency": "INR",
                    "status": "failed",
                    "error_code": "BAD_REQUEST_ERROR",
                }
            }
        }
    }
    raw_bytes, sig = generate_signed_payload(payload_dict)

    with pytest.MonkeyPatch.context() as m:
        m.setattr("backend.config.settings.RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        # First delivery
        res1 = ingestion_service.process_webhook_request(db_session, raw_bytes, sig)
        assert res1["status"] == "success"
        assert res1["processed"] is True

        # Second (replayed) delivery with same event_id
        res2 = ingestion_service.process_webhook_request(db_session, raw_bytes, sig)
        assert res2["status"] == "duplicate"
        assert res2["processed"] is False
        assert res2["event_id"] == "evt_REPLAY_100"

    # Verify only ONE audit event and ONE transaction was created in DB
    assert db_session.query(AuditEvent).filter_by(event_id="evt_REPLAY_100").count() == 1
    assert db_session.query(Transaction).filter_by(razorpay_payment_id="pay_REPLAY_100").count() == 1


# --- 3. Concurrent Duplicate Events ---
def test_3_concurrent_duplicate_events(tmp_path):
    """Simulate multithreaded concurrent duplicate webhook delivery to prove DB uniqueness safety."""
    db_file = tmp_path / "test_concurrent.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url, echo=False, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    payload_dict = {
        "event": "payment.failed",
        "event_id": "evt_CONCURRENT_999",
        "created_at": 1700000000,
        "contains": ["payment"],
        "payload": {"payment": {"entity": {"id": "pay_CONCURRENT_999", "amount": 100000}}}
    }
    raw_bytes, sig = generate_signed_payload(payload_dict)

    def worker_deliver():
        session = Session()
        try:
            ingestion_service = IngestionService()
            with pytest.MonkeyPatch.context() as m:
                m.setattr("backend.config.settings.RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
                return ingestion_service.process_webhook_request(session, raw_bytes, sig)
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker_deliver) for _ in range(5)]
        results = [f.result() for f in futures]

    successes = [r for r in results if r.get("status") == "success"]
    duplicates = [r for r in results if r.get("status") == "duplicate"]

    # Exactly 1 worker succeeded, remaining workers received duplicate response from DB constraint
    assert len(successes) == 1
    assert len(duplicates) == 4


# --- 4. Malformed Payloads ---
def test_4_malformed_payloads():
    client = TestClient(app)
    with pytest.MonkeyPatch.context() as m:
        m.setattr("backend.config.settings.RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        response = client.post(
            "/api/webhooks/razorpay",
            content="MALFORMED_NON_JSON_CONTENT",
            headers={"X-Razorpay-Signature": "some_signature"},
        )
        assert response.status_code == 400


# --- 5. Unsupported Events ---
def test_5_unsupported_events(db_session):
    ingestion_service = IngestionService()
    payload_dict = {
        "event": "unsupported.custom_event",
        "event_id": "evt_UNSUPPORTED_001",
        "created_at": 1700000000,
        "payload": {}
    }
    raw_bytes, sig = generate_signed_payload(payload_dict)

    with pytest.MonkeyPatch.context() as m:
        m.setattr("backend.config.settings.RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        res = ingestion_service.process_webhook_request(db_session, raw_bytes, sig)
        assert res["status"] == "success"
        assert res["result"]["action"] == "unhandled_event_logged"

    # Verify event recorded safely in audit log
    assert db_session.query(AuditEvent).filter_by(event_id="evt_UNSUPPORTED_001").count() == 1


# --- 6. payment.failed Processing ---
def test_6_payment_failed_processing(db_session):
    ingestion_service = IngestionService()
    payload_dict = {
        "event": "payment.failed",
        "event_id": "evt_FAIL_TEST_101",
        "created_at": 1700000000,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_FAIL_101",
                    "amount": 350000,
                    "currency": "INR",
                    "email": "aarav@example.com",
                    "contact": "+919876543210",
                    "status": "failed",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_reason": "payment_authentication_failed",
                }
            }
        }
    }
    raw_bytes, sig = generate_signed_payload(payload_dict)

    with pytest.MonkeyPatch.context() as m:
        m.setattr("backend.config.settings.RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        res = ingestion_service.process_webhook_request(db_session, raw_bytes, sig)
        assert res["status"] == "success"
        case_id = res["result"]["case_id"]

    case = db_session.query(RecoveryCase).filter_by(id=case_id).first()
    assert case is not None
    assert case.status == RecoveryCaseStatus.DETECTED.value
    assert case.transaction.amount_paise == 350000
    assert case.customer.email == "aarav@example.com"


# --- 7. Causal Attribution Invariant: Unrelated Successful Payment Must NOT be Claimed ---
def test_7_unrelated_successful_payment_not_attributed(db_session):
    """CRITICAL ACCEPTANCE CRITERIA 5: Successful payment with NO RecoverAI action MUST NOT be claimed as revenue."""
    payload_dict = {
        "event": "payment_link.paid",
        "event_id": "evt_UNRELATED_999",
        "created_at": 1700000000,
        "payload": {
            "payment_link": {"entity": {"id": "plink_UNRELATED_EXTERNAL", "amount": 500000}},
            "payment": {"entity": {"id": "pay_UNRELATED_EXTERNAL", "amount": 500000}},
        }
    }
    raw_bytes, sig = generate_signed_payload(payload_dict)

    ingestion_service = IngestionService()
    with pytest.MonkeyPatch.context() as m:
        m.setattr("backend.config.settings.RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        res = ingestion_service.process_webhook_request(db_session, raw_bytes, sig)
        assert res["status"] == "success"
        result = res["result"]
        assert result["status"] == "unattributed"
        assert result["claimed_by_recoverai"] is False

    # Confirm NO StrategyOutcome or revenue attribution record was created!
    assert db_session.query(StrategyOutcome).count() == 0


# --- 8. State Machine Invariant: Invalid State Transition Fails Safely ---
def test_8_invalid_state_transition_fails_safely(db_session):
    """CRITICAL ACCEPTANCE CRITERIA 6 & 7: State transitions are centrally enforced. Invalid transitions fail safely."""
    txn = Transaction(amount_paise=100000, status=TransactionStatus.FAILED.value)
    db_session.add(txn)
    db_session.commit()

    case = RecoveryCase(transaction_id=txn.id, status=RecoveryCaseStatus.DETECTED.value)
    db_session.add(case)
    db_session.commit()

    # Attempt illegal direct transition DETECTED -> RECOVERED
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        StateMachineService.transition_to(db_session, case, RecoveryCaseStatus.RECOVERED.value)

    assert exc_info.value.current_status == RecoveryCaseStatus.DETECTED.value
    assert exc_info.value.target_status == RecoveryCaseStatus.RECOVERED.value

    # Verify state remained UNCHANGED
    db_session.refresh(case)
    assert case.status == RecoveryCaseStatus.DETECTED.value

    # Verify audit event recorded blocked attempt
    blocked_audit = db_session.query(AuditEvent).filter_by(event_type="INVALID_STATE_TRANSITION_BLOCKED").first()
    assert blocked_audit is not None
    assert blocked_audit.details["attempted_status"] == RecoveryCaseStatus.RECOVERED.value


# --- 9. Already-Recovered Case Protection ---
def test_9_already_recovered_case_protection(db_session):
    """CRITICAL ACCEPTANCE CRITERIA 10: Already-recovered case rejects duplicate attribution."""
    txn = Transaction(amount_paise=200000, status=TransactionStatus.FAILED.value)
    db_session.add(txn)
    db_session.commit()

    case = RecoveryCase(transaction_id=txn.id, status=RecoveryCaseStatus.RECOVERED.value, is_terminal=True)
    db_session.add(case)
    db_session.commit()

    action = RecoveryAction(
        recovery_case_id=case.id,
        action_type=StrategyType.PAYMENT_LINK.value,
        razorpay_payment_link_id="plink_ALREADY_RECOVERED",
    )
    db_session.add(action)
    db_session.commit()

    res = RecoveryService.process_causal_attribution(
        db_session, payment_link_id="plink_ALREADY_RECOVERED", amount_recovered_paise=200000
    )
    assert res["status"] == "already_recovered"
    assert res["claimed_by_recoverai"] is False


# --- 10. Partial Failure & Transaction Rollback ---
def test_10_partial_failure_rollback(db_session):
    """CRITICAL ACCEPTANCE CRITERIA 8 & 9: Database rollback on domain error."""
    ingestion_service = IngestionService()
    payload_dict = {
        "event": "payment.failed",
        "event_id": "evt_ROLLBACK_001",
        "payload": {"payment": {"entity": {"id": "pay_ROLLBACK_001", "amount": 100000}}}
    }
    raw_bytes, sig = generate_signed_payload(payload_dict)

    with patch.object(RecoveryService, "process_failed_payment", side_effect=RuntimeError("Simulated Domain Failure")):
        with pytest.MonkeyPatch.context() as m:
            m.setattr("backend.config.settings.RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
            with pytest.raises(RuntimeError):
                ingestion_service.process_webhook_request(db_session, raw_bytes, sig)

    # Verify entire transaction was rolled back (No audit event or partial state left behind!)
    assert db_session.query(AuditEvent).filter_by(event_id="evt_ROLLBACK_001").count() == 0
    assert db_session.query(Transaction).filter_by(razorpay_payment_id="pay_ROLLBACK_001").count() == 0


# --- 11. Security Tests: Secret & Credential Sanitization ---
def test_11_security_sanitization():
    raw_data = {
        "card_number": "4111111111111111",
        "cvv": "123",
        "secret": "my_secret_key",
        "public_field": "safe_value",
        "nested": {"password": "super_secret_pass", "amount": 5000}
    }
    sanitized = sanitize_payload(raw_data)
    assert sanitized["card_number"] == "[REDACTED]"
    assert sanitized["cvv"] == "[REDACTED]"
    assert sanitized["secret"] == "[REDACTED]"
    assert sanitized["public_field"] == "safe_value"
    assert sanitized["nested"]["password"] == "[REDACTED]"
    assert sanitized["nested"]["amount"] == 5000


# --- 12. Full End-to-End Integration Test: Complete Causal Chain ---
def test_12_full_end_to_end_causal_attribution_chain(db_session):
    """
    CRITICAL ACCEPTANCE CRITERIA 14:
    Signed Webhook -> Ingestion -> Transaction -> RecoveryCase -> Action -> Success Event -> Verification -> Recovered Revenue -> StrategyOutcome -> Audit Trail.
    """
    ingestion_service = IngestionService()
    
    # Step 1: Failed payment webhook arrives
    fail_payload_dict = {
        "event": "payment.failed",
        "event_id": "evt_CHAIN_FAIL_001",
        "created_at": 1700000000,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_CHAIN_FAIL_001",
                    "amount": 250000, # ₹2,500.00
                    "currency": "INR",
                    "status": "failed",
                    "error_reason": "payment_authentication_failed",
                }
            }
        }
    }
    raw_bytes1, sig1 = generate_signed_payload(fail_payload_dict)

    with pytest.MonkeyPatch.context() as m:
        m.setattr("backend.config.settings.RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        res1 = ingestion_service.process_webhook_request(db_session, raw_bytes1, sig1)
        case_id = res1["result"]["case_id"]

    case = db_session.query(RecoveryCase).filter_by(id=case_id).first()
    assert case is not None
    assert case.status == RecoveryCaseStatus.DETECTED.value

    # Step 2: Simulate State Machine progression to POLICY_APPROVED
    StateMachineService.transition_to(db_session, case, RecoveryCaseStatus.ANALYZED.value)
    StateMachineService.transition_to(db_session, case, RecoveryCaseStatus.SEGMENTED.value)
    StateMachineService.transition_to(db_session, case, RecoveryCaseStatus.ELIGIBLE.value)
    StateMachineService.transition_to(db_session, case, RecoveryCaseStatus.STRATEGIES_EVALUATED.value)
    StateMachineService.transition_to(db_session, case, RecoveryCaseStatus.POLICY_APPROVED.value)

    # Step 3: Record RecoverAI Action (Creation of Payment Link plink_CHAIN_100)
    action = RecoveryService.record_recovery_action(
        db_session,
        case=case,
        action_type=StrategyType.PAYMENT_LINK.value,
        razorpay_payment_link_id="plink_CHAIN_100",
        payment_link_url="https://rzp.io/i/chain_100",
    )
    assert action.razorpay_payment_link_id == "plink_CHAIN_100"

    # Step 4: Success webhook arrives (payment_link.paid)
    paid_payload_dict = {
        "event": "payment_link.paid",
        "event_id": "evt_CHAIN_PAID_002",
        "created_at": 1700000050,
        "contains": ["payment_link", "payment"],
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_CHAIN_100",
                    "status": "paid",
                    "reference_id": case.id,
                    "amount": 250000,
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_CHAIN_SUCCESS_999",
                    "amount": 250000,
                }
            }
        }
    }
    raw_bytes2, sig2 = generate_signed_payload(paid_payload_dict)

    with pytest.MonkeyPatch.context() as m:
        m.setattr("backend.config.settings.RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
        res2 = ingestion_service.process_webhook_request(db_session, raw_bytes2, sig2)
        assert res2["status"] == "success"
        result2 = res2["result"]
        assert result2["status"] == "recovered"
        assert result2["claimed_by_recoverai"] is True
        assert result2["amount_paise"] == 250000

    # Step 5: Verify domain invariants & audit trail
    db_session.refresh(case)
    assert case.status == RecoveryCaseStatus.RECOVERED.value
    assert case.is_terminal is True

    # Verify StrategyOutcome record
    outcome = db_session.query(StrategyOutcome).filter_by(recovery_case_id=case.id).first()
    assert outcome is not None
    assert outcome.outcome == "RECOVERED"
    assert outcome.outcome_source == OutcomeSource.VERIFIED.value
    assert outcome.amount_recovered_paise == 250000

    # Verify Audit Events
    audit_events = db_session.query(AuditEvent).filter_by(recovery_case_id=case.id).all()
    event_types = [a.event_type for a in audit_events]
    assert "CASE_DETECTED" in event_types
    assert "RECOVERY_ATTRIBUTED" in event_types
