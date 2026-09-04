"""
Deterministic Strategy Ranker & Comparator for RecoverAI
Ranks candidate recovery strategies using sample-size confidence tiers, Wilson score lower bounds,
and fallback traces. Resolves ties deterministically and avoids naive conversion rate traps.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.services.fallback_engine import FallbackEngine
from backend.models.enums import StrategyType, ConfidenceLevel

CANDIDATE_STRATEGIES = [
    StrategyType.PAYMENT_LINK.value,
    StrategyType.DELAYED_RETRY.value,
    StrategyType.REMINDER.value,
    StrategyType.METHOD_SWITCH.value,
    StrategyType.NO_ACTION.value,
]

TIER_PRECEDENCE = {
    ConfidenceLevel.HIGH.value: 4,
    ConfidenceLevel.MEDIUM.value: 3,
    ConfidenceLevel.LOW.value: 2,
    ConfidenceLevel.INSUFFICIENT.value: 1,
}

class StrategyRanker:
    """Ranks and compares candidate strategies deterministically using statistical lower bounds."""

    @staticmethod
    def compare_and_rank_strategies(
        outcomes: List[Dict[str, Any]],
        failure_category: str,
        payment_method: Optional[str],
        amount_range: str,
        customer_type: Optional[str],
        as_of_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Compare all candidate strategies for a payment context, apply fallback hierarchy,
        compute Wilson score lower bounds, and rank them deterministically.
        """
        evaluated_strategies = []

        for strat in CANDIDATE_STRATEGIES:
            eval_res = FallbackEngine.evaluate_strategy_with_fallback(
                outcomes,
                failure_category,
                payment_method,
                amount_range,
                customer_type,
                strat,
                as_of_time,
            )
            perf = eval_res["performance"]
            trace = eval_res["evidence_trace"]

            evaluated_strategies.append({
                "strategy_type": strat,
                "attempt_count": perf["attempt_count"],
                "success_count": perf["success_count"],
                "total_recovered_paise": perf["total_recovered_paise"],
                "recovery_rate": perf["recovery_rate"],
                "wilson_lower_bound": perf["wilson_lower_bound"],
                "sample_size_tier": perf["sample_size_tier"],
                "confidence_level": perf["confidence_level"],
                "sample_size_sufficient": perf["sample_size_sufficient"],
                "evidence_source": perf["evidence_source"],
                "fallback_level": trace["fallback_level"],
                "fallback_occurred": trace["fallback_occurred"],
                "fallback_reason": trace["fallback_reason"],
                "evidence_trace": trace,
            })

        # Deterministic Ranking Rule:
        # 1. Primary: Sample Size Tier precedence (HIGH > MEDIUM > LOW > INSUFFICIENT)
        # 2. Secondary: Wilson Lower Bound (descending)
        # 3. Tertiary: Success Count (descending)
        # 4. Quaternary: Strategy Name (alphabetical for deterministic tie-breaker)
        def sort_key(item: Dict[str, Any]):
            tier_val = TIER_PRECEDENCE.get(item["sample_size_tier"], 0)
            return (
                tier_val,
                item["wilson_lower_bound"],
                item["success_count"],
                item["strategy_type"],
            )

        ranked = sorted(evaluated_strategies, key=sort_key, reverse=True)
        winner = ranked[0]

        # Generate Human-Readable Rationale
        if winner["fallback_level"] == "GLOBAL_SAFE_DEFAULT":
            rationale = (
                f"Recommended strategy '{winner['strategy_type']}' based on global safe defaults "
                f"because canonical and aggregate segment evidence is INSUFFICIENT (<10 attempts)."
            )
        elif winner["fallback_occurred"]:
            rationale = (
                f"Recommended strategy '{winner['strategy_type']}' with Wilson lower bound {winner['wilson_lower_bound']:.1%} "
                f"utilizing {winner['fallback_level']} evidence ({winner['attempt_count']} attempts, {winner['success_count']} recoveries)."
            )
        else:
            rationale = (
                f"Recommended strategy '{winner['strategy_type']}' with highest conservative Wilson lower bound "
                f"{winner['wilson_lower_bound']:.1%} based on canonical 4D segment evidence "
                f"({winner['attempt_count']} attempts, {winner['success_count']} recoveries, rate {winner['recovery_rate']:.1%})."
            )

        method_str = payment_method.lower() if payment_method else "any"
        cust_str = customer_type.lower() if customer_type else "any"
        canonical_name = f"{failure_category.lower()}_{method_str}_{amount_range.lower()}_{cust_str}"

        return {
            "segment_name": canonical_name,
            "failure_category": failure_category,
            "payment_method": payment_method,
            "amount_range": amount_range,
            "customer_type": customer_type,
            "recommended_strategy": winner["strategy_type"],
            "recommendation_rationale": rationale,
            "winner_performance": winner,
            "ranked_strategies": ranked,
        }
