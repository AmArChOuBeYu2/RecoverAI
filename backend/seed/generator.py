"""
Master Synthetic Dataset Generator & Orchestrator for RecoverAI
Generates 1,000+ reproducible synthetic merchant transactions, customer histories, latent ground truth,
and observed historical outcomes. Validates invariants, applies temporal splits, exports data partitions,
and optionally seeds the local SQLite database.
"""

import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session

from backend.seed.config import GeneratorConfig
from backend.seed.customers import generate_customers
from backend.seed.transactions import generate_transactions
from backend.seed.outcomes import generate_outcomes_and_truth
from backend.seed.validation import validate_synthetic_dataset
from backend.seed.exporter import export_synthetic_dataset
from backend.models import (
    Segment,
    RecoveryStrategy,
    Customer,
    Transaction,
    DataCategory,
    ConfidenceLevel,
    StrategyType,
    FailureCategory,
    AmountRange,
    CustomerType,
)

DEFAULT_SEGMENTS = [
    {
        "name": "auth_failure_card_mid_returning",
        "failure_category": FailureCategory.AUTHENTICATION_FAILURE.value,
        "payment_method": "card",
        "amount_range": AmountRange.MID.value,
        "customer_type": CustomerType.RETURNING.value,
        "description": "Card authentication failure on mid-value transaction for returning customer.",
    },
    {
        "name": "bank_timeout_upi_low_new",
        "failure_category": FailureCategory.BANK_TIMEOUT.value,
        "payment_method": "upi",
        "amount_range": AmountRange.LOW.value,
        "customer_type": CustomerType.NEW.value,
        "description": "Bank timeout during UPI transaction on low-value amount for new customer.",
    },
    {
        "name": "insufficient_funds_card_high_returning",
        "failure_category": FailureCategory.INSUFFICIENT_FUNDS.value,
        "payment_method": "card",
        "amount_range": AmountRange.HIGH.value,
        "customer_type": CustomerType.RETURNING.value,
        "description": "Insufficient funds error on high-value card transaction for returning customer.",
    },
    {
        "name": "checkout_abandonment_card_mid_new",
        "failure_category": FailureCategory.CHECKOUT_ABANDONMENT.value,
        "payment_method": "card",
        "amount_range": AmountRange.MID.value,
        "customer_type": CustomerType.NEW.value,
        "description": "Inferred checkout abandonment on card transaction for new customer.",
    },
    {
        "name": "network_failure_netbanking_mid_returning",
        "failure_category": FailureCategory.NETWORK_FAILURE.value,
        "payment_method": "netbanking",
        "amount_range": AmountRange.MID.value,
        "customer_type": CustomerType.RETURNING.value,
        "description": "Gateway/network connection dropped during netbanking checkout for returning customer.",
    },
]

