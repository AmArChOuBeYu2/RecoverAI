"""
Wilson Score Interval Calculator & Sample Size Tier Evaluator
Provides mathematically sound lower confidence bound calculations for strategy success rates
and evaluates sample-size confidence tiers.
"""

import math
from backend.models.enums import ConfidenceLevel

def calculate_wilson_lower_bound(successes: int, attempts: int, z: float = 1.96) -> float:
    """
    Calculate the Wilson score interval lower bound at a given confidence level z (default z=1.96 for 95% CI).
    
    Formula:
      p_hat = successes / attempts
      denominator = 1 + (z^2 / n)
      centre = p_hat + (z^2 / (2 * n))
      spread = z * sqrt( (p_hat * (1 - p_hat) / n) + (z^2 / (4 * n^2)) )
      lower_bound = (centre - spread) / denominator
    """
    if attempts < 0 or successes < 0:
        raise ValueError(f"Invalid negative attempts ({attempts}) or successes ({successes})")
    if successes > attempts:
        raise ValueError(f"Successes ({successes}) cannot exceed attempts ({attempts})")
    if attempts == 0:
        return 0.0

    p_hat = successes / attempts
    n = float(attempts)
    z2 = z * z

    denominator = 1.0 + (z2 / n)
    centre = p_hat + (z2 / (2.0 * n))
    spread = z * math.sqrt((p_hat * (1.0 - p_hat) / n) + (z2 / (4.0 * (n ** 2))))
    
    lower_bound = (centre - spread) / denominator
    return max(0.0, min(1.0, round(lower_bound, 4)))

def derive_sample_size_tier(attempts: int) -> str:
    """
    Derive statistical sample-size tier from attempt count:
    - INSUFFICIENT (<10 attempts)
    - LOW (10-30 attempts)
    - MEDIUM (31-100 attempts)
    - HIGH (>100 attempts)
    """
    if attempts < 10:
        return ConfidenceLevel.INSUFFICIENT.value
    elif attempts <= 30:
        return ConfidenceLevel.LOW.value
    elif attempts <= 100:
        return ConfidenceLevel.MEDIUM.value
    else:
        return ConfidenceLevel.HIGH.value

def derive_confidence_level(attempts: int) -> str:
    """Derive human-readable confidence level from attempt count."""
    return derive_sample_size_tier(attempts)
