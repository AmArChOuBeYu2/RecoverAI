"""
Comprehensive Automated Test Suite for Milestone 7 — Synthetic Data Generator & Evaluation Dataset
Validates determinism, canonical 4D segment identity, schema integrity, enum validity, history consistency,
temporal splits, anti-leakage boundaries, sample-size tier coverage, boundary edge cases, and Case G trap scenario.
"""

import os
import json
import pytest
from pathlib import Path
from backend.seed.config import GeneratorConfig
from backend.seed.generator import run_synthetic_generation
from backend.seed.transactions import derive_canonical_segment_name
from backend.seed.validation import validate_synthetic_dataset
from backend.models.enums import (
    FailureCategory,
    CustomerType,
    AmountRange,
    StrategyType,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def test_deterministic_generation_same_seed(tmp_path):
    """Test 1 & 11: Running generation twice with the same seed produces 100% identical data."""
    config1 = GeneratorConfig(seed=20260904, total_transactions=500)
    config2 = GeneratorConfig(seed=20260904, total_transactions=500)

    res1 = run_synthetic_generation(config1, tmp_path / "run1")
    res2 = run_synthetic_generation(config2, tmp_path / "run2")

    assert res1["train_transactions"] == res2["train_transactions"]
    assert res1["holdout_transactions"] == res2["holdout_transactions"]
    assert res1["train_outcomes"] == res2["train_outcomes"]
    assert res1["ground_truth"] == res2["ground_truth"]

def test_different_seed_produces_different_data(tmp_path):
    """Test 2: Different seeds produce different synthetic records."""
    config1 = GeneratorConfig(seed=20260904, total_transactions=500)
    config2 = GeneratorConfig(seed=99999999, total_transactions=500)

    res1 = run_synthetic_generation(config1, tmp_path / "run1")
    res2 = run_synthetic_generation(config2, tmp_path / "run2")

    # Both dataset records and orderings should differ due to different seed
    assert res1["train_transactions"] != res2["train_transactions"]
    assert res1["ground_truth"] != res2["ground_truth"]

def test_minimum_500_records_generated(tmp_path):
    """Test 3: Generator produces at least 500 records (1000 configured)."""
    config = GeneratorConfig(seed=20260904, total_transactions=1000)
    res = run_synthetic_generation(config, tmp_path)

    total_records = len(res["train_transactions"]) + len(res["holdout_transactions"])
    assert total_records >= 500
    assert total_records == 1000

def test_schema_validity(tmp_path):
    """Test 4: All required schema attributes exist on transactions and customers."""
    config = GeneratorConfig(seed=20260904, total_transactions=500)
    res = run_synthetic_generation(config, tmp_path)

    txn = res["train_transactions"][0]
    required_txn_keys = {
        "id", "razorpay_order_id", "customer_id", "amount_paise", "currency",
        "status", "failure_category", "payment_method", "amount_range",
        "customer_type", "segment_name", "created_at", "failed_at", "attempt_count"
    }
    assert required_txn_keys.issubset(txn.keys())

    cust = res["customers"][0]
    required_cust_keys = {
        "id", "name", "email", "phone", "customer_type", "account_age_days",
        "previous_transaction_count", "previous_successful_payment_count",
        "previous_failed_payment_count", "previous_recovered_payment_count", "contacts_count_24h"
    }
    assert required_cust_keys.issubset(cust.keys())

def test_enum_validity(tmp_path):
    """Test 5: All generated string fields match project enums."""
    config = GeneratorConfig(seed=20260904, total_transactions=500)
    res = run_synthetic_generation(config, tmp_path)

    valid_failures = {e.value for e in FailureCategory}
    valid_cust_types = {e.value for e in CustomerType}
    valid_amount_ranges = {e.value for e in AmountRange}

    for txn in res["train_transactions"] + res["holdout_transactions"]:
        assert txn["failure_category"] in valid_failures
        assert txn["amount_range"] in valid_amount_ranges
        assert txn["customer_type"] in valid_cust_types

def test_amount_validity(tmp_path):
    """Test 6 & 12: Amounts are strictly positive integer paise, recovered <= amount."""
    config = GeneratorConfig(seed=20260904, total_transactions=500)
    res = run_synthetic_generation(config, tmp_path)

    for txn in res["train_transactions"] + res["holdout_transactions"]:
        assert isinstance(txn["amount_paise"], int)
        assert txn["amount_paise"] > 0

    for out in res["train_outcomes"] + res["holdout_outcomes"]:
        assert isinstance(out["recovered_amount_paise"], int)
        assert out["recovered_amount_paise"] >= 0

        matching_txn = next(t for t in res["train_transactions"] + res["holdout_transactions"] if t["id"] == out["transaction_id"])
        assert out["recovered_amount_paise"] <= matching_txn["amount_paise"]

def test_timestamp_validity(tmp_path):
    """Test 7: created_at <= failed_at for all transactions."""
    from datetime import datetime
    config = GeneratorConfig(seed=20260904, total_transactions=500)
    res = run_synthetic_generation(config, tmp_path)

    for txn in res["train_transactions"] + res["holdout_transactions"]:
        c_dt = datetime.fromisoformat(txn["created_at"])
        f_dt = datetime.fromisoformat(txn["failed_at"])
        assert c_dt <= f_dt

def test_customer_history_consistency(tmp_path):
    """Test 8: Customer history counters satisfy logical invariants."""
    config = GeneratorConfig(seed=20260904, total_transactions=500)
    res = run_synthetic_generation(config, tmp_path)

    for c in res["customers"]:
        assert c["previous_successful_payment_count"] + c["previous_failed_payment_count"] <= c["previous_transaction_count"]
        assert c["previous_recovered_payment_count"] <= c["previous_failed_payment_count"]
        assert c["contacts_count_24h"] >= 0

def test_canonical_4d_segment_derivation(tmp_path):
    """Test 9: Canonical 4D segment names incorporate customer_type."""
    config = GeneratorConfig(seed=20260904, total_transactions=500)
    res = run_synthetic_generation(config, tmp_path)

    for txn in res["train_transactions"]:
        expected = derive_canonical_segment_name(
            txn["failure_category"],
            txn["payment_method"],
            txn["amount_range"],
            txn["customer_type"],
        )
        assert txn["segment_name"] == expected

def test_customer_type_in_canonical_segment_identity():
    """REQUIREMENT 10: Two otherwise identical transactions with different customer_type belong to different canonical segments."""
    seg1 = derive_canonical_segment_name("AUTHENTICATION_FAILURE", "card", "MID", "RETURNING")
    seg2 = derive_canonical_segment_name("AUTHENTICATION_FAILURE", "card", "MID", "FATIGUED")

    assert seg1 == "authentication_failure_card_mid_returning"
    assert seg2 == "authentication_failure_card_mid_fatigued"
    assert seg1 != seg2

def test_sample_size_tier_coverage(tmp_path):
    """Test 10: All 4 sample size tiers (INSUFFICIENT, LOW, MEDIUM, HIGH) exist in dataset."""
    config = GeneratorConfig(seed=20260904, total_transactions=1000)
    res = run_synthetic_generation(config, tmp_path)

    tiers = res["stats"]["sample_size_tiers"]
    assert tiers["INSUFFICIENT"] > 0
    assert tiers["LOW"] > 0
    assert tiers["MEDIUM"] > 0
    assert tiers["HIGH"] > 0

def test_sparse_segment_triggers_fallback_protection(tmp_path):
    """REQUIREMENT 11: Sparse segments (<10 txns) fall into INSUFFICIENT tier to exercise sample-size protections."""
    config = GeneratorConfig(seed=20260904, total_transactions=500)
    res = run_synthetic_generation(config, tmp_path)

    from collections import Counter
    segment_counts = Counter(t["segment_name"] for t in res["train_transactions"])
    sparse_segments = [seg for seg, count in segment_counts.items() if count < 10]

    assert len(sparse_segments) > 0, "Dataset must contain sparse segments to exercise fallback protections."

def test_temporal_split_correctness(tmp_path):
    """Test 13: 80/20 chronological split without future leakage."""
    from datetime import datetime
    config = GeneratorConfig(seed=20260904, total_transactions=1000, historical_ratio=0.80)
    res = run_synthetic_generation(config, tmp_path)

    assert len(res["train_transactions"]) == 800
    assert len(res["holdout_transactions"]) == 200

    max_train = max(datetime.fromisoformat(t["created_at"]) for t in res["train_transactions"])
    min_holdout = min(datetime.fromisoformat(t["created_at"]) for t in res["holdout_transactions"])
    assert max_train <= min_holdout

def test_hidden_truth_separation_and_anti_leakage(tmp_path):
    """Test 14, 15, 16: Hidden ground truth is isolated in simulation_truth/ directory and omitted from observed outcomes."""
    config = GeneratorConfig(seed=20260904, total_transactions=500)
    res = run_synthetic_generation(config, tmp_path)

    truth_file = tmp_path / "data" / "simulation_truth" / "ground_truth.json"
    observed_outcomes_file = tmp_path / "data" / "observed" / "outcomes.json"

    assert truth_file.exists()
    assert observed_outcomes_file.exists()

    with open(observed_outcomes_file, "r") as f:
        observed_data = json.load(f)

    for out in observed_data:
        assert "true_best_strategy" not in out
        assert "true_recoverability" not in out
        assert "candidate_probabilities" not in out

def test_edge_case_presence(tmp_path):
    """Test 17: Explicit boundary edge case amounts are present in dataset."""
    config = GeneratorConfig(seed=20260904, total_transactions=500)
    res = run_synthetic_generation(config, tmp_path)

    amounts = {t["amount_paise"] for t in res["train_transactions"] + res["holdout_transactions"]}
    required_edge_amounts = {49999, 50000, 999999, 1000000, 1000001, 4999999, 5000000, 5000001}
    assert required_edge_amounts.issubset(amounts)

def test_metadata_correctness(tmp_path):
    """Test 18 & 19: Metadata file contains version, seed, record counts, and split definitions."""
    config = GeneratorConfig(seed=20260904, total_transactions=500)
    res = run_synthetic_generation(config, tmp_path)

    meta_file = tmp_path / "data" / "metadata" / "dataset_metadata.json"
    assert meta_file.exists()

    with open(meta_file, "r") as f:
        meta = json.load(f)

    assert meta["dataset_version"] == "v1.0"
    assert meta["seed"] == 20260904
    assert meta["total_transactions"] == 500
    assert meta["split_definition"]["historical_train_ratio"] == 0.80

def test_strategy_assignment_independence(tmp_path):
    """Test 20: Historical strategy assignment is marked as HISTORICAL_MERCHANT_POLICY."""
    config = GeneratorConfig(seed=20260904, total_transactions=500)
    res = run_synthetic_generation(config, tmp_path)

    for out in res["train_outcomes"]:
        assert out["assigned_by"] == "HISTORICAL_MERCHANT_POLICY"
        assert out["outcome_source"] == "OBSERVED"

def test_case_g_trap_scenario(tmp_path):
    """Test 22: Case G small-sample trap sample marker exists in outcome data."""
    config = GeneratorConfig(seed=20260904, total_transactions=500)
    res = run_synthetic_generation(config, tmp_path)

    trap_outcomes = [o for o in res["train_outcomes"] if o.get("is_case_g_trap_sample")]
    assert len(trap_outcomes) >= 1
