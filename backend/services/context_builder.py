"""
Context Builder Service — RecoverAI Milestone 10
Assembles complete structured context (transaction, customer history, 4D segment, prior recovery actions)
for a RecoveryCase.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.models.recovery_case import RecoveryCase
from backend.models.recovery_action import RecoveryAction
from backend.models.enums import StrategyType

logger = logging.getLogger(__name__)

class ContextBuilder:
    """Service for assembling rich structured context for recovery cases."""

    @staticmethod
    def assemble_case_context(db: Session, case: RecoveryCase, as_of_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Assemble structured context for a RecoveryCase:
        - Transaction details + integer paise amount + failure details
        - Customer details + 24h contact history + purchase profile
        - Canonical 4D Segment information
        - Prior recovery attempt history & active link status
        """
        now = as_of_time or datetime.now(timezone.utc)
        txn = case.transaction
        cust = case.customer
        segment = case.segment

        # Calculate transaction age in hours
        txn_created = txn.created_at if (txn and txn.created_at) else now
        if txn_created.tzinfo is None:
            txn_created = txn_created.replace(tzinfo=timezone.utc)
        age_seconds = (now - txn_created).total_seconds()
        age_hours = max(0.0, round(age_seconds / 3600.0, 2))

        # Retrieve prior recovery actions
        actions = db.query(RecoveryAction).filter_by(recovery_case_id=case.id).all()
        action_history = [
            {
                "id": a.id,
                "action_type": a.action_type,
                "execution_mode": a.execution_mode,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in actions
        ]

        active_payment_link = next(
            (a.razorpay_payment_link_id for a in actions if a.action_type == StrategyType.PAYMENT_LINK.value and a.status in ("PENDING", "SENT")),
            None
        )

        return {
            "case": {
                "id": case.id,
                "status": case.status,
                "attempt_count": case.attempt_count,
                "is_terminal": case.is_terminal,
                "recoverability_score": case.recoverability_score,
                "detected_at": case.detected_at.isoformat() if case.detected_at else None,
            },
            "transaction": {
                "id": txn.id if txn else None,
                "razorpay_payment_id": txn.razorpay_payment_id if txn else None,
                "razorpay_order_id": txn.razorpay_order_id if txn else None,
                "amount_paise": txn.amount_paise if txn else 0,
                "amount_rupees": (txn.amount_paise / 100.0) if txn else 0.0,
                "currency": txn.currency if txn else "INR",
                "status": txn.status if txn else "FAILED",
                "failure_category": txn.failure_category if txn else "UNKNOWN",
                "error_code": txn.error_code if txn else None,
                "error_description": txn.error_description if txn else None,
                "error_source": txn.error_source if txn else None,
                "error_step": txn.error_step if txn else None,
                "error_reason": txn.error_reason if txn else None,
                "payment_method": txn.payment_method if txn else "card",
                "data_source": txn.data_source if txn else "OBSERVED",
                "created_at": txn_created.isoformat(),
                "age_hours": age_hours,
            },
            "customer": {
                "id": cust.id if cust else None,
                "email": cust.email if cust else None,
                "phone": cust.phone if cust else None,
                "name": cust.name if cust else None,
                "customer_type": getattr(cust, "customer_type", "NEW") if cust else "NEW",
                "contacts_count_24h": getattr(cust, "contacts_count_24h", 0) if cust else 0,
                "total_transactions": getattr(cust, "total_transactions", 0) if cust else 0,
                "successful_transactions": getattr(cust, "successful_transactions", 0) if cust else 0,
                "failed_transactions": getattr(cust, "failed_transactions", 0) if cust else 0,
            },
            "segment": {
                "id": segment.id if segment else None,
                "name": segment.name if segment else "unknown",
                "failure_category": segment.failure_category if segment else "UNKNOWN",
                "payment_method": segment.payment_method if segment else "card",
                "amount_range": segment.amount_range if segment else "MID",
                "customer_type": segment.customer_type if segment else "NEW",
            },
            "recovery_history": {
                "attempt_count": case.attempt_count,
                "action_history": action_history,
                "active_payment_link_id": active_payment_link,
            },
        }
