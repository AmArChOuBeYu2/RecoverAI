"""
Deterministic Strategy Ranker & Comparator for RecoverAI
Ranks candidate recovery strategies by combining Statistical Confidence (Wilson Lower Bound)
and Economic Strategy Value (expected recovered paise per attempt after friction/burden penalties).
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.services.fallback_engine import FallbackEngine
from backend.models.enums import StrategyType, ConfidenceLevel, RecommendationType

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

TIER_WEIGHTS = {
    ConfidenceLevel.HIGH.value: 1.00,
    ConfidenceLevel.MEDIUM.value: 0.95,
    ConfidenceLevel.LOW.value: 0.85,
    ConfidenceLevel.INSUFFICIENT.value: 0.50,
}

STRATEGY_BURDEN_PENALTY_FACTORS = {
    StrategyType.PAYMENT_LINK.value: 1.00,  # Standard direct recovery link
    StrategyType.DELAYED_RETRY.value: 0.95, # Low friction, minor gateway load
    StrategyType.METHOD_SWITCH.value: 0.90, # Moderate customer effort
    StrategyType.REMINDER.value: 0.85,      # Customer contact friction, minor fatigue risk
    StrategyType.NO_ACTION.value: 1.00,     # Zero contact burden
}

class StrategyRanker:
    """Ranks and compares candidate strategies deterministically balancing probability & economic value."""

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
        Compare candidate strategies, compute Statistical Confidence (Wilson LB) and Economic Strategy Value (Paise),
        and rank them deterministically.
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

            # Calculate Economic Strategy Value (Paise per attempt)
            avg_txn_paise = perf.get("avg_transaction_amount_paise", 100000)
            wilson_lb = perf["wilson_lower_bound"]
            expected_recovered_paise = perf.get("expected_recovered_paise_per_attempt", int(round(wilson_lb * avg_txn_paise)))

            burden_factor = STRATEGY_BURDEN_PENALTY_FACTORS.get(strat, 1.00)
            tier_weight = TIER_WEIGHTS.get(perf["sample_size_tier"], 0.50)

            economic_value_score = round(expected_recovered_paise * burden_factor * tier_weight, 2)

            evaluated_strategies.append({
                "strategy_type": strat,
                "attempt_count": perf["attempt_count"],
                "success_count": perf["success_count"],
                "total_recovered_paise": perf["total_recovered_paise"],
                "avg_transaction_amount_paise": avg_txn_paise,
                "avg_recovered_paise_per_attempt": perf.get("avg_recovered_paise_per_attempt", 0.0),
                "expected_recovered_paise_per_attempt": expected_recovered_paise,
                "burden_penalty_factor": burden_factor,
                "economic_strategy_value_score": economic_value_score,
                "recovery_rate": perf["recovery_rate"],
                "wilson_lower_bound": wilson_lb,
                "sample_size_tier": perf["sample_size_tier"],
                "confidence_level": perf["confidence_level"],
                "sample_size_sufficient": perf["sample_size_sufficient"],
                "evidence_category": perf.get("evidence_category", "OBSERVED"),
                "evidence_provenance": perf.get("evidence_provenance", "SYNTHETIC"),
                "evidence_source": perf.get("evidence_source", "OBSERVED:SYNTHETIC"),
                "fallback_level": trace["fallback_level"],
                "fallback_occurred": trace["fallback_occurred"],
                "fallback_reason": trace["fallback_reason"],
                "recommendation_type": trace.get("recommendation_type", RecommendationType.OPTIMIZED_RECOMMENDATION.value),
                "evidence_status": trace.get("evidence_status", "SUFFICIENT_EVIDENCE"),
                "strategy_source": trace.get("strategy_source", "CANONICAL_4D_EVIDENCE"),
                "evidence_trace": trace,
            })

        # Deterministic Ranking Rule:
        # 1. Primary: Sample Size Tier precedence (HIGH > MEDIUM > LOW > INSUFFICIENT)
        # 2. Secondary: Economic Strategy Value Score (descending expected monetary recovery in paise)
        # 3. Tertiary: Wilson Lower Bound (descending statistical probability)
        # 4. Quaternary: Strategy Name (alphabetical tie-breaker)
        def sort_key(item: Dict[str, Any]):
            tier_val = TIER_PRECEDENCE.get(item["sample_size_tier"], 0)
            return (
                tier_val,
                item["economic_strategy_value_score"],
                item["wilson_lower_bound"],
                item["strategy_type"],
            )

        ranked = sorted(evaluated_strategies, key=sort_key, reverse=True)
        winner = ranked[0]

        is_baseline = winner["recommendation_type"] == RecommendationType.BASELINE_RECOMMENDATION.value
        rec_type = RecommendationType.BASELINE_RECOMMENDATION.value if is_baseline else RecommendationType.OPTIMIZED_RECOMMENDATION.value

        # Generate Human-Readable Rationale
        if is_baseline:
            rationale = (
                f"BASELINE_RECOMMENDATION: Selected default strategy '{winner['strategy_type']}' "
                f"because historical segment evidence is INSUFFICIENT (<10 attempts). "
                f"Requires Policy Engine and Trust Gate authorization."
            )
        elif winner["fallback_occurred"]:
            rationale = (
                f"OPTIMIZED_RECOMMENDATION: Recommended strategy '{winner['strategy_type']}' "
                f"with Economic Value Score {winner['economic_strategy_value_score']} paise/attempt "
                f"(Wilson LB {winner['wilson_lower_bound']:.1%}) utilizing {winner['fallback_level']} evidence."
            )
        else:
            rationale = (
                f"OPTIMIZED_RECOMMENDATION: Recommended strategy '{winner['strategy_type']}' "
                f"with Economic Value Score {winner['economic_strategy_value_score']} paise/attempt "
                f"(Wilson LB {winner['wilson_lower_bound']:.1%}, expected recovery ₹{winner['expected_recovered_paise_per_attempt']/100:.2f}/attempt) "
                f"based on canonical 4D segment evidence."
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
            "recommendation_type": rec_type,
            "evidence_status": winner["evidence_status"],
            "strategy_source": winner["strategy_source"],
            "recommended_strategy": winner["strategy_type"],
            "recommendation_rationale": rationale,
            "winner_performance": winner,
            "ranked_strategies": ranked,
        }
