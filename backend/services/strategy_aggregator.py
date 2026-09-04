"""
Strategy Performance Aggregator for RecoverAI
Aggregates observed historical strategy outcomes into segment-level metrics with
temporal cutoff filtering, source-category separation, and Wilson score calculation.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.models import StrategyOutcome, DataCategory
from backend.services.wilson_score import (
    calculate_wilson_lower_bound,
    derive_sample_size_tier,
    derive_confidence_level,
)

class StrategyAggregator:
    """Aggregates strategy performance statistics strictly from OBSERVED/VERIFIED evidence."""

    @staticmethod
    def aggregate_from_outcomes_list(
        outcomes: List[Dict[str, Any]],
        segment_name: Optional[str] = None,
        strategy_type: Optional[str] = None,
        as_of_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate performance metrics from a list of outcome dicts for a specific segment & strategy.
        Supports temporal filtering: excludes outcomes created/failed after as_of_time.
        """
        filtered = []
        for o in outcomes:
            if segment_name is not None and o.get("segment_name") != segment_name:
                continue
            if strategy_type is not None and o.get("strategy_type") != strategy_type:
                continue
            
            # Temporal cutoff check (prevent future holdout data leakage)
            if as_of_time is not None:
                o_time_str = o.get("failed_at") or o.get("created_at")
                if o_time_str:
                    o_dt = datetime.fromisoformat(o_time_str)
                    if o_dt > as_of_time:
                        continue
            filtered.append(o)

        attempts = len(filtered)
        successes = sum(1 for o in filtered if o.get("outcome") == "RECOVERED")
        total_recovered_paise = sum(o.get("recovered_amount_paise", 0) for o in filtered)

        rate = round(successes / attempts, 4) if attempts > 0 else 0.0
        wilson_lb = calculate_wilson_lower_bound(successes, attempts)
        tier = derive_sample_size_tier(attempts)
        conf_level = derive_confidence_level(attempts)

        sources = {o.get("outcome_source", DataCategory.OBSERVED.value) for o in filtered}
        if not sources:
            source_str = DataCategory.OBSERVED.value
        elif len(sources) == 1:
            source_str = list(sources)[0]
        else:
            source_str = "MIXED (" + ", ".join(sorted(sources)) + ")"

        return {
            "segment_name": segment_name or "aggregate",
            "strategy_type": strategy_type or "all",
            "attempt_count": attempts,
            "success_count": successes,
            "total_recovered_paise": total_recovered_paise,
            "recovery_rate": rate,
            "wilson_lower_bound": wilson_lb,
            "sample_size_tier": tier,
            "confidence_level": conf_level,
            "sample_size_sufficient": attempts >= 10,
            "evidence_source": source_str,
        }

    @staticmethod
    def aggregate_from_db(
        db: Session,
        segment_id: str,
        strategy_type: str,
        as_of_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Aggregate performance metrics from SQLite database records with optional temporal cutoff."""
        query = db.query(StrategyOutcome).filter(
            StrategyOutcome.segment_id == segment_id,
            StrategyOutcome.strategy_type == strategy_type,
        )
        if as_of_time is not None:
            query = query.filter(StrategyOutcome.created_at <= as_of_time)

        outcomes = query.all()
        attempts = len(outcomes)
        successes = sum(1 for o in outcomes if o.outcome == "RECOVERED")
        total_recovered_paise = sum(o.amount_recovered_paise or 0 for o in outcomes)

        rate = round(successes / attempts, 4) if attempts > 0 else 0.0
        wilson_lb = calculate_wilson_lower_bound(successes, attempts)
        tier = derive_sample_size_tier(attempts)
        conf_level = derive_confidence_level(attempts)

        sources = {o.outcome_source for o in outcomes if o.outcome_source}
        source_str = list(sources)[0] if len(sources) == 1 else (", ".join(sorted(sources)) if sources else DataCategory.OBSERVED.value)

        return {
            "segment_id": segment_id,
            "strategy_type": strategy_type,
            "attempt_count": attempts,
            "success_count": successes,
            "total_recovered_paise": total_recovered_paise,
            "recovery_rate": rate,
            "wilson_lower_bound": wilson_lb,
            "sample_size_tier": tier,
            "confidence_level": conf_level,
            "sample_size_sufficient": attempts >= 10,
            "evidence_source": source_str,
        }
