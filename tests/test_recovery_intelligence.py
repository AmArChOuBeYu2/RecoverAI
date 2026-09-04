"""
Comprehensive Unit & Integration Test Suite for Milestone 8 — Recovery Intelligence Foundations
Validates Wilson score math, Case G small-sample trap, sample size tiers, fallback hierarchy,
temporal leakage prevention, transparent recoverability scoring, portfolio revenue-at-risk, and API contracts.
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
from backend.models.enums import StrategyType, FailureCategory, ConfidenceLevel, DataCategory

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

def test_sample_size_tier_boundaries():
    """Verify sample size tier boundary transitions (<10, 10-30, 31-100, >100)."""
    assert derive_sample_size_tier(0) == ConfidenceLevel.INSUFFICIENT.value
    assert derive_sample_size_tier(1) == ConfidenceLevel.INSUFFICIENT.value
    assert derive_sample_size_tier(9) == ConfidenceLevel.INSUFFICIENT.value
    
    assert derive_sample_size_tier(10) == ConfidenceLevel.LOW.value
    assert derive_sample_size_tier(20) == ConfidenceLevel.LOW.value
    assert derive_sample_size_tier(30) == ConfidenceLevel.LOW.value
    
    assert derive_sample_size_tier(31) == ConfidenceLevel.MEDIUM.value
    assert derive_sample_size_tier(50) == ConfidenceLevel.MEDIUM.value
    assert derive_sample_size_tier(100) == ConfidenceLevel.MEDIUM.value
    
    assert derive_sample_size_tier(101) == ConfidenceLevel.HIGH.value
    assert derive_sample_size_tier(500) == ConfidenceLevel.HIGH.value

# -----------------------------------------------------------------------------
# 2. Fallback Hierarchy & Evidence Trace Tests
# -----------------------------------------------------------------------------

def test_fallback_hierarchy_execution():
    """Verify 4D -> 3D -> Failure Category -> Global Safe Default fallback steps."""
    outcomes = [
        # 4D canonical has only 2 attempts (< 10)
        {"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "PAYMENT_LINK", "outcome": "RECOVERED", "recovered_amount_paise": 1000, "outcome_source": "OBSERVED"},
        {"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "PAYMENT_LINK", "outcome": "NOT_RECOVERED", "recovered_amount_paise": 0, "outcome_source": "OBSERVED"},

        # 3D aggregate has 12 attempts (>= 10)
        *([{"segment_name": "authentication_failure_card_mid_new", "strategy_type": "PAYMENT_LINK", "outcome": "RECOVERED", "recovered_amount_paise": 1000, "outcome_source": "OBSERVED"}] * 6),
        *([{"segment_name": "authentication_failure_card_mid_fatigued", "strategy_type": "PAYMENT_LINK", "outcome": "NOT_RECOVERED", "recovered_amount_paise": 0, "outcome_source": "OBSERVED"}] * 6),
    ]

    res = FallbackEngine.evaluate_strategy_with_fallback(
        outcomes,
        failure_category="AUTHENTICATION_FAILURE",
        payment_method="card",
        amount_range="MID",
        customer_type="RETURNING",
        strategy_type="PAYMENT_LINK",
    )

    trace = res["evidence_trace"]
    assert trace["fallback_occurred"] is True
    assert trace["fallback_level"] == "3D_AGGREGATE"
    assert trace["requested_segment"] == "authentication_failure_card_mid_returning"
    assert res["performance"]["attempt_count"] == 14

def test_cold_start_insufficient_evidence():
    """Verify zero evidence returns GLOBAL_SAFE_DEFAULT fallback trace and INSUFFICIENT confidence."""
    empty_outcomes = []
    res = FallbackEngine.evaluate_strategy_with_fallback(
        empty_outcomes,
        failure_category="AUTHENTICATION_FAILURE",
        payment_method="upi",
        amount_range="HIGH",
        customer_type="FATIGUED",
        strategy_type="PAYMENT_LINK",
    )

    perf = res["performance"]
    trace = res["evidence_trace"]
    assert trace["fallback_level"] == "GLOBAL_SAFE_DEFAULT"
    assert perf["confidence_level"] == "INSUFFICIENT"
    assert perf["sample_size_sufficient"] is False

# -----------------------------------------------------------------------------
# 3. Temporal Leakage & Anti-Leakage Isolation Tests
# -----------------------------------------------------------------------------

def test_temporal_leakage_prevention():
    """REQUIREMENT: Future outcomes after decision as_of_time MUST NOT alter strategy performance aggregation."""
    base_time = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    future_time = base_time + timedelta(days=5)

    outcomes = [
        {"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "PAYMENT_LINK", "outcome": "RECOVERED", "recovered_amount_paise": 1000, "created_at": base_time.isoformat(), "failed_at": base_time.isoformat()},
        # Future outcome that should be ignored when as_of_time = base_time
        {"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "PAYMENT_LINK", "outcome": "NOT_RECOVERED", "recovered_amount_paise": 0, "created_at": future_time.isoformat(), "failed_at": future_time.isoformat()},
    ]

    stats_past = StrategyAggregator.aggregate_from_outcomes_list(
        outcomes, "authentication_failure_card_mid_returning", "PAYMENT_LINK", as_of_time=base_time
    )
    assert stats_past["attempt_count"] == 1
    assert stats_past["success_count"] == 1

    stats_all = StrategyAggregator.aggregate_from_outcomes_list(
        outcomes, "authentication_failure_card_mid_returning", "PAYMENT_LINK", as_of_time=None
    )
    assert stats_all["attempt_count"] == 2

def test_data_source_separation():
    """Verify evidence sources (OBSERVED, VERIFIED, SIMULATED, PROJECTED) stay distinct."""
    outcomes = [
        {"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "PAYMENT_LINK", "outcome": "RECOVERED", "recovered_amount_paise": 1000, "outcome_source": "VERIFIED"},
        {"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "PAYMENT_LINK", "outcome": "NOT_RECOVERED", "recovered_amount_paise": 0, "outcome_source": "SIMULATED"},
    ]

    stats = StrategyAggregator.aggregate_from_outcomes_list(
        outcomes, "authentication_failure_card_mid_returning", "PAYMENT_LINK"
    )
    assert stats["evidence_source"] == "MIXED (SIMULATED, VERIFIED)"

# -----------------------------------------------------------------------------
# 4. Deterministic Strategy Ranking & Recoverability Tests
# -----------------------------------------------------------------------------

def test_deterministic_strategy_ranking():
    """Verify StrategyRanker produces identical output for identical inputs and ranks by Wilson LB."""
    outcomes = [
        # Strategy A: PAYMENT_LINK -> 15 attempts, 10 recoveries (Wilson LB ~0.417, LOW tier)
        *([{"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "PAYMENT_LINK", "outcome": "RECOVERED", "recovered_amount_paise": 1000}] * 10),
        *([{"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "PAYMENT_LINK", "outcome": "NOT_RECOVERED", "recovered_amount_paise": 0}] * 5),
        
        # Strategy B: DELAYED_RETRY -> 1 attempt, 1 recovery (Wilson LB ~0.025, INSUFFICIENT tier)
        {"segment_name": "authentication_failure_card_mid_returning", "strategy_type": "DELAYED_RETRY", "outcome": "RECOVERED", "recovered_amount_paise": 1000},
    ]

    rank_res1 = StrategyRanker.compare_and_rank_strategies(
        outcomes, "AUTHENTICATION_FAILURE", "card", "MID", "RETURNING"
    )
    rank_res2 = StrategyRanker.compare_and_rank_strategies(
        outcomes, "AUTHENTICATION_FAILURE", "card", "MID", "RETURNING"
    )

    assert rank_res1 == rank_res2
    assert rank_res1["recommended_strategy"] == "PAYMENT_LINK"

def test_transparent_recoverability_scoring():
    """Verify transparent recoverability score calculation and factor contributions."""
    txn = {
        "id": "txn_test_101",
        "failure_category": "AUTHENTICATION_FAILURE",
        "amount_paise": 100000,
        "customer_type": "RETURNING",
        "attempt_count": 0,
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    cust = {"contacts_count_24h": 0}

    score_res = RecoverabilityScorer.calculate_recoverability_score(txn, cust)
    assert 0.01 <= score_res["recoverability_score"] <= 0.99
    assert score_res["score_category"] in ["HIGH", "MEDIUM", "LOW"]
    assert len(score_res["factors"]) >= 2
    assert any(f["name"] == "base_failure_category" for f in score_res["factors"])
    assert any(f["name"] == "customer_type_returning" for f in score_res["factors"])

def test_portfolio_revenue_at_risk_calculation():
    """Verify portfolio revenue at risk and eligible revenue in integer paise."""
    txns = [
        {"id": "t1", "amount_paise": 100000, "failure_category": "AUTHENTICATION_FAILURE", "segment_name": "s1", "created_at": "2026-09-01T10:00:00+00:00"},
        {"id": "t2", "amount_paise": 500000, "failure_category": "BANK_TIMEOUT", "segment_name": "s1", "created_at": "2026-09-01T11:00:00+00:00"},
        {"id": "t3", "amount_paise": 6000000, "failure_category": "REPEATED_FAILURE", "segment_name": "s2", "created_at": "2026-09-01T12:00:00+00:00"},
    ]

    metrics = PortfolioIntelligenceService.calculate_portfolio_metrics(txns, [])
    assert metrics["total_revenue_at_risk_paise"] == 6600000
    assert metrics["eligible_revenue_paise"] == 600000
    assert isinstance(metrics["projected_recoverable_revenue_paise"], int)

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
    assert "ranked_strategies" in data
    assert len(data["ranked_strategies"]) == 5

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
    assert "trace_steps" in data
