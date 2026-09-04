"""
Comprehensive Unit & Integration Test Suite for Milestone 8 Hardening — Recovery Intelligence Foundations
Validates Wilson score math, Case G small-sample trap, economic strategy value optimization,
evidence provenance separation, cold-start baseline semantics, temporal leakage prevention, and API contracts.
"""

import os
import json
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.main import app
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
from backend.models.enums import (
    StrategyType,
    FailureCategory,
    ConfidenceLevel,
    DataCategory,
    EvidenceProvenance,
    RecommendationType,
)

client = TestClient(app)

# -----------------------------------------------------------------------------
# 1. Wilson Score Math & Sample Size Tier Tests
# -----------------------------------------------------------------------------

def test_wilson_score_mathematical_accuracy():
    """Verify Wilson lower bound values against known statistical calculations."""
    assert calculate_wilson_lower_bound(0, 0) == 0.0
    assert calculate_wilson_lower_bound(0, 10) == 0.0
    assert calculate_wilson_lower_bound(10, 10) == pytest.approx(0.7225, abs=1e-3)
    assert calculate_wilson_lower_bound(50, 100) == pytest.approx(0.4038, abs=1e-3)
    assert calculate_wilson_lower_bound(100, 100) == pytest.approx(0.9630, abs=1e-3)

def test_wilson_score_invalid_inputs():
    """Verify Wilson score calculation raises ValueError for invalid inputs."""
    with pytest.raises(ValueError):
        calculate_wilson_lower_bound(-1, 10)
    with pytest.raises(ValueError):
        calculate_wilson_lower_bound(10, -5)
    with pytest.raises(ValueError):
        calculate_wilson_lower_bound(15, 10)

