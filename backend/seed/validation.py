"""
Synthetic Dataset Validation Layer for RecoverAI
Validates schema correctness, enum integrity, amount invariants, history consistency,
timestamp chronological order, sample-size tier coverage, canonical 4D segment identity, and anti-leakage boundaries.
"""

from collections import Counter
from datetime import datetime
from typing import List, Dict, Any
from backend.models.enums import (
    FailureCategory,
    CustomerType,
    AmountRange,
    StrategyType,
)

VALID_FAILURE_CATEGORIES = {e.value for e in FailureCategory}
VALID_CUSTOMER_TYPES = {e.value for e in CustomerType}
VALID_AMOUNT_RANGES = {e.value for e in AmountRange}
VALID_STRATEGY_TYPES = {e.value for e in StrategyType}
VALID_PAYMENT_METHODS = {"card", "upi", "netbanking", "wallet", None}

REQUIRED_EDGE_CASE_AMOUNTS = {
    49999, 50000, 999999, 1000000, 1000001, 4999999, 5000000, 5000001
}

def validate_synthetic_dataset(
    customers: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    outcomes: List[Dict[str, Any]],
    ground_truth: List[Dict[str, Any]],
    train_txns: List[Dict[str, Any]],
    holdout_txns: List[Dict[str, Any]],
):
    """
    Perform strict validation on the synthetic dataset.
    Raises ValueError with descriptive reason if invalid data is found.
    """
    customer_ids = {c["id"] for c in customers}
    transaction_ids = {t["id"] for t in transactions}

    # 1. Validate Customers
    if len(customers) < 100:
        raise ValueError(f"Insufficient customer records: {len(customers)}")

    for cust in customers:
        if cust["customer_type"] not in VALID_CUSTOMER_TYPES:
            raise ValueError(f"Invalid customer type in customer {cust['id']}: {cust['customer_type']}")
        
        txns = cust["previous_transaction_count"]
        succ = cust["previous_successful_payment_count"]
        fail = cust["previous_failed_payment_count"]
        rec = cust["previous_recovered_payment_count"]
        contacts = cust["contacts_count_24h"]

        if succ + fail > txns:
            raise ValueError(f"Inconsistent customer history for {cust['id']}: succ ({succ}) + fail ({fail}) > total ({txns})")
        if rec > fail:
            raise ValueError(f"Inconsistent recovery history for {cust['id']}: recovered ({rec}) > failed ({fail})")
        if contacts < 0:
            raise ValueError(f"Negative contact count for {cust['id']}: {contacts}")

    # 2. Validate Transactions & 4D Segment Identity
    if len(transactions) < 500:
        raise ValueError(f"Transaction count below 500 requirement: {len(transactions)}")

    amounts_present = set()

    for txn in transactions:
        t_id = txn["id"]
        if txn["customer_id"] not in customer_ids:
            raise ValueError(f"Transaction {t_id} references unknown customer_id: {txn['customer_id']}")
        
        if txn["failure_category"] not in VALID_FAILURE_CATEGORIES:
            raise ValueError(f"Invalid failure category in transaction {t_id}: {txn['failure_category']}")

        if txn["payment_method"] not in VALID_PAYMENT_METHODS:
            raise ValueError(f"Invalid payment method in transaction {t_id}: {txn['payment_method']}")

        if txn["amount_range"] not in VALID_AMOUNT_RANGES:
            raise ValueError(f"Invalid amount range in transaction {t_id}: {txn['amount_range']}")

        if txn["customer_type"] not in VALID_CUSTOMER_TYPES:
            raise ValueError(f"Invalid customer type in transaction {t_id}: {txn['customer_type']}")

        # Validate canonical 4D segment identity key format
        method_str = txn["payment_method"].lower() if txn["payment_method"] else "any"
        cust_str = txn["customer_type"].lower() if txn["customer_type"] else "any"
        expected_segment = f"{txn['failure_category'].lower()}_{method_str}_{txn['amount_range'].lower()}_{cust_str}"
        if txn["segment_name"] != expected_segment:
            raise ValueError(f"Segment identity mismatch in transaction {t_id}: expected '{expected_segment}', got '{txn['segment_name']}'")

        amt = txn["amount_paise"]
        if not isinstance(amt, int) or amt <= 0:
            raise ValueError(f"Invalid integer paise amount in transaction {t_id}: {amt}")

        amounts_present.add(amt)

        # Timestamps check
        created_dt = datetime.fromisoformat(txn["created_at"])
        failed_dt = datetime.fromisoformat(txn["failed_at"])

        if created_dt > failed_dt:
            raise ValueError(f"Transaction {t_id} created_at ({created_dt}) > failed_at ({failed_dt})")

    # Check presence of exact edge case boundary amounts
    missing_edge_amounts = REQUIRED_EDGE_CASE_AMOUNTS - amounts_present
    if missing_edge_amounts:
        raise ValueError(f"Missing required edge case amounts in transaction dataset: {missing_edge_amounts}")

    # 3. Validate Outcomes
    outcome_txn_ids = set()
    for out in outcomes:
        t_id = out["transaction_id"]
        if t_id not in transaction_ids:
            raise ValueError(f"Outcome references non-existent transaction_id: {t_id}")
        
        if out["strategy_type"] not in VALID_STRATEGY_TYPES:
            raise ValueError(f"Invalid strategy_type in outcome for {t_id}: {out['strategy_type']}")

        rec_amt = out["recovered_amount_paise"]
        if rec_amt < 0:
            raise ValueError(f"Negative recovered amount in outcome for {t_id}: {rec_amt}")

        matching_txn = next(t for t in transactions if t["id"] == t_id)
        if rec_amt > matching_txn["amount_paise"]:
            raise ValueError(f"Outcome recovered amount ({rec_amt}) > transaction amount ({matching_txn['amount_paise']})")

        outcome_txn_ids.add(t_id)

    if len(outcome_txn_ids) != len(transactions):
        raise ValueError(f"Mismatched outcome count: {len(outcome_txn_ids)} outcomes for {len(transactions)} transactions")

    # 4. Check Segment Sample-Size Tier Coverage
    segment_counts = Counter(t["segment_name"] for t in transactions)
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

    missing_tiers = [tier for tier, count in tier_counts.items() if count == 0]
    if missing_tiers:
        raise ValueError(f"Synthetic dataset lacks coverage for segment sample-size tiers: {missing_tiers}. Distribution: {tier_counts}")

    # 5. Check Temporal Split Integrity
    if not train_txns or not holdout_txns:
        raise ValueError("Temporal train/holdout split is empty.")

    max_train_time = max(datetime.fromisoformat(t["created_at"]) for t in train_txns)
    min_holdout_time = min(datetime.fromisoformat(t["created_at"]) for t in holdout_txns)

    if max_train_time > min_holdout_time:
        raise ValueError(f"Temporal split violation: max train created_at ({max_train_time}) > min holdout created_at ({min_holdout_time})")

    # 6. Check Anti-Leakage Separation
    for out in outcomes:
        if "true_best_strategy" in out or "true_recoverability" in out:
            raise ValueError("Data leakage detected: Observed historical outcome contains hidden simulation truth!")

    return True
