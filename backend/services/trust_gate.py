"""
Deterministic Trust Gate Service
Performs pre-policy checks for fraud risk, excessive failure velocity, and suspicious repeated activity.
"""

import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel
from backend.models.customer import Customer
from backend.models.transaction import Transaction
from backend.models.enums import CustomerType

logger = logging.getLogger(__name__)

class TrustGateResult(BaseModel):
    """Result of Trust Gate evaluation."""
    passed: bool
    suspicious_pattern_detected: bool
    reason: str
    details: Dict[str, Any] = {}

class TrustGateService:
    """Deterministic Trust Gate evaluating financial velocity & suspicious payment patterns."""

    @staticmethod
    def evaluate(
        transaction: Transaction,
        customer: Optional[Customer] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> TrustGateResult:
        """
        Evaluate Trust Gate checks:
        1. Customer fatigue check (CustomerType.FATIGUED or failed_transactions >= 5)
        2. High velocity failure check (multiple failures in short window)
        3. Suspicious metadata flags
        """
        ctx = context or {}

        # 1. Customer Fatigue & Excessive Failures Check
        if customer:
            if customer.customer_type == CustomerType.FATIGUED.value:
                return TrustGateResult(
                    passed=False,
                    suspicious_pattern_detected=True,
                    reason="Customer marked FATIGUED due to excessive recent payment failures",
                    details={"customer_id": customer.id, "failed_count": customer.failed_transactions},
                )
            if customer.failed_transactions >= 5 and customer.successful_transactions == 0:
                return TrustGateResult(
                    passed=False,
                    suspicious_pattern_detected=True,
                    reason="Excessive consecutive failures with zero successful transactions",
                    details={"customer_id": customer.id, "failed_count": customer.failed_transactions},
                )

        # 2. Velocity / Suspicious Flags in Context
        if ctx.get("is_flagged_suspicious"):
            return TrustGateResult(
                passed=False,
                suspicious_pattern_detected=True,
                reason="Context flagged for suspicious pattern or velocity spike",
                details=ctx,
            )

        return TrustGateResult(
            passed=True,
            suspicious_pattern_detected=False,
            reason="Trust Gate passed cleanly",
            details={},
        )