def test_case_g_small_sample_trap():
    """REQUIREMENT: Strategy B (40/150 = 26.7%, HIGH tier) MUST rank above Strategy A (1/1 = 100%, INSUFFICIENT tier)."""
    outcomes = [
        # Strategy A (METHOD_SWITCH): 1 attempt, 1 recovery (1/1 = 100% naive rate, INSUFFICIENT tier)
        {"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "METHOD_SWITCH", "outcome": "RECOVERED", "recovered_amount_paise": 1000},

        # Strategy B (PAYMENT_LINK): 150 attempts, 40 recoveries (40/150 = 26.7% naive rate, HIGH tier)
        *([{"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "PAYMENT_LINK", "outcome": "RECOVERED", "recovered_amount_paise": 1000}] * 40),
        *([{"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "PAYMENT_LINK", "outcome": "NOT_RECOVERED", "recovered_amount_paise": 0}] * 110),
    ]

    rank_res = StrategyRanker.compare_and_rank_strategies(
        outcomes, "AUTHENTICATION_FAILURE", "card", "MID", "RETURNING"
    )

    assert rank_res["recommended_strategy"] == "PAYMENT_LINK"
    ranked_types = [s["strategy_type"] for s in rank_res["ranked_strategies"]]
    assert ranked_types.index("PAYMENT_LINK") < ranked_types.index("METHOD_SWITCH")

# -----------------------------------------------------------------------------
# 2. Strategy Economic Value Optimization Tests
# -----------------------------------------------------------------------------

def test_strategy_monetary_value_optimization():
    """REQUIREMENT: Lower recovery rate on high-value payments can produce greater economic value than higher rate on low-value payments."""
    outcomes = [
        # Strategy A (REMINDER): 40% recovery rate on ₹100 transactions (10,000 paise) -> Expected ~₹40/attempt
        *([{"segment_name": "bank_timeout_upi_mid_returning", "strategy_type": "REMINDER", "outcome": "RECOVERED", "recovered_amount_paise": 10000, "transaction_amount_paise": 10000}] * 8),
        *([{"segment_name": "bank_timeout_upi_mid_returning", "strategy_type": "REMINDER", "outcome": "NOT_RECOVERED", "recovered_amount_paise": 0, "transaction_amount_paise": 10000}] * 12),

        # Strategy B (DELAYED_RETRY): 30% recovery rate on ₹5,000 transactions (500,000 paise) -> Expected ~₹1,500/attempt
        *([{"segment_name": "bank_timeout_upi_mid_returning", "strategy_type": "DELAYED_RETRY", "outcome": "RECOVERED", "recovered_amount_paise": 500000, "transaction_amount_paise": 500000}] * 6),
        *([{"segment_name": "bank_timeout_upi_mid_returning", "strategy_type": "DELAYED_RETRY", "outcome": "NOT_RECOVERED", "recovered_amount_paise": 0, "transaction_amount_paise": 500000}] * 14),
    ]

    rank_res = StrategyRanker.compare_and_rank_strategies(
        outcomes, "BANK_TIMEOUT", "upi", "MID", "RETURNING"
    )

    # Strategy B (DELAYED_RETRY) has lower rate (30% vs 40%) but much higher monetary recovery expected
    strat_b = next(s for s in rank_res["ranked_strategies"] if s["strategy_type"] == "DELAYED_RETRY")
    strat_a = next(s for s in rank_res["ranked_strategies"] if s["strategy_type"] == "REMINDER")

    assert strat_b["expected_recovered_paise_per_attempt"] > strat_a["expected_recovered_paise_per_attempt"]
    assert strat_b["economic_strategy_value_score"] > strat_a["economic_strategy_value_score"]
    assert rank_res["recommended_strategy"] == "DELAYED_RETRY"

def test_small_sample_protection_with_high_amount():
    """Verify that a 1-attempt ₹50,000 transaction (1/1 = 100%) CANNOT dominate a well-tested strategy (40/150) due to tier weighting."""
    outcomes = [
        # Strategy A (METHOD_SWITCH): 1 attempt, 1 recovery on ₹50,000 (INSUFFICIENT tier)
        {"segment_name": "authentication_failure_card_high_returning", "strategy_type": "METHOD_SWITCH", "outcome": "RECOVERED", "recovered_amount_paise": 5000000, "transaction_amount_paise": 5000000},

        # Strategy B (PAYMENT_LINK): 40 recoveries out of 150 on ₹50,000 (HIGH tier)
        *([{"segment_name": "authentication_failure_card_high_returning", "strategy_type": "PAYMENT_LINK", "outcome": "RECOVERED", "recovered_amount_paise": 5000000, "transaction_amount_paise": 5000000}] * 40),
        *([{"segment_name": "authentication_failure_card_high_returning", "strategy_type": "PAYMENT_LINK", "outcome": "NOT_RECOVERED", "recovered_amount_paise": 0, "transaction_amount_paise": 5000000}] * 110),
    ]

    rank_res = StrategyRanker.compare_and_rank_strategies(
        outcomes, "AUTHENTICATION_FAILURE", "card", "HIGH", "RETURNING"
    )

    assert rank_res["recommended_strategy"] == "PAYMENT_LINK"

# -----------------------------------------------------------------------------
# 3. Provenance & Cold-Start Baseline Semantics Tests
# -----------------------------------------------------------------------------

def test_evidence_provenance_separation():
    """REQUIREMENT: OBSERVED + SYNTHETIC is distinct from VERIFIED + RAZORPAY_TEST_MODE."""
    outcomes_synth = [
        {"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "PAYMENT_LINK", "outcome": "RECOVERED", "recovered_amount_paise": 1000, "evidence_category": "OBSERVED", "evidence_provenance": "SYNTHETIC"},
    ]
    outcomes_razorpay = [
        {"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "PAYMENT_LINK", "outcome": "RECOVERED", "recovered_amount_paise": 1000, "evidence_category": "VERIFIED", "evidence_provenance": "RAZORPAY_TEST_MODE"},
    ]

    stats_s = StrategyAggregator.aggregate_from_outcomes_list(outcomes_synth, "authentication_failure_card_mid_returning", "PAYMENT_LINK")
    stats_r = StrategyAggregator.aggregate_from_outcomes_list(outcomes_razorpay, "authentication_failure_card_mid_returning", "PAYMENT_LINK")

    assert stats_s["evidence_category"] == DataCategory.OBSERVED.value
    assert stats_s["evidence_provenance"] == EvidenceProvenance.SYNTHETIC.value

    assert stats_r["evidence_category"] == DataCategory.VERIFIED.value
    assert stats_r["evidence_provenance"] == EvidenceProvenance.RAZORPAY_TEST_MODE.value

    assert stats_s["evidence_source"] != stats_r["evidence_source"]

def test_cold_start_baseline_semantics():
    """REQUIREMENT: Cold start recommendations MUST be labeled BASELINE_RECOMMENDATION & INSUFFICIENT_EVIDENCE."""
    empty_outcomes = []
    rank_res = StrategyRanker.compare_and_rank_strategies(
        empty_outcomes, "AUTHENTICATION_FAILURE", "card", "MID", "RETURNING"
    )

    assert rank_res["recommendation_type"] == RecommendationType.BASELINE_RECOMMENDATION.value
    assert rank_res["evidence_status"] == "INSUFFICIENT_EVIDENCE"
    assert rank_res["strategy_source"] == "DETERMINISTIC_BASELINE"

# -----------------------------------------------------------------------------
# 4. Temporal Money-Value Leakage Tests
# -----------------------------------------------------------------------------

def test_temporal_money_value_leakage_prevention():
    """REQUIREMENT: Future high-value outcomes after as_of_time CANNOT alter historical strategy rankings or expected value."""
    base_time = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    future_time = base_time + timedelta(days=5)

    outcomes = [
        # Past outcome: 10/10 recoveries on ₹1,000 (100,000 paise)
        *([{"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "PAYMENT_LINK", "outcome": "RECOVERED", "recovered_amount_paise": 100000, "transaction_amount_paise": 100000, "created_at": base_time.isoformat()}] * 10),
        
        # Future outcome: 10/10 recoveries on ₹50,000 (5,000,000 paise) for REMINDER
        *([{"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "REMINDER", "outcome": "RECOVERED", "recovered_amount_paise": 5000000, "transaction_amount_paise": 5000000, "created_at": future_time.isoformat()}] * 10),
    ]

    # Evaluate as of base_time
    rank_past = StrategyRanker.compare_and_rank_strategies(
        outcomes, "AUTHENTICATION_FAILURE", "card", "MID", "RETURNING", as_of_time=base_time
    )

    # PAYMENT_LINK should win in the past because future REMINDER outcomes were excluded
    assert rank_past["recommended_strategy"] == "PAYMENT_LINK"
    reminder_past = next(s for s in rank_past["ranked_strategies"] if s["strategy_type"] == "REMINDER")
    assert reminder_past["attempt_count"] == 0

# -----------------------------------------------------------------------------
# 5. REST API Integration Tests
# -----------------------------------------------------------------------------

def test_api_portfolio_intelligence():
    response = client.get("/api/intelligence/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert "total_revenue_at_risk_paise" in data
    assert "eligible_revenue_paise" in data
    assert "sample_size_tiers" in data

def test_api_segments_list():
    response = client.get("/api/intelligence/segments")
    assert response.status_code == 200
    data = response.json()
    assert "total_canonical_segments" in data
    assert "sample_size_tiers" in data

def test_api_strategies_compare():
    response = client.get(
        "/api/intelligence/strategies/compare",
        params={
            "failure_category": "AUTHENTICATION_FAILURE",
            "payment_method": "card",
            "amount_range": "MID",
            "customer_type": "RETURNING",
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "recommended_strategy" in data
    assert "recommendation_type" in data
    assert "ranked_strategies" in data
    
    strat0 = data["ranked_strategies"][0]
    assert "economic_strategy_value_score" in strat0
    assert "evidence_category" in strat0
    assert "evidence_provenance" in strat0

def test_api_recoverability_post():
    payload = {
        "failure_category": "AUTHENTICATION_FAILURE",
        "payment_method": "card",
        "amount_paise": 150000,
        "customer_type": "RETURNING",
        "attempt_count": 0,
        "contacts_count_24h": 1,
    }
    response = client.post("/api/intelligence/recoverability", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "recoverability_score" in data
    assert "factors" in data

def test_api_evidence_trace():
    response = client.get(
        "/api/intelligence/evidence-trace",
        params={
            "failure_category": "AUTHENTICATION_FAILURE",
            "payment_method": "card",
            "amount_range": "MID",
            "customer_type": "RETURNING",
            "strategy_type": "PAYMENT_LINK",
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "fallback_level" in data
    assert "recommendation_type" in data
    assert "evidence_status" in data
    assert "trace_steps" in data