def run_synthetic_generation(
    config: GeneratorConfig = None,
    project_root: Path = None,
    db: Session = None,
) -> Dict[str, Any]:
    """Master generation function. Deterministic given config.seed."""
    if config is None:
        config = GeneratorConfig()
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent.parent

    # 1. Initialize random number generators with fixed seed
    random.seed(config.seed)
    rng = random.Random(config.seed)

    # 2. Generate Entities
    customers = generate_customers(config, rng)
    customers_map = {c["id"]: c for c in customers}

    raw_transactions = generate_transactions(config, customers, rng)
    ground_truth, raw_outcomes = generate_outcomes_and_truth(raw_transactions, customers_map, rng)

    # 3. Sort Chronologically by created_at
    combined = list(zip(raw_transactions, raw_outcomes, ground_truth))
    combined.sort(key=lambda item: item[0]["created_at"])

    sorted_txns = [item[0] for item in combined]
    sorted_outcomes = [item[1] for item in combined]
    sorted_truth = [item[2] for item in combined]

    # 4. Temporal Split (Historical/Train 80%, Holdout/Test 20%)
    split_index = int(len(sorted_txns) * config.historical_ratio)
    train_txns = sorted_txns[:split_index]
    holdout_txns = sorted_txns[split_index:]

    train_outcomes = sorted_outcomes[:split_index]
    holdout_outcomes = sorted_outcomes[split_index:]

    # 5. Extract 4-Dimensional Canonical Segments
    segments_dict: Dict[str, Dict[str, Any]] = {}
    for txn in sorted_txns:
        seg_name = txn["segment_name"]
        if seg_name not in segments_dict:
            segments_dict[seg_name] = {
                "name": seg_name,
                "failure_category": txn["failure_category"],
                "payment_method": txn["payment_method"],
                "amount_range": txn["amount_range"],
                "customer_type": txn["customer_type"],
                "description": f"Canonical 4D segment for {seg_name}",
            }
    segments_list = list(segments_dict.values())

    # 6. Validate Synthetic Dataset
    validate_synthetic_dataset(
        customers,
        sorted_txns,
        sorted_outcomes,
        sorted_truth,
        train_txns,
        holdout_txns,
    )

    # 7. Compute Statistics for Metadata
    generated_at = datetime.now(timezone.utc).isoformat()
    stats = _compute_dataset_statistics(
        customers, sorted_txns, train_txns, holdout_txns, sorted_outcomes, segments_list, generated_at
    )

    # 8. Export to file partitions
    export_paths = export_synthetic_dataset(
        config,
        project_root,
        customers,
        train_txns,
        holdout_txns,
        train_outcomes,
        holdout_outcomes,
        sorted_truth,
        segments_list,
        stats,
    )

    # 9. Optionally seed local database
    if db is not None:
        _seed_database(db, customers, segments_list, train_txns, train_outcomes)

    return {
        "config": config,
        "export_paths": export_paths,
        "stats": stats,
        "customers": customers,
        "train_transactions": train_txns,
        "holdout_transactions": holdout_txns,
        "train_outcomes": train_outcomes,
        "holdout_outcomes": holdout_outcomes,
        "ground_truth": sorted_truth,
    }

def seed_default_segments(db: Session) -> list[Segment]:
    """Seed baseline default segments into database for backward compatibility with existing tests."""
    created_segments = []
    for seg_data in DEFAULT_SEGMENTS:
        existing = db.query(Segment).filter_by(name=seg_data["name"]).first()
        if not existing:
            segment = Segment(**seg_data)
            db.add(segment)
            created_segments.append(segment)
    db.commit()

    all_segments = db.query(Segment).all()
    for seg in all_segments:
        for strat_type in [StrategyType.PAYMENT_LINK, StrategyType.RETRY, StrategyType.REMINDER]:
            existing_strat = db.query(RecoveryStrategy).filter_by(
                segment_id=seg.id, strategy_type=strat_type.value
            ).first()
            if not existing_strat:
                strat = RecoveryStrategy(
                    segment_id=seg.id,
                    strategy_type=strat_type.value,
                    attempt_count=0,
                    success_count=0,
                    total_recovered_paise=0,
                    recovery_rate=0.0,
                    wilson_lower_bound=0.0,
                    sample_size_sufficient=False,
                    data_source=DataCategory.OBSERVED.value,
                    confidence_level=ConfidenceLevel.INSUFFICIENT.value,
                )
                db.add(strat)
    db.commit()
    return all_segments

