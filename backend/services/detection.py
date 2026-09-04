"""
Detection Engine — RecoverAI Milestone 10
Detects failed payments and abandoned checkouts, creates RecoveryCase entities,
and initiates segmentation pipeline.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from backend.models.transaction import Transaction
from backend.models.recovery_case import RecoveryCase
from backend.models.audit_event import AuditEvent
from backend.models.enums import (
    TransactionStatus,
    FailureCategory,
    RecoveryCaseStatus,
    DataCategory,
)
from backend.services.recovery_service import RecoveryService
from backend.services.segmentation import SegmentationService
from backend.services.sanitization import sanitize_payload

logger = logging.getLogger(__name__)

class DetectionEngine:
    """Engine for detecting payment failures and initializing recovery cases."""

    @staticmethod
    def detect_unhandled_failures(db: Session, limit: int = 500) -> List[RecoveryCase]:
        """
        Scan database for Transactions in FAILED status that do NOT have a RecoveryCase.
        Initializes RecoveryCase (status=DETECTED) and assigns canonical 4D segment.
        """
        # Find failed transactions without recovery cases
        unhandled_txns = (
            db.query(Transaction)
            .outerjoin(RecoveryCase, Transaction.id == RecoveryCase.transaction_id)
            .filter(Transaction.status == TransactionStatus.FAILED.value)
            .filter(RecoveryCase.id.is_(None))
            .limit(limit)
            .all()
        )

        detected_cases = []
        for txn in unhandled_txns:
            case = RecoveryCase(
                transaction_id=txn.id,
                customer_id=txn.customer_id,
                status=RecoveryCaseStatus.DETECTED.value,
                attempt_count=0,
            )
            db.add(case)
            db.flush()

            db.add(AuditEvent(
                recovery_case_id=case.id,
                event_type="CASE_DETECTED",
                actor="SYSTEM",
                description=f"DetectionEngine initialized recovery case for transaction {txn.razorpay_payment_id or txn.id}",
                details={
                    "transaction_id": txn.id,
                    "payment_id": txn.razorpay_payment_id,
                    "failure_category": txn.failure_category,
                    "amount_paise": txn.amount_paise,
                },
            ))
            db.flush()

            # Advance to SEGMENTED via SegmentationService
            SegmentationService.assign_segment_to_case(db, case)
            detected_cases.append(case)

        db.flush()
        logger.info(f"DetectionEngine detected and segmented {len(detected_cases)} recovery cases.")
        return detected_cases

    @staticmethod
    def process_transaction_payload(db: Session, payment_data: Dict[str, Any]) -> RecoveryCase:
        """
        Process a single payment failure payload (e.g. from webhook or API batch),
        create transaction + case, and advance to SEGMENTED.
        """
        case = RecoveryService.process_failed_payment(db, payment_data)
        if case.status == RecoveryCaseStatus.DETECTED.value:
            SegmentationService.assign_segment_to_case(db, case)
        return case

    @staticmethod
    def detect_abandoned_checkouts(
        db: Session,
        min_age_minutes: int = 15,
        limit: int = 500,
        as_of_time: Optional[datetime] = None,
    ) -> List[RecoveryCase]:
        """
        Scan database for Transactions in CREATED status (zero payment attempts) older than min_age_minutes.
        Infers CUSTOMER_ABANDONMENT condition, initializes RecoveryCase (status=DETECTED),
        logs audit event with inferred_condition=True, and advances to SEGMENTED.
        """
        now = as_of_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        cutoff = now - timedelta(minutes=min_age_minutes)

        # Find CREATED transactions without recovery cases created before cutoff
        candidate_txns = (
            db.query(Transaction)
            .outerjoin(RecoveryCase, Transaction.id == RecoveryCase.transaction_id)
            .filter(Transaction.status == TransactionStatus.CREATED.value)
            .filter(RecoveryCase.id.is_(None))
            .limit(limit)
            .all()
        )

        abandoned_cases = []
        for txn in candidate_txns:
            txn_created = txn.created_at if txn.created_at else now
            if txn_created.tzinfo is None:
                txn_created = txn_created.replace(tzinfo=timezone.utc)

            # Strict age check: transaction age must be > min_age_minutes
            if txn_created > cutoff:
                continue

            # Set failure_category to CHECKOUT_ABANDONMENT
            txn.failure_category = FailureCategory.CHECKOUT_ABANDONMENT.value

            case = RecoveryCase(
                transaction_id=txn.id,
                customer_id=txn.customer_id,
                status=RecoveryCaseStatus.DETECTED.value,
                attempt_count=0,
            )
            db.add(case)
            db.flush()

            db.add(AuditEvent(
                recovery_case_id=case.id,
                event_type="ABANDONED_CHECKOUT_DETECTED",
                actor="SYSTEM",
                description=f"Inferred abandoned checkout condition for transaction {txn.razorpay_order_id or txn.id} (created > {min_age_minutes}m ago with 0 attempts)",
                details={
                    "transaction_id": txn.id,
                    "order_id": txn.razorpay_order_id,
                    "inferred_condition": True,
                    "failure_category": FailureCategory.CHECKOUT_ABANDONMENT.value,
                    "age_minutes": round((now - txn_created).total_seconds() / 60.0, 2),
                },
            ))
            db.flush()

            # Advance to SEGMENTED via SegmentationService
            SegmentationService.assign_segment_to_case(db, case)
            abandoned_cases.append(case)

        db.flush()
        logger.info(f"DetectionEngine detected {len(abandoned_cases)} inferred abandoned checkouts.")
        return abandoned_cases

