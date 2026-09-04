"""
Deterministic Safety Net Fallback Provider — Milestone 11
Offline rule-based fallback provider when all external LLM services are unavailable.
"""

import time
from typing import Dict, Any, Tuple
from backend.integrations.llm.base import LLMProvider
from backend.integrations.llm.schemas import RecoveryDiagnosis
from backend.models.enums import FailureCategory, StrategyType

class DeterministicFallbackProvider(LLMProvider):
    """Safety-net provider executing deterministic decision tree logic."""

    @property
    def name(self) -> str:
        return "deterministic"

    @property
    def model_name(self) -> str:
        return "rule-engine-v1"

    def diagnose(self, context: Dict[str, Any]) -> Tuple[RecoveryDiagnosis, Dict[str, Any]]:
        start_t = time.perf_counter()

        txn = context.get("transaction", {})
        cust = context.get("customer", {})
        hist = context.get("recovery_history", {})

        raw_cat = txn.get("failure_category", "UNKNOWN")
        category = raw_cat if raw_cat in {e.value for e in FailureCategory} else FailureCategory.UNKNOWN.value

        amount_paise = txn.get("amount_paise", 0)
        attempts = hist.get("attempt_count", 0)
        contacts_24h = cust.get("contacts_count_24h", 0)

        # Deterministic strategy resolution logic
        if attempts >= 2 or contacts_24h >= 3:
            strategy = StrategyType.NO_ACTION.value
            reasoning = "Deterministic safety limit: max recovery attempts or customer contact frequency reached."
            recoverability = 0.1
            confidence = 1.0
            narrative = f"Case blocked by deterministic frequency rules (attempts={attempts}, contacts_24h={contacts_24h})."

        elif amount_paise >= 1000000: # ₹10,000+
            strategy = StrategyType.HUMAN_REVIEW.value
            reasoning = "Deterministic high-value threshold triggered (amount >= ₹10,000)."
            recoverability = 0.75
            confidence = 0.95
            narrative = f"High-value transaction (₹{amount_paise/100:.2f}) requires human review before intervention."

        elif category in (FailureCategory.AUTHENTICATION_FAILURE.value, FailureCategory.INSUFFICIENT_FUNDS.value):
            strategy = StrategyType.PAYMENT_LINK.value
            reasoning = "Deterministic rule: Auth/funds failure responds best to interactive payment link."
            recoverability = 0.65
            confidence = 0.90
            narrative = f"Customer experienced {category}. Payment link allows immediate retry with alternate method."

        elif category in (FailureCategory.BANK_TIMEOUT.value, FailureCategory.GATEWAY_DOWNTIME.value):
            strategy = StrategyType.RETRY.value
            reasoning = "Deterministic rule: Infrastructure timeout indicates transient network condition."
            recoverability = 0.70
            confidence = 0.90
            narrative = f"Transient gateway/bank timeout detected for payment. Automated retry recommended."

        elif category == FailureCategory.CHECKOUT_ABANDONMENT.value:
            strategy = StrategyType.REMINDER.value
            reasoning = "Deterministic rule: Abandoned checkout requires reminder notification."
            recoverability = 0.50
            confidence = 0.85
            narrative = "Customer abandoned checkout. Gentle reminder link recommended."

        else:
            strategy = StrategyType.PAYMENT_LINK.value
            reasoning = "Deterministic baseline fallback strategy."
            recoverability = 0.50
            confidence = 0.80
            narrative = f"General failure category '{category}' diagnosed. Standard payment link issued as fallback."

        diagnosis = RecoveryDiagnosis(
            failure_category=category,
            diagnosis=narrative,
            recoverability_score=recoverability,
            confidence=confidence,
            recommended_strategy=strategy,
            reasoning_summary=reasoning,
        )

        elapsed_ms = int((time.perf_counter() - start_t) * 1000)
        metadata = {
            "latency_ms": max(1, elapsed_ms),
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }

        return diagnosis, metadata
