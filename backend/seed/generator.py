"""
Seed Data Generator for RecoverAI
Pre-populates baseline segments and initial strategy performance templates.
"""

from sqlalchemy.orm import Session
from backend.models import (
    Segment,
    RecoveryStrategy,
    FailureCategory,
    StrategyType,
    AmountRange,
    CustomerType,
    DataCategory,
    ConfidenceLevel,
)

# Standard initial segments for RecoverAI
DEFAULT_SEGMENTS = [
    {
        "name": "auth_failure_card_mid_value",
        "failure_category": FailureCategory.AUTHENTICATION_FAILURE.value,
        "payment_method": "card",
        "amount_range": AmountRange.MID.value,
        "customer_type": CustomerType.RETURNING.value,
        "description": "Card authentication failure on mid-value transaction for returning customer.",
    },
    {
        "name": "bank_timeout_upi_low_value",
        "failure_category": FailureCategory.BANK_TIMEOUT.value,
        "payment_method": "upi",
        "amount_range": AmountRange.LOW.value,
        "customer_type": CustomerType.NEW.value,
        "description": "Bank timeout during UPI transaction on low-value amount.",
    },
    {
        "name": "insufficient_funds_card_high_value",
        "failure_category": FailureCategory.INSUFFICIENT_FUNDS.value,
        "payment_method": "card",
        "amount_range": AmountRange.HIGH.value,
        "customer_type": CustomerType.RETURNING.value,
        "description": "Insufficient funds error on high-value card transaction.",
    },
    {
        "name": "checkout_abandonment_any_mid_value",
        "failure_category": FailureCategory.CHECKOUT_ABANDONMENT.value,
        "payment_method": None,
        "amount_range": AmountRange.MID.value,
        "customer_type": CustomerType.NEW.value,
        "description": "Inferred checkout abandonment (order created, no payment attempt).",
    },
    {
        "name": "network_failure_netbanking_any_value",
        "failure_category": FailureCategory.NETWORK_FAILURE.value,
        "payment_method": "netbanking",
        "amount_range": AmountRange.MID.value,
        "customer_type": None,
        "description": "Gateway/network connection dropped during netbanking checkout.",
    },
]

def seed_default_segments(db: Session) -> list[Segment]:
    """Seed initial segments if they do not already exist."""
    created_segments = []
    for seg_data in DEFAULT_SEGMENTS:
        existing = db.query(Segment).filter_by(name=seg_data["name"]).first()
        if not existing:
            segment = Segment(**seg_data)
            db.add(segment)
            created_segments.append(segment)
    db.commit()

    # Seed baseline strategy performance templates for created segments
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
