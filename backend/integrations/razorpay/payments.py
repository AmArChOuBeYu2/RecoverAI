"""
Razorpay Payment Service Integration
Provides payment retrieval and failure diagnostic metadata fetching.
"""

import logging
from typing import Optional, List
from backend.integrations.razorpay.client import RazorpayClient
from backend.integrations.razorpay.schemas import RazorpayPaymentResponse
from backend.integrations.razorpay.exceptions import RazorpayResourceNotFoundError

logger = logging.getLogger(__name__)

class RazorpayPaymentService:
    """Service wrapper for Razorpay Payment API operations."""

    def __init__(self, client: Optional[RazorpayClient] = None):
        self.client = client or RazorpayClient()

    def fetch_payment(self, payment_id: str) -> RazorpayPaymentResponse:
        """Fetch payment details by payment_id (e.g. pay_...)."""
        if not payment_id:
            raise ValueError("payment_id is required")

        res = self.client.safe_execute(self.client._sdk_client.payment.fetch, payment_id)
        return self._to_payment_response(res)

    def fetch_all_payments(self, count: int = 50, skip: int = 0) -> List[RazorpayPaymentResponse]:
        """Fetch list of payments with pagination (Max count 100 per request)."""
        count = min(count, 100)
        res = self.client.safe_execute(
            self.client._sdk_client.payment.all, {"count": count, "skip": skip}
        )
        items = res.get("items", []) if isinstance(res, dict) else []
        return [self._to_payment_response(item) for item in items]

    def fetch_order_payments(self, order_id: str) -> List[RazorpayPaymentResponse]:
        """Fetch all payment attempts made for a specific order."""
        if not order_id:
            raise ValueError("order_id is required")

        res = self.client.safe_execute(
            self.client._sdk_client.order.payments, order_id
        )
        items = res.get("items", []) if isinstance(res, dict) else []
        return [self._to_payment_response(item) for item in items]

    def _to_payment_response(self, data: dict) -> RazorpayPaymentResponse:
        """Convert raw dict response from SDK to normalized Pydantic DTO."""
        error_details = data.get("error", {}) if isinstance(data.get("error"), dict) else {}
        return RazorpayPaymentResponse(
            id=data.get("id", ""),
            amount=data.get("amount", 0),
            currency=data.get("currency", "INR"),
            status=data.get("status", "failed"),
            order_id=data.get("order_id"),
            method=data.get("method"),
            email=data.get("email"),
            contact=data.get("contact"),
            error_code=data.get("error_code") or error_details.get("code"),
            error_description=data.get("error_description") or error_details.get("description"),
            error_source=data.get("error_source") or error_details.get("source"),
            error_step=data.get("error_step") or error_details.get("step"),
            error_reason=data.get("error_reason") or error_details.get("reason"),
            created_at=data.get("created_at", 0),
            raw_payload=data,
        )
