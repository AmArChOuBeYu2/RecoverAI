"""
Core Recovery Domain Service
Handles recovery case initialization, action execution, and causal outcome attribution.
"""

import logging
from math import sqrt
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.models.customer import Customer
from backend.models.transaction import Transaction
from backend.models.recovery_case import RecoveryCase
from backend.models.recovery_action import RecoveryAction
from backend.models.recovery_strategy import RecoveryStrategy
from backend.models.strategy_outcome import StrategyOutcome
from backend.models.audit_event import AuditEvent
from backend.models.enums import (
    TransactionStatus,
    FailureCategory,
    RecoveryCaseStatus,
    DataCategory,
    OutcomeSource,
    ActionExecutionMode,
    ConfidenceLevel,
)
from backend.services.state_machine import StateMachineService
from backend.services.sanitization import sanitize_payload

logger = logging.getLogger(__name__)

def calculate_wilson_lower_bound(success_count: int, attempt_count: int, confidence: float = 1.96) -> float:
    """Calculate 95% Wilson score interval lower bound for small-sample statistical protection."""
    if attempt_count == 0:
        return 0.0
    p_hat = success_count / attempt_count
    n = attempt_count
    z = confidence
    denominator = 1 + z**2 / n
    centre_adjusted_probability = p_hat + z**2 / (2 * n)
    adjusted_standard_deviation = sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n)
    lower_bound = (centre_adjusted_probability - z * adjusted_standard_deviation) / denominator
    return max(0.0, float(lower_bound))

