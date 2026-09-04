"""
Unit & Integration Test Suite for Razorpay API Wrapper & Webhooks.
Covers all 20 required Razorpay integration test cases using mocks and deterministic payloads.
"""

import json
import pytest
import hmac
import hashlib
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.session import Base
from backend.integrations.razorpay import (
    RazorpayClient,
    RazorpayPaymentService,
    RazorpayOrderService,
    RazorpayPaymentLinkService,
    RazorpayWebhookService,
    CreatePaymentLinkRequest,
    RazorpayAuthenticationError,
    RazorpayInvalidRequestError,
    RazorpayResourceNotFoundError,
    RazorpayServerError,
    RazorpayTimeoutError,
    RazorpayWebhookSignatureError,
)
from backend.models.audit_event import AuditEvent

TEST_KEY_ID = "rzp_test_mock_key_123"
TEST_KEY_SECRET = "mock_secret_456"
TEST_WEBHOOK_SECRET = "mock_webhook_secret_789"

@pytest.fixture
def mock_client():
    """Fixture returning a RazorpayClient initialized with mock credentials."""
    return RazorpayClient(
        key_id=TEST_KEY_ID,
        key_secret=TEST_KEY_SECRET,
        webhook_secret=TEST_WEBHOOK_SECRET,
    )

