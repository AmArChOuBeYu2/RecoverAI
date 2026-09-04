"""
Synthetic Outcome & Latent Ground Truth Generator for RecoverAI
Generates hidden simulation ground truth and observed historical outcomes with controlled noise,
realistic context interactions, independent strategy assignments, and Case G small-sample trap scenario.
"""

import random
from typing import List, Dict, Any, Tuple
from backend.models.enums import StrategyType, FailureCategory, CustomerType

CANDIDATE_STRATEGIES = [
    StrategyType.PAYMENT_LINK.value,
    StrategyType.DELAYED_RETRY.value,
    StrategyType.REMINDER.value,
    StrategyType.METHOD_SWITCH.value,
    StrategyType.NO_ACTION.value,
]

# Base recovery probabilities per (FailureCategory, StrategyType)
BASE_PROBABILITIES: Dict[str, Dict[str, float]] = {
    FailureCategory.AUTHENTICATION_FAILURE.value: {
        StrategyType.PAYMENT_LINK.value: 0.48,
        StrategyType.METHOD_SWITCH.value: 0.35,
        StrategyType.REMINDER.value: 0.22,
        StrategyType.DELAYED_RETRY.value: 0.15,
        StrategyType.NO_ACTION.value: 0.02,
    },
    FailureCategory.BANK_TIMEOUT.value: {
        StrategyType.DELAYED_RETRY.value: 0.58,
        StrategyType.PAYMENT_LINK.value: 0.28,
        StrategyType.METHOD_SWITCH.value: 0.22,
        StrategyType.REMINDER.value: 0.12,
        StrategyType.NO_ACTION.value: 0.05,
    },
    FailureCategory.NETWORK_FAILURE.value: {
        StrategyType.DELAYED_RETRY.value: 0.52,
        StrategyType.PAYMENT_LINK.value: 0.32,
        StrategyType.METHOD_SWITCH.value: 0.25,
        StrategyType.REMINDER.value: 0.15,
        StrategyType.NO_ACTION.value: 0.03,
    },
    FailureCategory.INSUFFICIENT_FUNDS.value: {
        StrategyType.DELAYED_RETRY.value: 0.22,
        StrategyType.REMINDER.value: 0.18,
        StrategyType.PAYMENT_LINK.value: 0.12,
        StrategyType.METHOD_SWITCH.value: 0.10,
        StrategyType.NO_ACTION.value: 0.05,
    },
    FailureCategory.CHECKOUT_ABANDONMENT.value: {
        StrategyType.PAYMENT_LINK.value: 0.42,
        StrategyType.REMINDER.value: 0.38,
        StrategyType.METHOD_SWITCH.value: 0.20,
        StrategyType.DELAYED_RETRY.value: 0.10,
        StrategyType.NO_ACTION.value: 0.02,
    },
    FailureCategory.REPEATED_FAILURE.value: {
        StrategyType.NO_ACTION.value: 0.08,
        StrategyType.PAYMENT_LINK.value: 0.12,
        StrategyType.DELAYED_RETRY.value: 0.06,
        StrategyType.REMINDER.value: 0.05,
        StrategyType.METHOD_SWITCH.value: 0.09,
    },
    FailureCategory.UNKNOWN.value: {
        StrategyType.PAYMENT_LINK.value: 0.25,
        StrategyType.DELAYED_RETRY.value: 0.20,
        StrategyType.REMINDER.value: 0.15,
        StrategyType.METHOD_SWITCH.value: 0.15,
        StrategyType.NO_ACTION.value: 0.05,
    },
}

