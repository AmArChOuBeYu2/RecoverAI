"""
Razorpay Integration Package
Exports client, domain services, Pydantic schemas, and custom exceptions.
"""

from backend.integrations.razorpay.client import RazorpayClient
from backend.integrations.razorpay.exceptions import (
    RazorpayIntegrationError,
    RazorpayAuthenticationError,
    RazorpayInvalidRequestError,
    RazorpayResourceNotFoundError,
    RazorpayServerError,
    RazorpayTimeoutError,
    RazorpayWebhookSignatureError,
)
from backend.integrations.razorpay.schemas import (
    RazorpayPaymentResponse,
    RazorpayOrderResponse,
    CreatePaymentLinkRequest,
    RazorpayPaymentLinkResponse,
    RazorpayWebhookPayload,
)
from backend.integrations.razorpay.payments import RazorpayPaymentService
from backend.integrations.razorpay.orders import RazorpayOrderService
from backend.integrations.razorpay.payment_links import RazorpayPaymentLinkService
from backend.integrations.razorpay.webhooks import RazorpayWebhookService

__all__ = [
    "RazorpayClient",
    "RazorpayIntegrationError",
    "RazorpayAuthenticationError",
    "RazorpayInvalidRequestError",
    "RazorpayResourceNotFoundError",
    "RazorpayServerError",
    "RazorpayTimeoutError",
    "RazorpayWebhookSignatureError",
    "RazorpayPaymentResponse",
    "RazorpayOrderResponse",
    "CreatePaymentLinkRequest",
    "RazorpayPaymentLinkResponse",
    "RazorpayWebhookPayload",
    "RazorpayPaymentService",
    "RazorpayOrderService",
    "RazorpayPaymentLinkService",
    "RazorpayWebhookService",
]
