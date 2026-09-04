"""
Synthetic Transaction Generator
Generates realistic payment failures with heavy-tailed amount distribution, controlled segment density,
and exact boundary edge cases.
"""

import random
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from backend.seed.config import GeneratorConfig
from backend.models.enums import FailureCategory, AmountRange

EXACT_EDGE_CASE_AMOUNTS = [
    49999,   # ₹499.99 (LOW/MID boundary)
    50000,   # ₹500.00 (Exact boundary)
    999999,  # ₹9,999.99 (Just below high-value threshold)
    1000000, # ₹10,000.00 (Exact high-value threshold)
    1000001, # ₹10,000.01 (Just above high-value threshold)
    4999999, # ₹49,999.99 (Just below max auto action threshold)
    5000000, # ₹50,000.00 (Exact max auto action threshold)
    5000001, # ₹50,000.01 (Just above max auto action threshold)
]

def derive_amount_range(amount_paise: int) -> str:
    """Derive deterministic amount range enum from integer paise."""
    if amount_paise < 50000:
        return AmountRange.LOW.value
    elif amount_paise <= 500000:
        return AmountRange.MID.value
    elif amount_paise <= 5000000:
        return AmountRange.HIGH.value
    else:
        return AmountRange.PREMIUM.value

def generate_transactions(
    config: GeneratorConfig, customers: List[Dict[str, Any]], rng: random.Random
) -> List[Dict[str, Any]]:
    """Generate a reproducible list of synthetic failed/abandoned transaction records."""
    transactions = []
    base_time = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
    
    # Pre-select index points for exact edge cases
    edge_case_indices = set(rng.sample(range(config.total_transactions), len(EXACT_EDGE_CASE_AMOUNTS)))
    edge_case_map = dict(zip(edge_case_indices, EXACT_EDGE_CASE_AMOUNTS))

    failure_categories = list(config.failure_distribution.keys())
    failure_weights = list(config.failure_distribution.values())

    payment_methods = list(config.payment_method_distribution.keys())
    method_weights = list(config.payment_method_distribution.values())

    for i in range(1, config.total_transactions + 1):
        idx = i - 1
        customer = rng.choice(customers)

        # 1. Determine amount in integer paise
        if idx in edge_case_map:
            amount_paise = edge_case_map[idx]
        else:
            r = rng.random()
            if r < 0.25:
                amount_paise = rng.randint(5000, 49999) # ₹50 - ₹499.99 (LOW)
            elif r < 0.75:
                amount_paise = rng.randint(50000, 500000) # ₹500 - ₹5,000 (MID)
            elif r < 0.93:
                amount_paise = rng.randint(500001, 5000000) # ₹5,000 - ₹50,000 (HIGH)
            else:
                amount_paise = rng.randint(5000001, 15000000) # ₹50,000 - ₹150,000 (PREMIUM)

        # 2. Failure category & method selection with shaped segment clusters
        # Guarantees HIGH (>100), MEDIUM (31-100), LOW (10-30), and INSUFFICIENT (<10) tiers at 500 or 1000 txns
        roll_cluster = rng.random()
        if roll_cluster < 0.25:
            # Cluster 1 (HIGH tier): AUTHENTICATION_FAILURE + card + MID amount
            failure_cat = FailureCategory.AUTHENTICATION_FAILURE.value
            method = "card"
            if idx not in edge_case_map:
                amount_paise = rng.randint(50000, 500000)
        elif roll_cluster < 0.40:
            # Cluster 2 (HIGH/MEDIUM tier): BANK_TIMEOUT + upi + LOW amount
            failure_cat = FailureCategory.BANK_TIMEOUT.value
            method = "upi"
            if idx not in edge_case_map:
                amount_paise = rng.randint(5000, 49999)
        elif roll_cluster < 0.50:
            # Cluster 3 (MEDIUM tier): CHECKOUT_ABANDONMENT + card + MID amount
            failure_cat = FailureCategory.CHECKOUT_ABANDONMENT.value
            method = "card"
            if idx not in edge_case_map:
                amount_paise = rng.randint(50000, 500000)
        elif roll_cluster < 0.55:
            # Cluster 4 (LOW tier): INSUFFICIENT_FUNDS + card + HIGH amount
            failure_cat = FailureCategory.INSUFFICIENT_FUNDS.value
            method = "card"
            if idx not in edge_case_map:
                amount_paise = rng.randint(500001, 5000000)
        elif roll_cluster < 0.59:
            # Cluster 5 (LOW tier): NETWORK_FAILURE + netbanking + MID amount
            failure_cat = FailureCategory.NETWORK_FAILURE.value
            method = "netbanking"
            if idx not in edge_case_map:
                amount_paise = rng.randint(50000, 500000)
        else:
            # Long-tail unclustered transactions (forms INSUFFICIENT tier segments <10 txns)
            failure_cat = rng.choices(failure_categories, weights=failure_weights, k=1)[0]
            if failure_cat == FailureCategory.CHECKOUT_ABANDONMENT.value:
                method = rng.choice(["card", "upi", None])
            elif failure_cat == FailureCategory.AUTHENTICATION_FAILURE.value and rng.random() < 0.6:
                method = "card"
            elif failure_cat == FailureCategory.BANK_TIMEOUT.value and rng.random() < 0.5:
                method = "upi"
            else:
                method = rng.choices(payment_methods, weights=method_weights, k=1)[0]

        # 3. Timestamps (multi-day/week span)
        days_ago = rng.uniform(0.1, config.days_span)
        created_at = base_time - timedelta(days=days_ago)
        failed_at = created_at + timedelta(seconds=rng.randint(2, 45))

        # 4. Error code metadata mapping
        error_code, error_desc, error_reason = _get_error_metadata(failure_cat, rng)

        # 5. Derive segment name
        amount_range = derive_amount_range(amount_paise)
        segment_name = f"{failure_cat.lower()}_{method or 'any'}_{amount_range.lower()}"

        txn_record = {
            "id": f"txn_synth_{i:05d}",
            "razorpay_payment_id": f"pay_synth_{i:05d}" if failure_cat != FailureCategory.CHECKOUT_ABANDONMENT.value else None,
            "razorpay_order_id": f"order_synth_{i:05d}",
            "customer_id": customer["id"],
            "amount_paise": amount_paise,
            "currency": "INR",
            "status": "FAILED" if failure_cat != FailureCategory.CHECKOUT_ABANDONMENT.value else "CREATED",
            "failure_category": failure_cat,
            "payment_method": method,
            "amount_range": amount_range,
            "customer_type": customer["customer_type"],
            "segment_name": segment_name,
            "error_code": error_code,
            "error_description": error_desc,
            "error_reason": error_reason,
            "created_at": created_at.isoformat(),
            "failed_at": failed_at.isoformat(),
            "attempt_count": 0 if failure_cat == FailureCategory.CHECKOUT_ABANDONMENT.value else rng.randint(1, 2),
            "data_source": "SIMULATED",
        }
        transactions.append(txn_record)

    return transactions

