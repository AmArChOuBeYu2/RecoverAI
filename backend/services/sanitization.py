"""
Security Sanitization Utility
Redacts sensitive payment credentials, tokens, and secrets from payloads before storage or logging.
"""

import copy
from typing import Any, Dict

SENSITIVE_KEYS = {
    "card_number", "card", "cvv", "cvc", "password", "secret", 
    "auth_code", "token", "key_secret", "razorpay_key_secret"
}

def sanitize_payload(payload: Any) -> Any:
    """Recursively sanitize sensitive fields in a payload dict or list."""
    if isinstance(payload, dict):
        sanitized = {}
        for key, value in payload.items():
            if key.lower() in SENSITIVE_KEYS:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, (dict, list)):
                sanitized[key] = sanitize_payload(value)
            else:
                sanitized[key] = value
        return sanitized
    elif isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    return payload
