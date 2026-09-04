"""
Razorpay Webhook API Route Handler
Thin FastAPI handler parsing raw body and delegating processing to IngestionService.
"""

from fastapi import APIRouter, Request, Header, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.services.ingestion import IngestionService
from backend.integrations.razorpay import RazorpayWebhookSignatureError, RazorpayInvalidRequestError

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

@router.post("/razorpay")
async def handle_razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
    db: Session = Depends(get_db),
):
    """
    Ingest Razorpay webhook event.
    Verifies raw HMAC-SHA256 signature and processes domain updates with DB idempotency.
    """
    if not x_razorpay_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'X-Razorpay-Signature' header",
        )

    # Preserve exact raw body bytes for signature verification
    raw_body = await request.body()

    ingestion_service = IngestionService()
    try:
        result = ingestion_service.process_webhook_request(
            db=db, raw_body=raw_body, signature=x_razorpay_signature
        )
        return result
    except RazorpayWebhookSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RazorpayInvalidRequestError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing webhook: {str(e)}",
        )