def _get_error_metadata(failure_cat: str, rng: random.Random) -> tuple[str, str, str]:
    """Map failure category to realistic Razorpay error response fields."""
    if failure_cat == FailureCategory.AUTHENTICATION_FAILURE.value:
        return ("BAD_REQUEST_ERROR", "Payment authentication failed at 3DS OTP step", "payment_authentication_failed")
    elif failure_cat == FailureCategory.BANK_TIMEOUT.value:
        return ("GATEWAY_ERROR", "Bank gateway timed out during processing", "gateway_timeout")
    elif failure_cat == FailureCategory.INSUFFICIENT_FUNDS.value:
        return ("BAD_REQUEST_ERROR", "Insufficient funds in customer account", "insufficient_funds")
    elif failure_cat == FailureCategory.NETWORK_FAILURE.value:
        return ("GATEWAY_ERROR", "Network connection dropped by issuer bank", "network_drop")
    elif failure_cat == FailureCategory.CHECKOUT_ABANDONMENT.value:
        return ("CHECKOUT_ABANDONED", "Customer closed checkout tab before completing payment", "customer_abandoned")
    elif failure_cat == FailureCategory.REPEATED_FAILURE.value:
        return ("BAD_REQUEST_ERROR", "Multiple failed attempts on same card/VPA", "repeated_declines")
    else:
        return ("SERVER_ERROR", "Unknown processing error", "unknown_error")
