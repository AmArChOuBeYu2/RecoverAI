"""
Database-Enforced Webhook Ingestion Service
Handles raw signature verification, atomic database idempotency, and transactional event routing.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.integrations.razorpay import RazorpayWebhookService, RazorpayWebhookPayload
from backend.models.audit_event import AuditEvent
from backend.services.recovery_service import RecoveryService
from backend.services.sanitization import sanitize_payload

logger = logging.getLogger(__name__)

class IngestionService:
    """Service wrapper for webhook ingestion with database-level idempotency and transaction boundaries."""

    def __init__(self, webhook_service: Optional[RazorpayWebhookService] = None):
        self.webhook_service = webhook_service or RazorpayWebhookService()

    def process_webhook_request(
        self, db: Session, raw_body: bytes | str, signature: str
    ) -> Dict[str, Any]:
        """
        Process incoming Razorpay webhook request:
        1. Verify HMAC SHA-256 signature using exact raw body. Rejects tampered bodies with HTTP 400.
        2. Enforce DB-level idempotency by flushing AuditEvent with event_id.
        3. If DB IntegrityError is raised (duplicate event_id), rollback and return duplicate status.
        4. Execute domain handler atomically. If any error occurs, rollback transaction completely.
        """
        # 1. Signature Verification (raises RazorpayWebhookSignatureError on failure)
        payload = self.webhook_service.verify_and_parse_webhook(raw_body, signature)

        # 2. Database-enforced Idempotency & Atomic Transaction
        try:
            # Add audit event entry with unique event_id
            audit_event = AuditEvent(
                event_type=f"WEBHOOK_{payload.event.upper().replace('.', '_')}",
                event_id=payload.event_id,
                actor="RAZORPAY_WEBHOOK",
                description=f"Ingested webhook event '{payload.event}'",
                details=sanitize_payload(payload.payload),
            )
            db.add(audit_event)
            db.flush() # Triggers DB unique constraint check on event_id immediately
        except IntegrityError:
            # Caught database-enforced unique constraint violation (duplicate event_id)
            db.rollback()
            logger.info(f"Duplicate webhook event_id '{payload.event_id}' rejected by database constraint.")
            return {
                "status": "duplicate",
                "processed": False,
                "event_id": payload.event_id,
                "message": "Event has already been processed",
            }

        # 3. Route domain processing within the SAME atomic transaction
        try:
            result = self._route_webhook_event(db, payload)
            db.commit()
            return {
                "status": "success",
                "processed": True,
                "event_id": payload.event_id,
                "event": payload.event,
                "result": result,
            }
        except Exception as e:
            # Transactional safety: rollback ANY mutations (including audit_event) if domain processing fails
            logger.error(f"Error processing webhook event '{payload.event_id}': {str(e)}")
            db.rollback()
            raise

    def _route_webhook_event(self, db: Session, payload: RazorpayWebhookPayload) -> Dict[str, Any]:
        """Route parsed webhook payload to appropriate domain recovery logic."""
        event = payload.event
        event_payload = payload.payload

        if event == "payment.failed":
            payment_entity = event_payload.get("payment", {}).get("entity", {})
            case = RecoveryService.process_failed_payment(db, payment_entity)
            return {"action": "case_created", "case_id": case.id}

        elif event == "payment_link.paid":
            plink_entity = event_payload.get("payment_link", {}).get("entity", {})
            payment_entity = event_payload.get("payment", {}).get("entity", {})
            
            plink_id = plink_entity.get("id")
            payment_id = payment_entity.get("id")
            ref_id = plink_entity.get("reference_id")
            amount = payment_entity.get("amount") or plink_entity.get("amount", 0)

            return RecoveryService.process_causal_attribution(
                db,
                payment_link_id=plink_id,
                payment_id=payment_id,
                reference_id=ref_id,
                amount_recovered_paise=amount,
                raw_payload=event_payload,
            )

        elif event == "payment.captured":
            payment_entity = event_payload.get("payment", {}).get("entity", {})
            payment_id = payment_entity.get("id")
            order_id = payment_entity.get("order_id")
            amount = payment_entity.get("amount", 0)

            return RecoveryService.process_causal_attribution(
                db,
                payment_id=payment_id,
                reference_id=order_id,
                amount_recovered_paise=amount,
                raw_payload=event_payload,
            )

        else:
            logger.info(f"Unhandled webhook event type '{event}'. Recorded in audit log.")
            return {"action": "unhandled_event_logged", "event": event}
