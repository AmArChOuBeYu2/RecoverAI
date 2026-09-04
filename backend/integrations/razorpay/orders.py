"""
Razorpay Order Service Integration
Provides order creation, retrieval, and checkout abandonment detection input.
"""

import logging
from typing import Optional, List, Dict, Any
from backend.integrations.razorpay.client import RazorpayClient
from backend.integrations.razorpay.schemas import RazorpayOrderResponse

logger = logging.getLogger(__name__)

class RazorpayOrderService:
    """Service wrapper for Razorpay Orders API operations."""

    def __init__(self, client: Optional[RazorpayClient] = None):
        self.client = client or RazorpayClient()

    def create_order(
        self,
        amount_paise: int,
        currency: str = "INR",
        receipt: Optional[str] = None,
        notes: Optional[Dict[str, str]] = None,
    ) -> RazorpayOrderResponse:
        """Create a new Razorpay order."""
        if amount_paise <= 0:
            raise ValueError("amount_paise must be greater than zero")

        payload: Dict[str, Any] = {
            "amount": amount_paise,
            "currency": currency,
        }
        if receipt:
            payload["receipt"] = receipt
        if notes:
            payload["notes"] = notes

        res = self.client.safe_execute(self.client._sdk_client.order.create, payload)
        return self._to_order_response(res)

    def fetch_order(self, order_id: str) -> RazorpayOrderResponse:
        """Fetch an order by order_id (e.g. order_...)."""
        if not order_id:
            raise ValueError("order_id is required")

        res = self.client.safe_execute(self.client._sdk_client.order.fetch, order_id)
        return self._to_order_response(res)

    def fetch_all_orders(self, count: int = 50, skip: int = 0) -> List[RazorpayOrderResponse]:
        """Fetch list of orders for abandonment detection or state audit."""
        count = min(count, 100)
        res = self.client.safe_execute(
            self.client._sdk_client.order.all, {"count": count, "skip": skip}
        )
        items = res.get("items", []) if isinstance(res, dict) else []
        return [self._to_order_response(item) for item in items]

    def _to_order_response(self, data: dict) -> RazorpayOrderResponse:
        """Convert raw dict response from SDK to normalized Pydantic DTO."""
        return RazorpayOrderResponse(
            id=data.get("id", ""),
            amount=data.get("amount", 0),
            currency=data.get("currency", "INR"),
            status=data.get("status", "created"),
            attempts=data.get("attempts", 0),
            receipt=data.get("receipt"),
            created_at=data.get("created_at", 0),
            raw_payload=data,
        )
