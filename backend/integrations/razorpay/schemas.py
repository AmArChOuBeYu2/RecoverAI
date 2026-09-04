"""
Razorpay Integration Normalized Pydantic Schemas
Defines domain-friendly DTOs for Razorpay requests, responses, and webhooks.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

class RazorpayPaymentResponse(BaseModel):
    """Normalized response schema for a Razorpay payment object."""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    amount_paise: int = Field(alias="amount")
    currency: str = "INR"
    status: str
    order_id: Optional[str] = None
    method: Optional[str] = None
    email: Optional[str] = None
    contact: Optional[str] = None
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    error_source: Optional[str] = None
    error_step: Optional[str] = None
    error_reason: Optional[str] = None
    created_at: int
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

class RazorpayOrderResponse(BaseModel):
    """Normalized response schema for a Razorpay order object."""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    amount_paise: int = Field(alias="amount")
    currency: str = "INR"
    status: str # created, attempted, paid
    attempts: int = 0
    receipt: Optional[str] = None
    created_at: int
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

class CreatePaymentLinkRequest(BaseModel):
    """Request schema for creating a Razorpay Payment Link."""
    amount_paise: int
    currency: str = "INR"
    description: str
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_contact: Optional[str] = None
    reference_id: str = Field(..., max_length=40, description="Maps to recovery case or order ID")
    expire_by: Optional[int] = Field(default=None, description="Unix timestamp")
    notify_sms: bool = False
    notify_email: bool = False
    reminder_enable: bool = False
    notes: Dict[str, str] = Field(default_factory=dict)

class RazorpayPaymentLinkResponse(BaseModel):
    """Normalized response schema for a Razorpay payment link object."""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    amount_paise: int = Field(alias="amount")
    currency: str = "INR"
    status: str # created, paid, expired, cancelled
    short_url: str
    reference_id: Optional[str] = None
    description: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_contact: Optional[str] = None
    expire_by: Optional[int] = None
    created_at: int
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

class RazorpayWebhookPayload(BaseModel):
    """Normalized schema for incoming Razorpay Webhook events."""
    event: str # payment.failed, payment_link.paid, payment_link.expired, etc.
    event_id: str
    created_at: int
    contains: list[str] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(default_factory=dict)
