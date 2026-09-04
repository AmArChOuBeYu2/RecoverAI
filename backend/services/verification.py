"""
Verification Service — RecoverAI Milestone 15
Verifies action outcomes for recovery cases using Razorpay Test Mode API for REAL actions
and segment-specific empirical conversion rates for SIMULATED actions.
"""

import logging
import hashlib
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from backend.models.recovery_case import RecoveryCase
from backend.models.recovery_action import RecoveryAction
from backend.models.enums import (
    ActionExecutionMode,
    OutcomeSource,
    FailureCategory,
    StrategyType,
)
from backend.integrations.razorpay.payment_links import RazorpayPaymentLinkService
from backend.integrations.razorpay.exceptions import RazorpayIntegrationError

logger = logging.getLogger(__name__)

# Simulated recovery conversion probability by Failure Category
SIMULATED_CONVERSION_RATES: Dict[str, float] = {
    FailureCategory.AUTHENTICATION_FAILURE.value: 0.45,
    FailureCategory.BANK_TIMEOUT.value: 0.65,
    FailureCategory.NETWORK_FAILURE.value: 0.65,
    FailureCategory.INSUFFICIENT_FUNDS.value: 0.15,
    FailureCategory.CHECKOUT_ABANDONMENT.value: 0.30,
    FailureCategory.REPEATED_FAILURE.value: 0.10,
    FailureCategory.BUSINESS_ERROR.value: 0.05,
    FailureCategory.UNKNOWN.value: 0.20,
}

class VerificationResult:
    """Structured result returned by VerificationService."""
    def __init__(
        self,
        case_id: str,
        action_id: str,
        outcome: str, # RECOVERED, NOT_RECOVERED, PENDING
        amount_recovered_paise: int,
        outcome_source: str, # VERIFIED, SIMULATED
        details: Dict[str, Any],
    ):
        self.case_id = case_id
        self.action_id = action_id
        self.outcome = outcome
        self.amount_recovered_paise = amount_recovered_paise
        self.outcome_source = outcome_source
        self.details = details

