"""
Master Recovery Intelligence Service for RecoverAI
Provides provider-independent service contracts for strategy performance aggregation,
Wilson score ranking, hierarchical fallback tracing, explainable recoverability scoring,
and portfolio revenue-at-risk analysis.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.services.strategy_aggregator import StrategyAggregator
from backend.services.fallback_engine import FallbackEngine
from backend.services.strategy_ranker import StrategyRanker
from backend.services.recoverability_scorer import RecoverabilityScorer
from backend.services.portfolio_intelligence import PortfolioIntelligenceService
from backend.models.enums import DataCategory

class RecoveryIntelligenceService:
    """Master deterministic intelligence service for strategy optimization and portfolio analysis."""

    def __init__(self, observed_outcomes: Optional[List[Dict[str, Any]]] = None, db: Optional[Session] = None):
        self.observed_outcomes = observed_outcomes or []
        self.db = db

    def get_strategy_performance(
        self,
        segment_name: str,
        strategy_type: str,
        as_of_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Fetch strategy performance metrics for a specific segment & strategy with cutoff filtering."""
        if self.observed_outcomes:
            return StrategyAggregator.aggregate_from_outcomes_list(
                self.observed_outcomes, segment_name, strategy_type, as_of_time
            )
        elif self.db:
            # Look up segment ID from DB
            from backend.models import Segment
            seg = self.db.query(Segment).filter_by(name=segment_name).first()
            if seg:
                return StrategyAggregator.aggregate_from_db(self.db, seg.id, strategy_type, as_of_time)
        
        return {
            "segment_name": segment_name,
            "strategy_type": strategy_type,
            "attempt_count": 0,
            "success_count": 0,
            "total_recovered_paise": 0,
            "recovery_rate": 0.0,
            "wilson_lower_bound": 0.0,
            "sample_size_tier": "INSUFFICIENT",
            "confidence_level": "INSUFFICIENT",
            "sample_size_sufficient": False,
            "evidence_source": DataCategory.OBSERVED.value,
        }

    def compare_strategies(
        self,
        failure_category: str,
        payment_method: Optional[str],
        amount_range: str,
        customer_type: Optional[str],
        as_of_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Compare candidate strategies for a payment context using Wilson lower bounds and fallback hierarchy."""
        return StrategyRanker.compare_and_rank_strategies(
            self.observed_outcomes,
            failure_category,
            payment_method,
            amount_range,
            customer_type,
            as_of_time,
        )

    def get_recoverability(
        self,
        transaction: Dict[str, Any],
        customer: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compute transparent, explainable propensity score R in [0.0, 1.0] and factor contributions."""
        return RecoverabilityScorer.calculate_recoverability_score(transaction, customer)

    def get_evidence_trace(
        self,
        failure_category: str,
        payment_method: Optional[str],
        amount_range: str,
        customer_type: Optional[str],
        strategy_type: str,
        as_of_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Fetch step-by-step evidence trace for a strategy evaluation."""
        eval_res = FallbackEngine.evaluate_strategy_with_fallback(
            self.observed_outcomes,
            failure_category,
            payment_method,
            amount_range,
            customer_type,
            strategy_type,
            as_of_time,
        )
        return eval_res["evidence_trace"]

    def get_portfolio_opportunity(
        self,
        transactions: List[Dict[str, Any]],
        customers_map: Optional[Dict[str, Dict[str, Any]]] = None,
        as_of_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Compute portfolio revenue at risk, eligible revenue, and segment opportunity rankings."""
        return PortfolioIntelligenceService.calculate_portfolio_metrics(
            transactions, self.observed_outcomes, customers_map, as_of_time
        )
