"""
Transparent Recoverability Scorer for RecoverAI
Calculates explainable, deterministic propensity scores R in [0.0, 1.0] for payment recovery potential,
exposing granular positive and negative factor contributions.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.models.enums import FailureCategory, CustomerType

BASE_RECOVERABILITY = {
    FailureCategory.AUTHENTICATION_FAILURE.value: 0.65,
    FailureCategory.BANK_TIMEOUT.value: 0.70,
    FailureCategory.NETWORK_FAILURE.value: 0.68,
    FailureCategory.CHECKOUT_ABANDONMENT.value: 0.55,
    FailureCategory.INSUFFICIENT_FUNDS.value: 0.35,
    FailureCategory.REPEATED_FAILURE.value: 0.20,
    FailureCategory.UNKNOWN.value: 0.40,
}

class RecoverabilityScorer:
    """Computes transparent recoverability propensity scores with detailed factor breakdowns."""

    @staticmethod
    def calculate_recoverability_score(transaction: Dict[str, Any], customer: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate deterministic recoverability score R in [0.0, 1.0] for a transaction.
        Returns score and list of positive/negative factor contributions.
        """
        failure_cat = transaction.get("failure_category", FailureCategory.UNKNOWN.value)
        base_score = BASE_RECOVERABILITY.get(failure_cat, 0.40)
        
        factors: List[Dict[str, Any]] = []
        factors.append({
            "name": "base_failure_category",
            "contribution": base_score,
            "description": f"Base recoverability for {failure_cat} ({int(base_score*100)}%)",
        })

        current_score = base_score

        # 1. Recency Factor (Time since failure)
        failed_at_str = transaction.get("failed_at") or transaction.get("created_at")
        if failed_at_str:
            try:
                failed_dt = datetime.fromisoformat(failed_at_str)
                if failed_dt.tzinfo is None:
                    failed_dt = failed_dt.replace(tzinfo=timezone.utc)
                
                now = datetime.now(timezone.utc)
                hours_since = (now - failed_dt).total_seconds() / 3600.0

                if hours_since <= 1.0:
                    current_score += 0.10
                    factors.append({
                        "name": "recency_bonus_1h",
                        "contribution": +0.10,
                        "description": "Failure occurred less than 1 hour ago (+10%)",
                    })
                elif hours_since <= 6.0:
                    current_score += 0.05
                    factors.append({
                        "name": "recency_bonus_6h",
                        "contribution": +0.05,
                        "description": "Failure occurred between 1 and 6 hours ago (+5%)",
                    })
                elif hours_since > 24.0:
                    current_score -= 0.10
                    factors.append({
                        "name": "recency_penalty_24h",
                        "contribution": -0.10,
                        "description": "Failure is older than 24 hours (-10%)",
                    })
            except (ValueError, TypeError):
                pass

        # 2. Customer Type Factor
        cust_type = transaction.get("customer_type") or (customer.get("customer_type") if customer else None)
        if cust_type == CustomerType.RETURNING.value:
            current_score += 0.08
            factors.append({
                "name": "customer_type_returning",
                "contribution": +0.08,
                "description": "Returning customer with historical success (+8%)",
            })
        elif cust_type == CustomerType.FATIGUED.value:
            current_score -= 0.15
            factors.append({
                "name": "customer_type_fatigued",
                "contribution": -0.15,
                "description": "Fatigued customer with recent failure history (-15%)",
            })

        # 3. Attempt Count Penalty
        attempt_count = transaction.get("attempt_count", 0)
        if attempt_count == 1:
            current_score -= 0.05
            factors.append({
                "name": "attempt_count_1",
                "contribution": -0.05,
                "description": "1 previous attempt failed (-5%)",
            })
        elif attempt_count >= 2:
            current_score -= 0.18
            factors.append({
                "name": "attempt_count_multiple",
                "contribution": -0.18,
                "description": f"Multiple previous attempts ({attempt_count}) failed (-18%)",
            })

        # 4. 24h Contact Fatigue Penalty
        contacts_24h = customer.get("contacts_count_24h", 0) if customer else 0
        if contacts_24h >= 3:
            current_score -= 0.15
            factors.append({
                "name": "high_contact_fatigue",
                "contribution": -0.15,
                "description": f"High recent contact count ({contacts_24h} in 24h) (-15%)",
            })

        # 5. High Amount Penalty (> ₹50,000 paise)
        amount_paise = transaction.get("amount_paise", 0)
        if amount_paise > 5000000:
            current_score -= 0.10
            factors.append({
                "name": "high_amount_penalty",
                "contribution": -0.10,
                "description": "Transaction amount exceeds ₹50,000 threshold (-10%)",
            })

        final_score = max(0.01, min(0.99, round(current_score, 4)))

        return {
            "transaction_id": transaction.get("id"),
            "recoverability_score": final_score,
            "score_category": "HIGH" if final_score >= 0.70 else ("MEDIUM" if final_score >= 0.40 else "LOW"),
            "factors": factors,
        }