class VerificationService:
    """
    Verification engine evaluating recovery action outcomes.
    
    Rules:
    1. Payment Link creation is an ACTION, NOT RECOVERY.
    2. REAL_TEST_MODE actions are verified strictly via Razorpay API (VERIFIED outcome).
    3. SIMULATED actions are evaluated via deterministic segment conversion rates (SIMULATED outcome).
    """

    def __init__(self, payment_link_service: Optional[RazorpayPaymentLinkService] = None):
        self.payment_link_service = payment_link_service or RazorpayPaymentLinkService()

    @classmethod
    def get_simulated_conversion_probability(cls, failure_category: Optional[str]) -> float:
        """Get baseline simulated conversion rate for a failure category."""
        if not failure_category:
            return 0.20
        return SIMULATED_CONVERSION_RATES.get(failure_category, 0.20)

    @classmethod
    def determine_simulated_outcome(cls, case: RecoveryCase, action: RecoveryAction) -> bool:
        """
        Determines simulated recovery outcome deterministically based on case transaction ID,
        amount, action ID, and segment failure category.
        """
        fc = case.transaction.failure_category if case.transaction else FailureCategory.UNKNOWN.value
        probability = cls.get_simulated_conversion_probability(fc)

        # Deterministic seed hashing: SHA256 of case.id + action.id
        seed_str = f"{case.id}:{action.id}:{case.transaction_id if case.transaction else ''}"
        hash_val = int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16)
        normalized_val = (hash_val % 10000) / 10000.0 # float between 0.0000 and 0.9999

        return normalized_val < probability

    def verify_action_outcome(
        self,
        db: Session,
        case: RecoveryCase,
        action: RecoveryAction,
    ) -> VerificationResult:
        """
        Verify the outcome of a specific attempted RecoveryAction.
        
        For REAL_TEST_MODE:
        - Call Razorpay API to fetch payment link status.
        - 'paid' -> RECOVERED (VERIFIED)
        - 'expired' / 'cancelled' -> NOT_RECOVERED (VERIFIED)
        - 'created' / 'partially_paid' -> PENDING
        
        For SIMULATED:
        - Apply deterministic segment conversion rate -> RECOVERED or NOT_RECOVERED (SIMULATED).
        """
        txn_amount = case.transaction.amount_paise if case.transaction else 0

        # 1. REAL TEST MODE VERIFICATION
        if action.execution_mode == ActionExecutionMode.REAL_TEST_MODE.value and action.razorpay_payment_link_id:
            try:
                link_res = self.payment_link_service.fetch_payment_link(action.razorpay_payment_link_id)
                status = link_res.status.lower()

                if status == "paid":
                    return VerificationResult(
                        case_id=case.id,
                        action_id=action.id,
                        outcome="RECOVERED",
                        amount_recovered_paise=link_res.amount_paise or txn_amount,
                        outcome_source=OutcomeSource.VERIFIED.value,
                        details={
                            "razorpay_status": status,
                            "razorpay_payment_link_id": link_res.id,
                            "verified_via": "RAZORPAY_API",
                        },
                    )
                elif status in ("expired", "cancelled"):
                    return VerificationResult(
                        case_id=case.id,
                        action_id=action.id,
                        outcome="NOT_RECOVERED",
                        amount_recovered_paise=0,
                        outcome_source=OutcomeSource.VERIFIED.value,
                        details={
                            "razorpay_status": status,
                            "razorpay_payment_link_id": link_res.id,
                            "verified_via": "RAZORPAY_API",
                        },
                    )
                else:
                    return VerificationResult(
                        case_id=case.id,
                        action_id=action.id,
                        outcome="PENDING",
                        amount_recovered_paise=0,
                        outcome_source=OutcomeSource.VERIFIED.value,
                        details={
                            "razorpay_status": status,
                            "razorpay_payment_link_id": link_res.id,
                            "verified_via": "RAZORPAY_API",
                        },
                    )
            except Exception as e:
                logger.error(f"Failed to fetch Razorpay payment link '{action.razorpay_payment_link_id}' for verification: {e}")
                return VerificationResult(
                    case_id=case.id,
                    action_id=action.id,
                    outcome="PENDING",
                    amount_recovered_paise=0,
                    outcome_source=OutcomeSource.VERIFIED.value,
                    details={"error": str(e), "razorpay_payment_link_id": action.razorpay_payment_link_id},
                )

        # 2. DELAYED RETRY & SCHEDULED ACTIONS
        if action.action_type == StrategyType.DELAYED_RETRY.value or action.status == "SCHEDULED":
            return VerificationResult(
                case_id=case.id,
                action_id=action.id,
                outcome="PENDING",
                amount_recovered_paise=0,
                outcome_source=OutcomeSource.SIMULATED.value,
                details={"reason": "Delayed retry is scheduled for future execution; outcome pending"},
            )

        # 3. ESCALATION & HUMAN REVIEW ACTIONS
        if action.action_type in (StrategyType.ESCALATION.value, StrategyType.HUMAN_REVIEW.value):
            return VerificationResult(
                case_id=case.id,
                action_id=action.id,
                outcome="PENDING",
                amount_recovered_paise=0,
                outcome_source=OutcomeSource.SIMULATED.value,
                details={"reason": "Case requires human review or escalation; outcome pending"},
            )

        # 4. SIMULATED MODE VERIFICATION FOR COMPLETED / IMMEDIATE ACTIONS
        is_sim_success = self.determine_simulated_outcome(case, action)
        if is_sim_success:
            return VerificationResult(
                case_id=case.id,
                action_id=action.id,
                outcome="RECOVERED",
                amount_recovered_paise=txn_amount,
                outcome_source=OutcomeSource.SIMULATED.value,
                details={
                    "simulation_label": "SIMULATED_CONVERSION_SUCCESS",
                    "failure_category": case.transaction.failure_category if case.transaction else "UNKNOWN",
                    "conversion_probability": self.get_simulated_conversion_probability(case.transaction.failure_category if case.transaction else None),
                },
            )
        else:
            return VerificationResult(
                case_id=case.id,
                action_id=action.id,
                outcome="NOT_RECOVERED",
                amount_recovered_paise=0,
                outcome_source=OutcomeSource.SIMULATED.value,
                details={
                    "simulation_label": "SIMULATED_CONVERSION_FAILURE",
                    "failure_category": case.transaction.failure_category if case.transaction else "UNKNOWN",
                    "conversion_probability": self.get_simulated_conversion_probability(case.transaction.failure_category if case.transaction else None),
                },
            )