def _compute_dataset_statistics(
    customers, sorted_txns, train_txns, holdout_txns, outcomes, segments, generated_at
) -> Dict[str, Any]:
    """Compute detailed analytical summary of the generated dataset."""
    from collections import Counter

    failure_dist = dict(Counter(t["failure_category"] for t in sorted_txns))
    method_dist = dict(Counter(t["payment_method"] for t in sorted_txns))
    cust_type_dist = dict(Counter(t["customer_type"] for t in sorted_txns))
    amount_range_dist = dict(Counter(t["amount_range"] for t in sorted_txns))

    segment_counts = Counter(t["segment_name"] for t in sorted_txns)
    tier_counts = {"INSUFFICIENT": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for count in segment_counts.values():
        if count < 10:
            tier_counts["INSUFFICIENT"] += 1
        elif count <= 30:
            tier_counts["LOW"] += 1
        elif count <= 100:
            tier_counts["MEDIUM"] += 1
        else:
            tier_counts["HIGH"] += 1

    total_amount_paise = sum(t["amount_paise"] for t in sorted_txns)
    total_recovered_paise = sum(o["recovered_amount_paise"] for o in outcomes)

    return {
        "generated_at": generated_at,
        "total_records": len(sorted_txns),
        "train_records": len(train_txns),
        "holdout_records": len(holdout_txns),
        "total_customers": len(customers),
        "total_segments": len(segments),
        "sample_size_tiers": tier_counts,
        "total_revenue_at_risk_paise": total_amount_paise,
        "total_observed_recovered_paise": total_recovered_paise,
        "observed_overall_recovery_rate": round(total_recovered_paise / total_amount_paise, 4) if total_amount_paise > 0 else 0.0,
        "distributions": {
            "failure_category": failure_dist,
            "payment_method": method_dist,
            "customer_type": cust_type_dist,
            "amount_range": amount_range_dist,
        },
    }

def _seed_database(
    db: Session,
    customers: list,
    segments: list,
    transactions: list,
    outcomes: list,
):
    """Seed SQLite database with generated customers, segments, transactions, and observed strategy metrics."""
    # Seed Customers
    for c_data in customers:
        if not db.query(Customer).filter_by(id=c_data["id"]).first():
            cust = Customer(
                id=c_data["id"],
                name=c_data["name"],
                email=c_data["email"],
                phone=c_data["phone"],
                customer_type=c_data["customer_type"],
                total_transactions=c_data["previous_transaction_count"],
                successful_transactions=c_data["previous_successful_payment_count"],
                failed_transactions=c_data["previous_failed_payment_count"],
                contacts_count_24h=c_data["contacts_count_24h"],
            )
            db.add(cust)
    db.commit()

    # Seed Segments
    for s_data in segments:
        seg = db.query(Segment).filter_by(name=s_data["name"]).first()
        if not seg:
            seg = Segment(**s_data)
            db.add(seg)
    db.commit()

    # Seed Baseline Strategy Performance Metrics per Segment
    all_segments = db.query(Segment).all()
    for seg in all_segments:
        seg_outcomes = [o for o in outcomes if o["segment_name"] == seg.name]
        for strat_enum in StrategyType:
            strat_outcomes = [o for o in seg_outcomes if o["strategy_type"] == strat_enum.value]
            attempts = len(strat_outcomes)
            succs = sum(1 for o in strat_outcomes if o["outcome"] == "RECOVERED")
            recovered_paise = sum(o["recovered_amount_paise"] for o in strat_outcomes)
            
            rate = round(succs / attempts, 4) if attempts > 0 else 0.0
            is_sufficient = attempts >= 10

            existing = db.query(RecoveryStrategy).filter_by(
                segment_id=seg.id, strategy_type=strat_enum.value
            ).first()

            if not existing:
                strat_obj = RecoveryStrategy(
                    segment_id=seg.id,
                    strategy_type=strat_enum.value,
                    attempt_count=attempts,
                    success_count=succs,
                    total_recovered_paise=recovered_paise,
                    recovery_rate=rate,
                    sample_size_sufficient=is_sufficient,
                    data_source=DataCategory.OBSERVED.value,
                    confidence_level=ConfidenceLevel.HIGH.value if attempts >= 30 else (ConfidenceLevel.LOW.value if attempts >= 10 else ConfidenceLevel.INSUFFICIENT.value),
                )
                db.add(strat_obj)
    db.commit()

if __name__ == "__main__":
    results = run_synthetic_generation()
    print("Synthetic dataset generation complete!")
    print(f"Total transactions: {results['stats']['total_records']}")
    print(f"Total canonical segments: {results['stats']['total_segments']}")
    print(f"Train/Holdout split: {results['stats']['train_records']} / {results['stats']['holdout_records']}")
    print(f"Sample-size tiers: {results['stats']['sample_size_tiers']}")
