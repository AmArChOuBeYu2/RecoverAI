"""
Razorpay Webhook Service Integration
Handles webhook signature verification, event validation, idempotency, and audit logging.
"""

import json
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.integrations.razorpay.client import RazorpayClient
from backend.integrations.razorpay.schemas import RazorpayWebhookPayload
from backend.integrations.razorpay.exceptions import RazorpayWebhookSignatureError, RazorpayInvalidRequestError
from backend.models.audit_event import AuditEvent

logger = logging.getLogger(__name__)

class RazorpayWebhookService:
    """Service wrapper for Razorpay Webhook processing & idempotency enforcement."""

    def __init__(self, client: Optional[RazorpayClient] = None):
        self.client = client or RazorpayClient()

    def verify_and_parse_webhook(
        self, body_bytes: bytes | str, signature: str
    ) -> RazorpayWebhookPayload:
        """
        Verify raw HMAC-SHA256 webhook signature and parse event payload.
        Raises RazorpayWebhookSignatureError if verification fails.
        """
        # 1. Verify signature against configured webhook secret
        self.client.verify_webhook_signature(body_bytes, signature)

        # 2. Parse JSON payload
        try:
            if isinstance(body_bytes, bytes):
                body_str = body_bytes.decode("utf-8")
            else:
                body_str = body_bytes
            
            raw_json = json.loads(body_str)
        except json.JSONDecodeError as e:
            raise RazorpayInvalidRequestError(f"Malformed JSON webhook payload: {str(e)}")

        event_name = raw_json.get("event")
        event_id = raw_json.get("event_id")
        created_at = raw_json.get("created_at", 0)

        if not event_name or not event_id:
            raise RazorpayInvalidRequestError("Missing required 'event' or 'event_id' fields in webhook payload")

        return RazorpayWebhookPayload(
            event=event_name,
            event_id=event_id,
            created_at=created_at,
            contains=raw_json.get("contains", []),
            payload=raw_json.get("payload", {}),
        )

    def is_duplicate_event(self, db: Session, event_id: str) -> bool:
        """Check if a webhook event_id has already been processed (idempotency check)."""
        existing = db.query(AuditEvent).filter_by(event_id=event_id).first()
        return existing is not None

    def record_webhook_audit_event(
        self, db: Session, payload: RazorpayWebhookPayload, recovery_case_id: Optional[str] = None
    ) -> AuditEvent:
        """Record an audit event entry for the received webhook with unique event_id."""
        audit_entry = AuditEvent(
            event_type=f"WEBHOOK_{payload.event.upper().replace('.', '_')}",
            event_id=payload.event_id,
            recovery_case_id=recovery_case_id,
            actor="RAZORPAY_WEBHOOK",
            description=f"Received Razorpay webhook event '{payload.event}'",
            details=payload.payload,
        )
        db.add(audit_entry)
        db.commit()
        return audit_entry
