"""
Hierarchical Fallback Engine for RecoverAI
Executes the approved fallback hierarchy when 4D canonical segment evidence is insufficient (<10 txns):
4D Canonical -> 3D Aggregate -> Failure Category Baseline -> Global Safe Default / Insufficient Evidence.
Generates structured, step-by-step EvidenceTrace records with cold-start baseline labels.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.services.strategy_aggregator import StrategyAggregator
from backend.models.enums import StrategyType, FailureCategory, ConfidenceLevel, DataCategory, EvidenceProvenance, RecommendationType

DEFAULT_SAFE_STRATEGIES = {
    FailureCategory.AUTHENTICATION_FAILURE.value: StrategyType.PAYMENT_LINK.value,
    FailureCategory.BANK_TIMEOUT.value: StrategyType.DELAYED_RETRY.value,
    FailureCategory.NETWORK_FAILURE.value: StrategyType.DELAYED_RETRY.value,
    FailureCategory.CHECKOUT_ABANDONMENT.value: StrategyType.PAYMENT_LINK.value,
    FailureCategory.INSUFFICIENT_FUNDS.value: StrategyType.REMINDER.value,
    FailureCategory.REPEATED_FAILURE.value: StrategyType.NO_ACTION.value,
    FailureCategory.UNKNOWN.value: StrategyType.PAYMENT_LINK.value,
}

class FallbackEngine:
    """Executes multi-level evidence fallback and logs complete evidence traces."""

    @staticmethod
    def evaluate_strategy_with_fallback(
        outcomes: List[Dict[str, Any]],
        failure_category: str,
        payment_method: Optional[str],
        amount_range: str,
        customer_type: Optional[str],
        strategy_type: str,
        as_of_time: Optional[datetime] = None,
        min_sample_size: int = 10,
    ) -> Dict[str, Any]:
        """
        Evaluate strategy evidence through the 4-level fallback hierarchy.
        Returns aggregate stats plus evidence trace with cold-start baseline semantics.
        """
        from backend.services.segmentation import SegmentationService
        canonical_4d_name = SegmentationService.derive_canonical_segment_name(
            failure_category, payment_method, amount_range, customer_type
        )
        method_str = payment_method.lower() if payment_method else "any"
        aggregate_3d_prefix = f"{failure_category.lower()}_{method_str}_{amount_range.lower()}_"
        
        trace_steps = []

        # Level 1: 4D Canonical Segment
        l1_stats = StrategyAggregator.aggregate_from_outcomes_list(
            outcomes, canonical_4d_name, strategy_type, as_of_time
        )
        trace_steps.append({
            "level": "4D_CANONICAL",
            "segment_name": canonical_4d_name,
            "attempts": l1_stats["attempt_count"],
            "sufficient": l1_stats["attempt_count"] >= min_sample_size,
        })

        if l1_stats["attempt_count"] >= min_sample_size:
            return {
                "performance": l1_stats,
                "evidence_trace": {
                    "requested_segment": canonical_4d_name,
                    "fallback_level": "4D_CANONICAL",
                    "fallback_occurred": False,
                    "fallback_reason": None,
                    "effective_segment_name": canonical_4d_name,
                    "recommendation_type": RecommendationType.OPTIMIZED_RECOMMENDATION.value,
                    "evidence_status": "SUFFICIENT_EVIDENCE",
                    "strategy_source": "CANONICAL_4D_EVIDENCE",
                    "trace_steps": trace_steps,
                }
            }

        # Level 2: 3D Aggregate Segment (ignoring customer_type)
        l2_outcomes = [
            o for o in outcomes
            if o.get("segment_name", "").startswith(aggregate_3d_prefix)
            and o.get("strategy_type") == strategy_type
        ]
        l2_stats = StrategyAggregator.aggregate_from_outcomes_list(
            l2_outcomes, None, strategy_type, as_of_time
        )
        l2_stats["segment_name"] = aggregate_3d_prefix + "all"
        
        trace_steps.append({
            "level": "3D_AGGREGATE",
            "segment_prefix": aggregate_3d_prefix,
            "attempts": l2_stats["attempt_count"],
            "sufficient": l2_stats["attempt_count"] >= min_sample_size,
        })

        if l2_stats["attempt_count"] >= min_sample_size:
            l2_stats["evidence_source"] = f"{l2_stats['evidence_source']} (FALLBACK_3D)"
            return {
                "performance": l2_stats,
                "evidence_trace": {
                    "requested_segment": canonical_4d_name,
                    "fallback_level": "3D_AGGREGATE",
                    "fallback_occurred": True,
                    "fallback_reason": f"4D sample size ({l1_stats['attempt_count']}) < threshold ({min_sample_size})",
                    "effective_segment_name": aggregate_3d_prefix + "all",
                    "recommendation_type": RecommendationType.OPTIMIZED_RECOMMENDATION.value,
                    "evidence_status": "SUFFICIENT_EVIDENCE",
                    "strategy_source": "AGGREGATE_3D_EVIDENCE",
                    "trace_steps": trace_steps,
                }
            }

        # Level 3: Failure Category Baseline (ignoring method, amount, customer_type)
        l3_outcomes = [
            o for o in outcomes
            if o.get("segment_name", "").startswith(failure_category.lower())
            and o.get("strategy_type") == strategy_type
        ]
        l3_stats = StrategyAggregator.aggregate_from_outcomes_list(
            l3_outcomes, None, strategy_type, as_of_time
        )
        l3_stats["segment_name"] = failure_category.lower() + "_baseline"

        trace_steps.append({
            "level": "FAILURE_CATEGORY_BASELINE",
            "failure_category": failure_category,
            "attempts": l3_stats["attempt_count"],
            "sufficient": l3_stats["attempt_count"] >= min_sample_size,
        })

        if l3_stats["attempt_count"] >= min_sample_size:
            l3_stats["evidence_source"] = f"{l3_stats['evidence_source']} (FALLBACK_FAILURE_CATEGORY)"
            return {
                "performance": l3_stats,
                "evidence_trace": {
                    "requested_segment": canonical_4d_name,
                    "fallback_level": "FAILURE_CATEGORY_BASELINE",
                    "fallback_occurred": True,
                    "fallback_reason": f"3D aggregate sample size ({l2_stats['attempt_count']}) < threshold ({min_sample_size})",
                    "effective_segment_name": failure_category.lower() + "_baseline",
                    "recommendation_type": RecommendationType.OPTIMIZED_RECOMMENDATION.value,
                    "evidence_status": "SUFFICIENT_EVIDENCE",
                    "strategy_source": "CATEGORY_BASELINE_EVIDENCE",
                    "trace_steps": trace_steps,
                }
            }

        # Level 4: Cold-Start Baseline / Insufficient Evidence
        safe_strategy = DEFAULT_SAFE_STRATEGIES.get(failure_category, StrategyType.PAYMENT_LINK.value)
        l4_stats = {
            "segment_name": canonical_4d_name,
            "strategy_type": strategy_type,
            "attempt_count": l1_stats["attempt_count"],
            "success_count": l1_stats["success_count"],
            "total_recovered_paise": l1_stats["total_recovered_paise"],
            "avg_transaction_amount_paise": 100000,
            "avg_recovered_paise_per_attempt": 0.0,
            "expected_recovered_paise_per_attempt": 0,
            "recovery_rate": l1_stats["recovery_rate"],
            "wilson_lower_bound": l1_stats["wilson_lower_bound"],
            "sample_size_tier": ConfidenceLevel.INSUFFICIENT.value,
            "confidence_level": ConfidenceLevel.INSUFFICIENT.value,
            "sample_size_sufficient": False,
            "evidence_category": DataCategory.OBSERVED.value,
            "evidence_provenance": EvidenceProvenance.SYNTHETIC.value,
            "evidence_source": "GLOBAL_SAFE_DEFAULT",
            "is_safe_default": strategy_type == safe_strategy,
        }
        trace_steps.append({
            "level": "GLOBAL_SAFE_DEFAULT",
            "safe_default_strategy": safe_strategy,
            "attempts": l1_stats["attempt_count"],
            "sufficient": False,
        })

        return {
            "performance": l4_stats,
            "evidence_trace": {
                "requested_segment": canonical_4d_name,
                "fallback_level": "GLOBAL_SAFE_DEFAULT",
                "fallback_occurred": True,
                "fallback_reason": "No adequate historical evidence available; relying on deterministic baseline strategy.",
                "effective_segment_name": "global_safe_default",
                "recommendation_type": RecommendationType.BASELINE_RECOMMENDATION.value,
                "evidence_status": "INSUFFICIENT_EVIDENCE",
                "strategy_source": "DETERMINISTIC_BASELINE",
                "trace_steps": trace_steps,
            }
        }