class RecoveryService:
    """Core domain service for recovery case creation, action execution, and causal attribution."""

    @staticmethod
    def process_failed_payment(db: Session, payment_data: Dict[str, Any]) -> RecoveryCase:
        """
        Ingest a payment.failed event:
        1. Find/create Customer
        2. Create Transaction (FAILED)
        3. Create RecoveryCase (DETECTED)
        """
        payment_id = payment_data.get("id")
        if not payment_id:
            raise ValueError("payment_id is required")

        # Idempotency check on transaction creation
        existing_txn = db.query(Transaction).filter_by(razorpay_payment_id=payment_id).first()
        if existing_txn and existing_txn.recovery_case:
            return existing_txn.recovery_case

        # Extract customer info
        email = payment_data.get("email")
        contact = payment_data.get("contact")
        customer = None
        if email or contact:
            customer = db.query(Customer).filter((Customer.email == email) | (Customer.phone == contact)).first()
            if not customer:
                customer = Customer(
                    email=email,
                    phone=contact,
                    name=payment_data.get("notes", {}).get("customer_name"),
                )
                db.add(customer)
                db.flush()

        # Create Transaction
        error_details = payment_data.get("error", {}) if isinstance(payment_data.get("error"), dict) else {}
        txn = Transaction(
            razorpay_payment_id=payment_id,
            razorpay_order_id=payment_data.get("order_id"),
            customer_id=customer.id if customer else None,
            amount_paise=payment_data.get("amount", 0),
            currency=payment_data.get("currency", "INR"),
            status=TransactionStatus.FAILED.value,
            failure_category=payment_data.get("failure_category") or FailureCategory.AUTHENTICATION_FAILURE.value,
            error_code=payment_data.get("error_code") or error_details.get("code"),
            error_description=payment_data.get("error_description") or error_details.get("description"),
            error_source=payment_data.get("error_source") or error_details.get("source"),
            error_step=payment_data.get("error_step") or error_details.get("step"),
            error_reason=payment_data.get("error_reason") or error_details.get("reason"),
            payment_method=payment_data.get("method"),
            data_source=DataCategory.OBSERVED.value,
        )
        db.add(txn)
        db.flush()

        # Create RecoveryCase
        case = RecoveryCase(
            transaction_id=txn.id,
            customer_id=customer.id if customer else None,
            status=RecoveryCaseStatus.DETECTED.value,
            attempt_count=0,
        )
        db.add(case)
        db.flush()

        # Audit event
        db.add(AuditEvent(
            recovery_case_id=case.id,
            event_type="CASE_DETECTED",
            actor="SYSTEM",
            description=f"Recovery case detected for failed payment {payment_id}",
            details=sanitize_payload(payment_data),
        ))
        db.flush()
        return case

    @staticmethod
    def record_recovery_action(
        db: Session,
        case: RecoveryCase,
        action_type: str,
        execution_mode: str = ActionExecutionMode.REAL_TEST_MODE.value,
        razorpay_payment_link_id: Optional[str] = None,
        payment_link_url: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> RecoveryAction:
        """Record an attempted recovery action (e.g. PAYMENT_LINK creation)."""
        action = RecoveryAction(
            recovery_case_id=case.id,
            action_type=action_type,
            execution_mode=execution_mode,
            razorpay_payment_link_id=razorpay_payment_link_id,
            payment_link_url=payment_link_url,
            status="SENT" if razorpay_payment_link_id else "PENDING",
            payload=sanitize_payload(payload or {}),
        )
        db.add(action)
        case.attempt_count += 1
        db.flush()
        return action

    @staticmethod
    def process_causal_attribution(
        db: Session,
        payment_link_id: Optional[str] = None,
        payment_id: Optional[str] = None,
        reference_id: Optional[str] = None,
        amount_recovered_paise: int = 0,
        raw_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        CAUSAL RECOVERY ATTRIBUTION INVARIANT ENGINE:
        Verifies the full causal chain:
        1. Find matching RecoveryAction by payment_link_id or reference_id.
        2. If NO matching RecoverAI action exists: Payment is UNATTRIBUTED (does NOT count as RecoverAI revenue).
        3. If matching action exists: Verify case status is not already RECOVERED.
        4. Transition state machine -> AWAITING_VERIFICATION -> RECOVERED.
        5. Create StrategyOutcome with outcome_source=VERIFIED.
        6. Recompute RecoveryStrategy metrics (attempt_count, success_count, total_recovered_paise, recovery_rate, wilson_lower_bound).
        """
        # Search for matching RecoverAI action
        action = None
        if payment_link_id:
            action = db.query(RecoveryAction).filter_by(razorpay_payment_link_id=payment_link_id).first()
        if not action and reference_id:
            action = db.query(RecoveryAction).filter_by(recovery_case_id=reference_id).first()

        # INVARIANT REQUIREMENT 5: If no attributable action exists, reject attribution!
        if not action:
            logger.info("Unattributed payment received (no matching RecoverAI action found). Not claiming revenue.")
            db.add(AuditEvent(
                event_type="UNATTRIBUTED_PAYMENT_RECEIVED",
                actor="RAZORPAY_WEBHOOK",
                description="Successful payment received without an attributable RecoverAI recovery action",
                details=sanitize_payload(raw_payload or {}),
            ))
            db.flush()
            return {
                "status": "unattributed",
                "claimed_by_recoverai": False,
                "reason": "No causal RecoverAI recovery action found for this payment",
            }

        case = action.recovery_case

        # INVARIANT REQUIREMENT 3 & 10: Already-recovered case protection
        if case.status == RecoveryCaseStatus.RECOVERED.value or case.is_terminal:
            logger.info(f"RecoveryCase '{case.id}' is already in terminal state RECOVERED. Ignoring duplicate attribution.")
            return {
                "status": "already_recovered",
                "claimed_by_recoverai": False,
                "case_id": case.id,
                "reason": "Recovery case is already marked as RECOVERED",
            }

        # Transition state machine safely through AWAITING_VERIFICATION -> RECOVERED
        if case.status == RecoveryCaseStatus.POLICY_APPROVED.value:
            StateMachineService.transition_to(db, case, RecoveryCaseStatus.ACTION_ATTEMPTED.value)

        if case.status == RecoveryCaseStatus.ACTION_ATTEMPTED.value:
            StateMachineService.transition_to(db, case, RecoveryCaseStatus.AWAITING_VERIFICATION.value)

        if case.status == RecoveryCaseStatus.AWAITING_VERIFICATION.value:
            StateMachineService.transition_to(db, case, RecoveryCaseStatus.RECOVERED.value)

        # Update action status
        action.status = "PAID"

        # Create StrategyOutcome record
        outcome = StrategyOutcome(
            recovery_case_id=case.id,
            segment_id=case.segment_id,
            strategy_type=action.action_type,
            outcome="RECOVERED",
            amount_recovered_paise=amount_recovered_paise or case.transaction.amount_paise,
            outcome_source=OutcomeSource.VERIFIED.value,
            attributed_at=datetime.now(timezone.utc),
        )
        db.add(outcome)
        db.flush()

        # Update RecoveryStrategy performance statistics if segment exists
        if case.segment_id:
            strat = db.query(RecoveryStrategy).filter_by(
                segment_id=case.segment_id, strategy_type=action.action_type
            ).first()
            if strat:
                strat.success_count += 1
                strat.total_recovered_paise += (amount_recovered_paise or case.transaction.amount_paise)
                if strat.attempt_count < strat.success_count:
                    strat.attempt_count = strat.success_count
                strat.recovery_rate = strat.success_count / strat.attempt_count if strat.attempt_count > 0 else 0.0
                strat.wilson_lower_bound = calculate_wilson_lower_bound(strat.success_count, strat.attempt_count)
                strat.sample_size_sufficient = (strat.attempt_count >= 10)
                if strat.attempt_count >= 100:
                    strat.confidence_level = ConfidenceLevel.HIGH.value
                elif strat.attempt_count >= 31:
                    strat.confidence_level = ConfidenceLevel.MEDIUM.value
                elif strat.attempt_count >= 10:
                    strat.confidence_level = ConfidenceLevel.LOW.value
                else:
                    strat.confidence_level = ConfidenceLevel.INSUFFICIENT.value

        db.add(AuditEvent(
            recovery_case_id=case.id,
            event_type="RECOVERY_ATTRIBUTED",
            actor="SYSTEM",
            description=f"Authoritative recovery attributed to strategy '{action.action_type}' (Amount: ₹{(amount_recovered_paise or case.transaction.amount_paise) / 100:.2f})",
            details=sanitize_payload(raw_payload or {}),
        ))
        db.flush()

        return {
            "status": "recovered",
            "claimed_by_recoverai": True,
            "case_id": case.id,
            "amount_paise": amount_recovered_paise or case.transaction.amount_paise,
            "strategy": action.action_type,
        }
