"""
Segmentation Service — RecoverAI Milestone 9
Handles deterministic 4D segment derivation, auto-creation, database initialization,
case assignment, and state machine transition (ANALYZED -> SEGMENTED).
"""

import logging
from typing import Optional, Union, Dict, Any, List
from sqlalchemy.orm import Session

from backend.models.segment import Segment
from backend.models.recovery_case import RecoveryCase
from backend.models.recovery_strategy import RecoveryStrategy
from backend.models.transaction import Transaction
from backend.models.customer import Customer
from backend.models.audit_event import AuditEvent
from backend.models.enums import (
    FailureCategory,
    AmountRange,
    CustomerType,
    StrategyType,
    RecoveryCaseStatus,
    ConfidenceLevel,
    DataCategory,
)
from backend.services.state_machine import StateMachineService

logger = logging.getLogger(__name__)

# Standard combinations for canonical 4D segments
VALID_FAILURE_CATEGORIES = [
    FailureCategory.AUTHENTICATION_FAILURE.value,
    FailureCategory.BANK_TIMEOUT.value,
    FailureCategory.NETWORK_FAILURE.value,
    FailureCategory.INSUFFICIENT_FUNDS.value,
    FailureCategory.CHECKOUT_ABANDONMENT.value,
    FailureCategory.REPEATED_FAILURE.value,
    FailureCategory.BUSINESS_ERROR.value,
]

VALID_PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet"]
VALID_AMOUNT_RANGES = [AmountRange.LOW.value, AmountRange.MID.value, AmountRange.HIGH.value, AmountRange.PREMIUM.value]
VALID_CUSTOMER_TYPES = [CustomerType.NEW.value, CustomerType.RETURNING.value, CustomerType.FATIGUED.value]

ALL_STRATEGY_TYPES = [
    StrategyType.PAYMENT_LINK.value,
    StrategyType.RETRY.value,
    StrategyType.REMINDER.value,
    StrategyType.DELAYED_RETRY.value,
    StrategyType.METHOD_SWITCH.value,
    StrategyType.NO_ACTION.value,
    StrategyType.HUMAN_REVIEW.value,
]

