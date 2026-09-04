"""
Portfolio Intelligence & Revenue-at-Risk Engine for RecoverAI
Computes portfolio-level revenue at risk, eligible revenue, recoverability-weighted opportunity,
and segment-level evidence distributions.
"""

from collections import Counter
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.services.recoverability_scorer import RecoverabilityScorer
from backend.services.wilson_score import derive_sample_size_tier

class PortfolioIntelligenceService:
    """Computes portfolio-level revenue at risk, opportunity matrices, and segment metrics."""

    @staticmethod
    def calculate_portfolio_metrics(
        transactions: List[Dict[str, Any]],
        outcomes: List[Dict[str, Any]],
        customers_map: Optional[Dict[str, Dict[str, Any]]] = None,
        as_of_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Calculate deterministic portfolio revenue metrics in integer paise.
        """
        customers_map = customers_map or {}
        
        # Filter transactions chronologically if as_of_time is provided
        valid_txns = []
        for t in transactions:
            if as_of_time is not None:
                t_dt = datetime.fromisoformat(t["created_at"])
                if t_dt > as_of_time:
                    continue
            valid_txns.append(t)

        total_txns = len(valid_txns)
        total_revenue_at_risk = sum(t.get("amount_paise", 0) for t in valid_txns)

        # Eligible revenue filter: amount <= ₹50,000 paise (5,000,000 paise) and not REPEATED_FAILURE
        eligible_txns = [
            t for t in valid_txns
            if t.get("amount_paise", 0) <= 5000000 and t.get("failure_category") != "REPEATED_FAILURE"
        ]
        eligible_revenue = sum(t.get("amount_paise", 0) for t in eligible_txns)

        # Recoverability-weighted projected recoverable revenue
        projected_recoverable_paise = 0
        segment_txns_counter = Counter(t.get("segment_name", "unknown") for t in valid_txns)
        segment_amounts_counter = Counter()

        for t in valid_txns:
            cust_id = t.get("customer_id")
            cust = customers_map.get(cust_id) if cust_id else None
            rec_res = RecoverabilityScorer.calculate_recoverability_score(t, cust)
            score = rec_res["recoverability_score"]
            amt = t.get("amount_paise", 0)
            projected = int(round(amt * score))
            projected_recoverable_paise += projected

            seg_name = t.get("segment_name", "unknown")
            segment_amounts_counter[seg_name] += amt

        # Aggregate sample-size tiers across segments
        tier_counts = {"INSUFFICIENT": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0}
        segment_profiles = []

        for seg_name, count in segment_txns_counter.items():
            tier = derive_sample_size_tier(count)
            tier_counts[tier] += 1

            seg_amount = segment_amounts_counter[seg_name]
            segment_profiles.append({
                "segment_name": seg_name,
                "transaction_count": count,
                "revenue_at_risk_paise": seg_amount,
                "sample_size_tier": tier,
            })

        # Rank segments by revenue at risk
        segment_profiles.sort(key=lambda s: s["revenue_at_risk_paise"], reverse=True)

        return {
            "total_transactions": total_txns,
            "total_revenue_at_risk_paise": total_revenue_at_risk,
            "eligible_transactions": len(eligible_txns),
            "eligible_revenue_paise": eligible_revenue,
            "projected_recoverable_revenue_paise": projected_recoverable_paise,
            "overall_projected_recovery_rate": round(projected_recoverable_paise / total_revenue_at_risk, 4) if total_revenue_at_risk > 0 else 0.0,
            "sample_size_tiers": tier_counts,
            "total_canonical_segments": len(segment_txns_counter),
            "top_opportunity_segments": segment_profiles[:10],
        }