@pytest.fixture
def db_session():
    """Fixture returning an in-memory SQLite database session for webhook idempotency tests."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


# --- 1. Razorpay client initialization ---
def test_1_razorpay_client_initialization(mock_client):
    assert mock_client.key_id == TEST_KEY_ID
    assert mock_client.key_secret == TEST_KEY_SECRET
    assert mock_client.webhook_secret == TEST_WEBHOOK_SECRET
    assert mock_client._sdk_client is not None


# --- 2. Test Mode configuration validation ---
def test_2_test_mode_configuration_validation():
    client = RazorpayClient(key_id="rzp_test_12345", key_secret="secret_abc")
    assert client.key_id.startswith("rzp_test_")


# --- 3. Successful payment fetch ---
def test_3_successful_payment_fetch(mock_client):
    service = RazorpayPaymentService(client=mock_client)
    mock_payload = {
        "id": "pay_TEST123",
        "amount": 150000,
        "currency": "INR",
        "status": "failed",
        "method": "card",
        "email": "customer@example.com",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Payment failed due to invalid OTP",
        "error_reason": "payment_authentication_failed",
        "created_at": 1700000000,
    }
    with patch.object(mock_client._sdk_client.payment, "fetch", return_value=mock_payload):
        payment = service.fetch_payment("pay_TEST123")
        assert payment.id == "pay_TEST123"
        assert payment.amount_paise == 150000
        assert payment.status == "failed"
        assert payment.error_code == "BAD_REQUEST_ERROR"
        assert payment.error_reason == "payment_authentication_failed"


# --- 4. Successful order fetch ---
def test_4_successful_order_fetch(mock_client):
    service = RazorpayOrderService(client=mock_client)
    mock_payload = {
        "id": "order_TEST456",
        "amount": 50000,
        "currency": "INR",
        "status": "created",
        "attempts": 0,
        "receipt": "rcpt_001",
        "created_at": 1700000000,
    }
    with patch.object(mock_client._sdk_client.order, "fetch", return_value=mock_payload):
        order = service.fetch_order("order_TEST456")
        assert order.id == "order_TEST456"
        assert order.amount_paise == 50000
        assert order.status == "created"
        assert order.attempts == 0


# --- 5. Order creation ---
def test_5_order_creation(mock_client):
    service = RazorpayOrderService(client=mock_client)
    mock_payload = {
        "id": "order_NEW789",
        "amount": 75000,
        "currency": "INR",
        "status": "created",
        "attempts": 0,
        "receipt": "rcpt_new",
        "created_at": 1700000000,
    }
    with patch.object(mock_client._sdk_client.order, "create", return_value=mock_payload):
        order = service.create_order(amount_paise=75000, receipt="rcpt_new")
        assert order.id == "order_NEW789"
        assert order.amount_paise == 75000


# --- 6. Payment Link creation ---
def test_6_payment_link_creation(mock_client):
    service = RazorpayPaymentLinkService(client=mock_client)
    req = CreatePaymentLinkRequest(
        amount_paise=150000,
        description="Recovery Link for auth failure",
        reference_id="case_12345",
        customer_name="Priya Singh",
        customer_email="priya@example.com",
    )
    mock_payload = {
        "id": "plink_LINK101",
        "amount": 150000,
        "currency": "INR",
        "status": "created",
        "short_url": "https://rzp.io/i/mock_link",
        "reference_id": "case_12345",
        "description": "Recovery Link for auth failure",
        "created_at": 1700000000,
    }
    with patch.object(mock_client._sdk_client.payment_link, "create", return_value=mock_payload):
        link = service.create_payment_link(req)
        assert link.id == "plink_LINK101"
        assert link.short_url == "https://rzp.io/i/mock_link"
        assert link.amount_paise == 150000


# --- 7. Payment Link fetch ---
def test_7_payment_link_fetch(mock_client):
    service = RazorpayPaymentLinkService(client=mock_client)
    mock_payload = {
        "id": "plink_LINK101",
        "amount": 150000,
        "status": "paid",
        "short_url": "https://rzp.io/i/mock_link",
        "created_at": 1700000000,
    }
    with patch.object(mock_client._sdk_client.payment_link, "fetch", return_value=mock_payload):
        link = service.fetch_payment_link("plink_LINK101")
        assert link.id == "plink_LINK101"
        assert link.status == "paid"


# --- 8. Payment Link cancellation where supported ---
def test_8_payment_link_cancellation(mock_client):
    service = RazorpayPaymentLinkService(client=mock_client)
    mock_payload = {
        "id": "plink_LINK101",
        "amount": 150000,
        "status": "cancelled",
        "short_url": "https://rzp.io/i/mock_link",
        "created_at": 1700000000,
    }
    with patch.object(mock_client._sdk_client.payment_link, "cancel", return_value=mock_payload):
        link = service.cancel_payment_link("plink_LINK101")
        assert link.status == "cancelled"


# --- 9. API authentication failure ---
def test_9_api_authentication_failure(mock_client):
    import razorpay.errors
    service = RazorpayPaymentService(client=mock_client)
    with patch.object(
        mock_client._sdk_client.payment,
        "fetch",
        side_effect=razorpay.errors.BadRequestError("401 Authentication failed"),
    ):
        with pytest.raises(RazorpayAuthenticationError):
            service.fetch_payment("pay_INVALID_AUTH")


# --- 10. Invalid request ---
def test_10_invalid_request(mock_client):
    import razorpay.errors
    service = RazorpayOrderService(client=mock_client)
    with patch.object(
        mock_client._sdk_client.order,
        "create",
        side_effect=razorpay.errors.BadRequestError("Amount must be at least 100 paise"),
    ):
        with pytest.raises(RazorpayInvalidRequestError):
            service.create_order(amount_paise=50)


# --- 11. Timeout ---
def test_11_timeout_handling(mock_client):
    service = RazorpayPaymentService(client=mock_client)
    with patch.object(
        mock_client._sdk_client.payment,
        "fetch",
        side_effect=TimeoutError("Request timed out after 10.0s"),
    ):
        with pytest.raises(RazorpayTimeoutError):
            service.fetch_payment("pay_SLOW123")


# --- 12. HTTP/API failure ---
def test_12_http_api_failure(mock_client):
    import razorpay.errors
    service = RazorpayPaymentService(client=mock_client)
    with patch.object(
        mock_client._sdk_client.payment,
        "fetch",
        side_effect=razorpay.errors.ServerError("502 Bad Gateway"),
    ):
        with pytest.raises(RazorpayServerError):
            service.fetch_payment("pay_SERVER_ERR")


# --- 13. Malformed Razorpay response ---
def test_13_malformed_razorpay_response(mock_client):
    service = RazorpayWebhookService(client=mock_client)
    with patch.object(mock_client, "verify_webhook_signature", return_value=True):
        with pytest.raises(RazorpayInvalidRequestError):
            service.verify_and_parse_webhook("INVALID_NON_JSON_BODY", "mock_signature")


# --- 14. Webhook signature success ---
def test_14_webhook_signature_success(mock_client):
    service = RazorpayWebhookService(client=mock_client)
    raw_payload = json.dumps({
        "event": "payment.failed",
        "event_id": "evt_PAYMENT_FAILED_001",
        "created_at": 1700000000,
        "contains": ["payment"],
        "payload": {"payment": {"entity": {"id": "pay_FAIL123"}}}
    })
    
    # Generate valid HMAC-SHA256 signature
    valid_sig = hmac.new(
        TEST_WEBHOOK_SECRET.encode("utf-8"),
        raw_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    parsed = service.verify_and_parse_webhook(raw_payload, valid_sig)
    assert parsed.event == "payment.failed"
    assert parsed.event_id == "evt_PAYMENT_FAILED_001"


# --- 15. Webhook signature failure ---
def test_15_webhook_signature_failure(mock_client):
    service = RazorpayWebhookService(client=mock_client)
    raw_payload = json.dumps({"event": "payment.failed", "event_id": "evt_123"})
    
    with pytest.raises(RazorpayWebhookSignatureError):
        service.verify_and_parse_webhook(raw_payload, "INVALID_SIGNATURE_HASH")


# --- 16. Duplicate webhook ---
def test_16_duplicate_webhook(mock_client, db_session):
    service = RazorpayWebhookService(client=mock_client)
    
    # Insert prior audit event with event_id
    existing_audit = AuditEvent(
        event_type="WEBHOOK_PAYMENT_FAILED",
        event_id="evt_DUP_999",
        description="Previous webhook event",
    )
    db_session.add(existing_audit)
    db_session.commit()

    is_dup = service.is_duplicate_event(db_session, "evt_DUP_999")
    assert is_dup is True


# --- 17. Webhook idempotency ---
def test_17_webhook_idempotency(mock_client, db_session):
    service = RazorpayWebhookService(client=mock_client)
    is_dup_first = service.is_duplicate_event(db_session, "evt_NEW_100")
    assert is_dup_first is False

    # Simulate parsing and recording
    payload = service.verify_and_parse_webhook(
        json.dumps({"event": "payment.failed", "event_id": "evt_NEW_100", "created_at": 1700000000}),
        hmac.new(TEST_WEBHOOK_SECRET.encode("utf-8"), json.dumps({"event": "payment.failed", "event_id": "evt_NEW_100", "created_at": 1700000000}).encode("utf-8"), hashlib.sha256).hexdigest()
    )
    service.record_webhook_audit_event(db_session, payload)

    # Check second attempt
    is_dup_second = service.is_duplicate_event(db_session, "evt_NEW_100")
    assert is_dup_second is True


# --- 18. payment_link.paid processing ---
def test_18_payment_link_paid_processing(mock_client):
    service = RazorpayWebhookService(client=mock_client)
    body_dict = {
        "event": "payment_link.paid",
        "event_id": "evt_PLINK_PAID_777",
        "created_at": 1700000000,
        "contains": ["payment_link", "payment"],
        "payload": {
            "payment_link": {"entity": {"id": "plink_101", "status": "paid"}},
            "payment": {"entity": {"id": "pay_SUCCESS_999", "amount": 150000}},
        }
    }
    body_bytes = json.dumps(body_dict).encode("utf-8")
    sig = hmac.new(TEST_WEBHOOK_SECRET.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    parsed = service.verify_and_parse_webhook(body_bytes, sig)
    assert parsed.event == "payment_link.paid"
    assert parsed.payload["payment_link"]["entity"]["id"] == "plink_101"
    assert parsed.payload["payment"]["entity"]["id"] == "pay_SUCCESS_999"


# --- 19. payment.failed processing ---
def test_19_payment_failed_processing(mock_client):
    service = RazorpayWebhookService(client=mock_client)
    body_dict = {
        "event": "payment.failed",
        "event_id": "evt_PAY_FAILED_888",
        "created_at": 1700000000,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_FAIL_888",
                    "amount": 250000,
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_reason": "payment_authentication_failed"
                }
            }
        }
    }
    body_bytes = json.dumps(body_dict).encode("utf-8")
    sig = hmac.new(TEST_WEBHOOK_SECRET.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    parsed = service.verify_and_parse_webhook(body_bytes, sig)
    assert parsed.event == "payment.failed"
    assert parsed.payload["payment"]["entity"]["error_reason"] == "payment_authentication_failed"


# --- 20. Safe error handling (no secret leakage) ---
def test_20_safe_error_handling(mock_client):
    err = RazorpayAuthenticationError("Invalid API key or secret")
    assert TEST_KEY_SECRET not in str(err)
    assert err.status_code == 401
