"""
RecoverAI Application Services Package
"""

from backend.services.sanitization import sanitize_payload
from backend.services.state_machine import StateMachineService, InvalidStateTransitionError
from backend.services.recovery_service import RecoveryService
from backend.services.wilson_score import (
    calculate_wilson_lower_bound,
    derive_sample_size_tier,
    derive_confidence_level,
)
from backend.services.strategy_aggregator import StrategyAggregator
from backend.services.fallback_engine import FallbackEngine
from backend.services.strategy_ranker import StrategyRanker
from backend.services.recoverability_scorer import RecoverabilityScorer
from backend.services.portfolio_intelligence import PortfolioIntelligenceService
from backend.services.recovery_intelligence import RecoveryIntelligenceService

from backend.services.ingestion import IngestionService
from backend.services.policy_config import PolicyConfig
from backend.services.trust_gate import TrustGateService, TrustGateResult
from backend.services.policy_engine import PolicyEngine, PolicyEvaluationResult, RuleEvaluationDetail
from backend.services.authorization import ActionAuthorizationService, ActionAuthorizationError

__all__ = [
    "sanitize_payload",
    "StateMachineService",
    "InvalidStateTransitionError",
    "RecoveryService",
    "calculate_wilson_lower_bound",
    "derive_sample_size_tier",
    "derive_confidence_level",
    "StrategyAggregator",
    "FallbackEngine",
    "StrategyRanker",
    "RecoverabilityScorer",
    "PortfolioIntelligenceService",
    "RecoveryIntelligenceService",
    "IngestionService",
    "PolicyConfig",
    "TrustGateService",
    "TrustGateResult",
    "PolicyEngine",
    "PolicyEvaluationResult",
    "RuleEvaluationDetail",
    "ActionAuthorizationService",
    "ActionAuthorizationError",
]
