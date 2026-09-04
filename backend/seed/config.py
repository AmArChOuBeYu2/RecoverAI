"""
Synthetic Data Generator Configuration
Defines default seed, record count targets, failure distributions, amount distributions, and file paths.
"""

from typing import Dict, Any
from pydantic import BaseModel, Field

class GeneratorConfig(BaseModel):
    """Configuration for RecoverAI synthetic dataset generation."""
    
    seed: int = 20260904
    dataset_version: str = "v1.0"
    generator_version: str = "v1.0"
    total_transactions: int = 1000 # 1,000 realistic records
    total_customers: int = 400
    
    # Temporal range (days before evaluation time)
    days_span: int = 30
    historical_ratio: float = 0.80 # 80% Train/Historical, 20% Holdout/Test
    
    # Failure category target proportions
    failure_distribution: Dict[str, float] = Field(default_factory=lambda: {
        "AUTHENTICATION_FAILURE": 0.35,
        "BANK_TIMEOUT": 0.25,
        "CHECKOUT_ABANDONMENT": 0.15,
        "INSUFFICIENT_FUNDS": 0.10,
        "REPEATED_FAILURE": 0.08,
        "NETWORK_FAILURE": 0.05,
        "UNKNOWN": 0.02,
    })

    # Payment method target proportions
    payment_method_distribution: Dict[str, float] = Field(default_factory=lambda: {
        "card": 0.40,
        "upi": 0.35,
        "netbanking": 0.15,
        "wallet": 0.10,
    })

    # Customer type target proportions
    customer_type_distribution: Dict[str, float] = Field(default_factory=lambda: {
        "NEW": 0.40,
        "RETURNING": 0.45,
        "FATIGUED": 0.15,
    })
