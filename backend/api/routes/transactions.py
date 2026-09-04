"""
Transactions REST API Routes — RecoverAI Milestone 20
Provides endpoints for listing, filtering, and inspecting transactions.
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.models.transaction import Transaction
from backend.models.recovery_case import RecoveryCase

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

@router.get("", response_model=Dict[str, Any])
def list_transactions(
    status: Optional[str] = Query(None, description="Filter by status e.g. FAILED, CAPTURED"),
    failure_category: Optional[str] = Query(None, description="Filter by failure category e.g. AUTHENTICATION_FAILURE"),
    payment_method: Optional[str] = Query(None, description="Filter by payment method e.g. card, upi"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List transactions with optional filtering and pagination."""
    query = db.query(Transaction)
    if status:
        query = query.filter(Transaction.status == status.upper())
    if failure_category:
        query = query.filter(Transaction.failure_category == failure_category.upper())
    if payment_method:
        query = query.filter(Transaction.payment_method == payment_method.lower())

    total_count = query.count()
    txns = query.order_by(Transaction.created_at.desc()).offset(offset).limit(limit).all()

    items = []
    for t in txns:
        case = db.query(RecoveryCase).filter_by(transaction_id=t.id).first()
        items.append({
            "id": t.id,
            "razorpay_payment_id": t.razorpay_payment_id,
            "customer_id": t.customer_id,
            "amount_paise": t.amount_paise,
            "amount_rupees": round(t.amount_paise / 100.0, 2),
            "currency": t.currency,
            "status": t.status,
            "failure_category": t.failure_category,
            "payment_method": t.payment_method,
            "error_code": t.error_code,
            "error_description": t.error_description,
            "has_recovery_case": case is not None,
            "recovery_case_id": case.id if case else None,
            "recovery_case_status": case.status if case else None,
            "failed_at": t.created_at.isoformat() if t.created_at else None,
        })

    return {
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "transactions": items,
    }

@router.get("/{txn_id}", response_model=Dict[str, Any])
def get_transaction_detail(
    txn_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed transaction data, customer profile, and linked recovery case."""
    t = db.query(Transaction).filter_by(id=txn_id).first()
    if not t:
        raise HTTPException(status_code=404, detail=f"Transaction '{txn_id}' not found")

    case = db.query(RecoveryCase).filter_by(transaction_id=t.id).first()

    return {
        "id": t.id,
        "razorpay_payment_id": t.razorpay_payment_id,
        "razorpay_order_id": t.razorpay_order_id,
        "customer_id": t.customer_id,
        "customer_name": t.customer.name if t.customer else None,
        "customer_email": t.customer.email if t.customer else None,
        "amount_paise": t.amount_paise,
        "amount_rupees": round(t.amount_paise / 100.0, 2),
        "currency": t.currency,
        "status": t.status,
        "failure_category": t.failure_category,
        "payment_method": t.payment_method,
        "error_code": t.error_code,
        "error_description": t.error_description,
        "has_recovery_case": case is not None,
        "recovery_case": {
            "id": case.id,
            "status": case.status,
            "attempt_count": case.attempt_count,
            "is_eligible": case.is_eligible,
            "is_terminal": case.is_terminal,
            "segment_id": case.segment_id,
            "segment_name": case.segment.name if case and case.segment else None,
        } if case else None,
        "failed_at": t.created_at.isoformat() if t.created_at else None,
    }