class SegmentationService:
    """Service for deterministic payment failure segmentation and tracking."""

    @staticmethod
    def derive_amount_range(amount_paise: int) -> str:
        """
        Map monetary amount in integer paise to canonical AmountRange enum:
        - LOW: < ₹500 (< 50,000 paise)
        - MID: ₹500 - ₹5,000 (50,000 - 500,000 paise)
        - HIGH: ₹5,000 - ₹50,000 (500,001 - 5,000,000 paise)
        - PREMIUM: > ₹50,000 (> 5,000,000 paise)
        """
        if amount_paise < 50000:
            return AmountRange.LOW.value
        elif amount_paise <= 500000:
            return AmountRange.MID.value
        elif amount_paise <= 5000000:
            return AmountRange.HIGH.value
        else:
            return AmountRange.PREMIUM.value

    @staticmethod
    def derive_canonical_segment_name(
        failure_category: str,
        payment_method: Optional[str],
        amount_range_or_paise: Union[str, int],
        customer_type: Optional[str],
    ) -> str:
        """
        Construct the canonical 4D segment name key:
        {failure_category}_{payment_method}_{amount_range}_{customer_type}
        """
        cat_str = (failure_category or "unknown").lower()
        method_str = (payment_method or "unknown").lower()
        
        if isinstance(amount_range_or_paise, int):
            amt_str = SegmentationService.derive_amount_range(amount_range_or_paise).lower()
        else:
            amt_str = (amount_range_or_paise or "mid").lower()

        cust_str = (customer_type or "new").lower()
        return f"{cat_str}_{method_str}_{amt_str}_{cust_str}"

    @staticmethod
    def get_or_create_segment(
        db: Session,
        failure_category: str,
        payment_method: Optional[str],
        amount_range_or_paise: Union[str, int],
        customer_type: Optional[str],
    ) -> Segment:
        """
        Retrieve existing Segment by 4D canonical name or auto-create and persist it with
        default strategy tracking records.
        """
        if isinstance(amount_range_or_paise, int):
            amount_range = SegmentationService.derive_amount_range(amount_range_or_paise)
        else:
            amount_range = (amount_range_or_paise or AmountRange.MID.value).upper()

        method_str = (payment_method or "unknown").lower()
        cust_type_str = (customer_type or CustomerType.NEW.value).upper()
        cat_str = (failure_category or FailureCategory.AUTHENTICATION_FAILURE.value).upper()

        name = SegmentationService.derive_canonical_segment_name(
            cat_str, method_str, amount_range, cust_type_str
        )

        segment = db.query(Segment).filter_by(name=name).first()
        if segment:
            return segment

        # Auto-create segment
        description = (
            f"Segment for {cat_str} failure via {method_str.upper()} "
            f"in range {amount_range} for {cust_type_str} customer"
        )
        segment = Segment(
            name=name,
            failure_category=cat_str,
            payment_method=method_str,
            amount_range=amount_range,
            customer_type=cust_type_str,
            description=description,
        )
        db.add(segment)
        db.flush()

        # Initialize strategy performance tracking entries for all strategies
        for strat_type in ALL_STRATEGY_TYPES:
            existing_strat = db.query(RecoveryStrategy).filter_by(
                segment_id=segment.id, strategy_type=strat_type
            ).first()
            if not existing_strat:
                db.add(RecoveryStrategy(
                    segment_id=segment.id,
                    strategy_type=strat_type,
                    attempt_count=0,
                    success_count=0,
                    total_recovered_paise=0,
                    recovery_rate=0.0,
                    wilson_lower_bound=0.0,
                    sample_size_sufficient=False,
                    confidence_level=ConfidenceLevel.INSUFFICIENT.value,
                    data_source=DataCategory.OBSERVED.value,
                ))

        db.flush()
        logger.info(f"Auto-created canonical 4D segment: {name} (ID: {segment.id})")
        return segment

    @staticmethod
    def seed_all_canonical_segments(db: Session) -> List[Segment]:
        """
        Seed all 336 canonical 4D segments in the database idempotently.
        """
        segments = []
        for cat in VALID_FAILURE_CATEGORIES:
            for method in VALID_PAYMENT_METHODS:
                for amt in VALID_AMOUNT_RANGES:
                    for cust in VALID_CUSTOMER_TYPES:
                        seg = SegmentationService.get_or_create_segment(
                            db, failure_category=cat, payment_method=method, amount_range_or_paise=amt, customer_type=cust
                        )
                        segments.append(seg)
        db.commit()
        return segments

    @staticmethod
    def assign_segment_to_case(db: Session, case: RecoveryCase) -> Segment:
        """
        Deterministically segment a RecoveryCase:
        1. Extract transaction and customer attributes.
        2. Resolve or auto-create canonical 4D Segment.
        3. Associate segment with case.
        4. Advance state machine DETECTED -> ANALYZED -> SEGMENTED.
        5. Log immutable audit event.
        """
        txn = case.transaction
        cust = case.customer

        failure_category = txn.failure_category if txn else FailureCategory.AUTHENTICATION_FAILURE.value
        payment_method = txn.payment_method if txn else "card"
        amount_paise = txn.amount_paise if txn else 0
        customer_type = getattr(cust, "customer_type", None) if cust else None
        if not customer_type:
            customer_type = CustomerType.NEW.value

        segment = SegmentationService.get_or_create_segment(
            db=db,
            failure_category=failure_category,
            payment_method=payment_method,
            amount_range_or_paise=amount_paise,
            customer_type=customer_type,
        )

        case.segment_id = segment.id

        # Advance state machine through DETECTED -> ANALYZED -> SEGMENTED if needed
        if case.status == RecoveryCaseStatus.DETECTED.value:
            StateMachineService.transition_to(
                db, case, RecoveryCaseStatus.ANALYZED.value, actor="SYSTEM", reason="Completed failure context analysis"
            )
        if case.status == RecoveryCaseStatus.ANALYZED.value:
            StateMachineService.transition_to(
                db, case, RecoveryCaseStatus.SEGMENTED.value, actor="SYSTEM", reason=f"Assigned canonical 4D segment '{segment.name}'"
            )

        db.add(AuditEvent(
            recovery_case_id=case.id,
            event_type="CASE_SEGMENTED",
            actor="SYSTEM",
            description=f"RecoveryCase assigned to canonical segment '{segment.name}'",
            details={
                "segment_id": segment.id,
                "segment_name": segment.name,
                "failure_category": segment.failure_category,
                "payment_method": segment.payment_method,
                "amount_range": segment.amount_range,
                "customer_type": segment.customer_type,
            },
        ))
        db.flush()
        return segment
