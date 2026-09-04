"""
Structured Prompt Engineering Module — Milestone 11
Builds system and user prompts for payment recovery diagnosis without temporal or ground-truth leakage.
"""

import json
from typing import Dict, Any

SYSTEM_DIAGNOSIS_PROMPT = """You are RecoverAI, an expert Payment Recovery & Diagnostic AI Agent for Indian payment gateways (Razorpay).
Your task is to analyze payment failure details, customer profile history, canonical 4D segment data, and prior recovery history, then return a structured JSON recovery diagnosis.

CRITICAL INSTRUCTIONS:
1. Output MUST strictly conform to the following JSON schema:
{
  "failure_category": "<one of: AUTHENTICATION_FAILURE, INSUFFICIENT_FUNDS, BANK_TIMEOUT, GATEWAY_DOWNTIME, CUSTOMER_ABANDONMENT, METHOD_UNAVAILABLE, ACCOUNT_BLOCKED, EXPIRED_CARD, TECHNICAL_ERROR, UNKNOWN>",
  "diagnosis": "<detailed narrative explaining root cause of failure>",
  "recoverability_score": <float between 0.0 and 1.0 representing propensity to recover>,
  "confidence": <float between 0.0 and 1.0 representing confidence in diagnosis>,
  "recommended_strategy": "<one of: PAYMENT_LINK, RETRY, REMINDER, DELAYED_RETRY, METHOD_SWITCH, NO_ACTION, HUMAN_REVIEW>",
  "reasoning_summary": "<concise explanation of strategy choice>"
}

2. Strategy Selection Guidelines:
- AUTHENTICATION_FAILURE / INSUFFICIENT_FUNDS: Suggest PAYMENT_LINK or REMINDER (allows customer to try different payment method or add funds).
- BANK_TIMEOUT / GATEWAY_DOWNTIME: Suggest RETRY or DELAYED_RETRY (transient issue likely resolved later).
- High value transactions (> ₹10,000): Suggest PAYMENT_LINK or HUMAN_REVIEW.
- Repeated failures / max retries reached: Suggest HUMAN_REVIEW or NO_ACTION.

3. DO NOT output any extra text, markdown formatting, or HTML tags outside the JSON object.
"""

def build_user_prompt(context: Dict[str, Any]) -> str:
    """Build structured user prompt from case context dictionary."""
    txn = context.get("transaction", {})
    cust = context.get("customer", {})
    seg = context.get("segment", {})
    hist = context.get("recovery_history", {})
    case = context.get("case", {})

    prompt_data = {
        "case_id": case.get("id"),
        "status": case.get("status"),
        "attempt_count": case.get("attempt_count", 0),
        "transaction": {
            "amount_rupees": txn.get("amount_rupees", 0.0),
            "currency": txn.get("currency", "INR"),
            "failure_category": txn.get("failure_category"),
            "error_code": txn.get("error_code"),
            "error_description": txn.get("error_description"),
            "payment_method": txn.get("payment_method"),
            "age_hours": txn.get("age_hours", 0.0),
        },
        "customer": {
            "customer_type": cust.get("customer_type"),
            "contacts_count_24h": cust.get("contacts_count_24h", 0),
            "total_transactions": cust.get("total_transactions", 0),
            "failed_transactions": cust.get("failed_transactions", 0),
            "successful_transactions": cust.get("successful_transactions", 0),
        },
        "segment": {
            "name": seg.get("name"),
            "failure_category": seg.get("failure_category"),
            "payment_method": seg.get("payment_method"),
            "amount_range": seg.get("amount_range"),
            "customer_type": seg.get("customer_type"),
        },
        "prior_recovery_attempts": hist.get("attempt_count", 0),
    }

    return f"Analyze the following payment case context and provide a structured JSON recovery diagnosis:\n\n{json.dumps(prompt_data, indent=2)}"
