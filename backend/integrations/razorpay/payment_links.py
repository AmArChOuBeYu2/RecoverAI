"""
Razorpay Payment Link Service Integration
Provides Payment Link creation, retrieval, and cancellation for recovery actions.
"""

import logging
from typing import Optional, Dict, Any
from backend.integrations.razorpay.client import RazorpayClient
from backend.integrations.razorpay.schemas import CreatePaymentLinkRequest, RazorpayPaymentLinkResponse
from backend.integrations.razorpay.exceptions import RazorpayInvalidRequestError

logger = logging.getLogger(__name__)

class RazorpayPaymentLinkService:
    """Service wrapper for Razorpay Payment Links API operations."""

    def __init__(self, client: Optional[RazorpayClient] = None):
        self.client = client or RazorpayClient()

    def create_payment_link(self, req: CreatePaymentLinkRequest) -> RazorpayPaymentLinkResponse:
        """
        Create a Payment Link in Razorpay Test Mode.
        NOTE: Creating a payment link is an ACTION, NOT RECOVERY.
        It does not alter the recovery case state to RECOVERED or claim revenue.
        """
        payload: Dict[str, Any] = {
            "amount": req.amount_paise,
            "currency": req.currency,
            "description": req.description,
            "reference_id": req.reference_id,
            "notify": {
                "sms": req.notify_sms,
                "email": req.notify_email,
            },
            "reminder_enable": req.reminder_enable,
        }

        if req.expire_by:
            payload["expire_by"] = req.expire_by

        customer_data = {}
        if req.customer_name:
            customer_data["name"] = req.customer_name
        if req.customer_email:
            customer_data["email"] = req.customer_email
        if req.customer_contact:
            customer_data["contact"] = req.customer_contact
        if customer_data:
            payload["customer"] = customer_data

        if req.notes:
            payload["notes"] = req.notes

        res = self.client.safe_execute(
            self.client._sdk_client.payment_link.create, payload
        )
        return self._to_link_response(res)

    def fetch_payment_link(self, link_id: str) -> RazorpayPaymentLinkResponse:
        """Fetch status and details of a Payment Link by plink_id."""
        if not link_id:
            raise ValueError("link_id is required")

        res = self.client.safe_execute(
            self.client._sdk_client.payment_link.fetch, link_id
        )
        return self._to_link_response(res)

    def cancel_payment_link(self, link_id: str) -> RazorpayPaymentLinkResponse:
        """Cancel an active Payment Link in Razorpay."""
        if not link_id:
            raise ValueError("link_id is required")

        res = self.client.safe_execute(
            self.client._sdk_client.payment_link.cancel, link_id
        )
        return self._to_link_response(res)

    def _to_link_response(self, data: dict) -> RazorpayPaymentLinkResponse:
        """Convert raw dict response from SDK to normalized Pydantic DTO."""
        customer_info = data.get("customer", {}) if isinstance(data.get("customer"), dict) else {}
        return RazorpayPaymentLinkResponse(
            id=data.get("id", ""),
            amount=data.get("amount", 0),
            currency=data.get("currency", "INR"),
            status=data.get("status", "created"),
            short_url=data.get("short_url", ""),
            reference_id=data.get("reference_id"),
            description=data.get("description"),
            customer_name=customer_info.get("name"),
            customer_email=customer_info.get("email"),
            customer_contact=customer_info.get("contact"),
            expire_by=data.get("expire_by"),
            created_at=data.get("created_at", 0),
            raw_payload=data,
        )
