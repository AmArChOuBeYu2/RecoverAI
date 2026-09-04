"""
Razorpay Low-Level Client Wrapper
Encapsulates official razorpay SDK calls with timeout, authentication, and error normalization.
"""

import logging
import razorpay
from typing import Dict, Any, Optional
from backend.config import settings
from backend.integrations.razorpay.exceptions import (
    RazorpayIntegrationError,
    RazorpayAuthenticationError,
    RazorpayInvalidRequestError,
    RazorpayResourceNotFoundError,
    RazorpayServerError,
    RazorpayTimeoutError,
    RazorpayWebhookSignatureError,
)

logger = logging.getLogger(__name__)

class RazorpayClient:
    """Server-side client wrapper around official razorpay Python SDK."""

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.key_id = key_id or settings.RAZORPAY_KEY_ID
        self.key_secret = key_secret or settings.RAZORPAY_KEY_SECRET
        self.webhook_secret = webhook_secret or settings.RAZORPAY_WEBHOOK_SECRET
        self.timeout = timeout

        if not self.key_id or not self.key_secret:
            logger.warning("Razorpay credentials not fully configured. API calls will fail if not mocked.")

        # Initialize official SDK client
        self._sdk_client = razorpay.Client(auth=(self.key_id, self.key_secret))
        # Ensure timeout option is set if supported on SDK session
        if hasattr(self._sdk_client, "session") and hasattr(self._sdk_client.session, "timeout"):
            self._sdk_client.session.timeout = self.timeout

    def verify_webhook_signature(self, body_bytes: bytes | str, signature: str) -> bool:
        """
        Verify Razorpay Webhook signature against configured webhook secret.
        Must use raw request body string/bytes.
        """
        if not signature:
            raise RazorpayWebhookSignatureError("Missing Razorpay signature header")
        
        if not self.webhook_secret:
            raise RazorpayWebhookSignatureError("RAZORPAY_WEBHOOK_SECRET is not configured")

        if isinstance(body_bytes, bytes):
            body_str = body_bytes.decode("utf-8")
        else:
            body_str = body_bytes

        try:
            self._sdk_client.utility.verify_webhook_signature(
                body_str, signature, self.webhook_secret
            )
            return True
        except Exception as e:
            logger.error("Razorpay webhook signature verification failed.")
            raise RazorpayWebhookSignatureError(f"Signature verification failed: {str(e)}")

    def safe_execute(self, func, *args, **kwargs) -> Dict[str, Any]:
        """Wrap SDK calls in standardized error handling without leaking secrets."""
        try:
            return func(*args, **kwargs)
        except razorpay.errors.BadRequestError as e:
            err_msg = str(e)
            if "401" in err_msg or "Authentication failed" in err_msg or "BAD_REQUEST_ERROR" in err_msg and "auth" in err_msg.lower():
                raise RazorpayAuthenticationError(err_msg)
            if "NOT_FOUND" in err_msg or "does not exist" in err_msg.lower():
                raise RazorpayResourceNotFoundError("resource", "requested_id")
            raise RazorpayInvalidRequestError(err_msg, raw_error={"detail": err_msg})
        except razorpay.errors.ServerError as e:
            raise RazorpayServerError(f"Razorpay server error: {str(e)}")
        except TimeoutError as e:
            raise RazorpayTimeoutError(f"Request timed out: {str(e)}")
        except RazorpayIntegrationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected Razorpay API error: {type(e).__name__}")
            raise RazorpayIntegrationError(f"Razorpay API call failed: {str(e)}")