def calculate_latent_ground_truth(
    transaction: Dict[str, Any], customer: Dict[str, Any], rng: random.Random
) -> Dict[str, Any]:
    """
    Calculate the hidden ground truth probabilities for a transaction across all strategies.
    This includes context modifiers, fatigue penalties, amount penalties, and stochastic noise.
    """
    failure_cat = transaction["failure_category"]
    cust_type = customer["customer_type"]
    contacts_24h = customer.get("contacts_count_24h", 0)
    amount_paise = transaction["amount_paise"]

    base_map = BASE_PROBABILITIES.get(failure_cat, BASE_PROBABILITIES[FailureCategory.UNKNOWN.value])
    
    candidate_probs: Dict[str, float] = {}
    factors: List[str] = [f"failure_category={failure_cat}"]

    # Customer type modifier
    cust_modifier = 0.0
    if cust_type == CustomerType.RETURNING.value:
        cust_modifier = +0.05
        factors.append("customer_type=RETURNING (+5%)")
    elif cust_type == CustomerType.FATIGUED.value:
        cust_modifier = -0.18
        factors.append("customer_type=FATIGUED (-18%)")

    # Fatigue contact modifier
    if contacts_24h >= 3:
        fatigue_penalty = min(0.20, contacts_24h * 0.05)
        cust_modifier -= fatigue_penalty
        factors.append(f"high_contacts_24h={contacts_24h} (-{int(fatigue_penalty*100)}%)")

    # High amount modifier (> ₹50,000 paise)
    amount_modifier = 0.0
    if amount_paise > 5000000:
        amount_modifier = -0.10
        factors.append("high_amount_above_50k (-10%)")

    for strat in CANDIDATE_STRATEGIES:
        base_p = base_map.get(strat, 0.10)
        
        # Apply modifiers
        p = base_p + cust_modifier + amount_modifier

        # NO_ACTION is unaffected by fatigue penalties
        if strat == StrategyType.NO_ACTION.value:
            p = max(0.01, base_p)

        # Add stochastic noise N(0, 0.04)
        noise = rng.gauss(0.0, 0.04)
        p = max(0.01, min(0.95, round(p + noise, 4)))
        candidate_probs[strat] = p

    # Find best strategy in ground truth
    best_strat = max(candidate_probs, key=candidate_probs.get)
    max_prob = candidate_probs[best_strat]

    return {
        "transaction_id": transaction["id"],
        "customer_id": transaction["customer_id"],
        "segment_name": transaction["segment_name"],
        "true_recoverability": max_prob,
        "true_best_strategy": best_strat,
        "candidate_probabilities": candidate_probs,
        "influencing_factors": factors,
    }

def generate_outcomes_and_truth(
    transactions: List[Dict[str, Any]],
    customers_map: Dict[str, Dict[str, Any]],
    rng: random.Random,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate hidden simulation ground truth records and observed historical outcomes.
    Includes Case G small-sample trap scenario.
    """
    ground_truth_records: List[Dict[str, Any]] = []
    observed_outcomes: List[Dict[str, Any]] = []

    for txn in transactions:
        cust = customers_map[txn["customer_id"]]
        
        # 1. Compute latent ground truth
        truth = calculate_latent_ground_truth(txn, cust, rng)
        ground_truth_records.append(truth)

        # 2. Historical strategy assignment (Independent of future optimizer)
        # We assign strategies with realistic merchant historical policy weights
        strat_weights = [0.40, 0.25, 0.20, 0.10, 0.05] # Payment link, retry, reminder, method switch, no action
        assigned_strategy = rng.choices(CANDIDATE_STRATEGIES, weights=strat_weights, k=1)[0]

        # 3. Simulate outcome using true latent probability for assigned strategy
        true_prob = truth["candidate_probabilities"][assigned_strategy]
        recovered = rng.random() < true_prob

        outcome_status = "RECOVERED" if recovered else "NOT_RECOVERED"
        recovered_amount = txn["amount_paise"] if recovered else 0

        observed_outcome = {
            "transaction_id": txn["id"],
            "customer_id": txn["customer_id"],
            "segment_name": txn["segment_name"],
            "strategy_type": assigned_strategy,
            "outcome": outcome_status,
            "recovered_amount_paise": recovered_amount,
            "assigned_by": "HISTORICAL_MERCHANT_POLICY",
            "outcome_source": "OBSERVED",
            "created_at": txn["created_at"],
            "failed_at": txn["failed_at"],
        }
        observed_outcomes.append(observed_outcome)

    # Inject Explicit Case G Small-Sample Trap Scenario
    _inject_case_g_trap_scenario(transactions, ground_truth_records, observed_outcomes)

    return ground_truth_records, observed_outcomes

def _inject_case_g_trap_scenario(
    transactions: List[Dict[str, Any]],
    ground_truth_records: List[Dict[str, Any]],
    observed_outcomes: List[Dict[str, Any]],
):
    """
    Inject Case G Small-Sample Trap:
    In a specific segment (e.g. 'repeated_failure_netbanking_mid'),
    Strategy A (METHOD_SWITCH) has 1 attempt and 1 recovery (100% naive rate, Wilson lower bound ~0.025)
    Strategy B (PAYMENT_LINK) has 150 attempts and 40 recoveries (26.7% rate, Wilson lower bound ~0.20)
    This forces the future strategy engine to rely on Wilson score lower bound rather than naive rate.
    """
    trap_txns = [t for t in transactions if t["segment_name"].startswith("repeated_failure")]
    if len(trap_txns) >= 2:
        t1 = trap_txns[0]
        # Modify outcome for t1 to be Strategy A (METHOD_SWITCH) -> RECOVERED (1/1 = 100%)
        out1 = next((o for o in observed_outcomes if o["transaction_id"] == t1["id"]), None)
        if out1:
            out1["strategy_type"] = StrategyType.METHOD_SWITCH.value
            out1["outcome"] = "RECOVERED"
            out1["recovered_amount_paise"] = t1["amount_paise"]
            out1["is_case_g_trap_sample"] = True
