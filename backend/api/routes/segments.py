"""
Segments REST API Routes — RecoverAI Milestone 9
Provides endpoints to list, filter, lookup, and view detailed canonical 4D segment data.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.models.segment import Segment
from backend.models.recovery_strategy import RecoveryStrategy
from backend.services.segmentation import SegmentationService

router = APIRouter(prefix="/api/segments", tags=["segments"])

@router.get("", response_model=Dict[str, Any])
def list_segments(
    failure_category: Optional[str] = Query(None, description="Filter by failure category"),
    payment_method: Optional[str] = Query(None, description="Filter by payment method"),
    amount_range: Optional[str] = Query(None, description="Filter by amount range"),
    customer_type: Optional[str] = Query(None, description="Filter by customer type"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List canonical 4D segments with optional dimensional filtering."""
    query = db.query(Segment)
    if failure_category:
        query = query.filter(Segment.failure_category == failure_category.upper())
    if payment_method:
        query = query.filter(Segment.payment_method == payment_method.lower())
    if amount_range:
        query = query.filter(Segment.amount_range == amount_range.upper())
    if customer_type:
        query = query.filter(Segment.customer_type == customer_type.upper())

    total_count = query.count()
    segments = query.offset(offset).limit(limit).all()

    items = []
    for s in segments:
        strats = db.query(RecoveryStrategy).filter_by(segment_id=s.id).all()
        total_attempts = sum(st.attempt_count for st in strats)
        total_recoveries = sum(st.success_count for st in strats)
        items.append({
            "id": s.id,
            "name": s.name,
            "failure_category": s.failure_category,
            "payment_method": s.payment_method,
            "amount_range": s.amount_range,
            "customer_type": s.customer_type,
            "description": s.description,
            "strategy_count": len(strats),
            "total_attempts": total_attempts,
            "total_recoveries": total_recoveries,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })

    return {
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "segments": items,
    }

@router.get("/lookup", response_model=Dict[str, Any])
def lookup_segment(
    failure_category: str = Query(..., description="Failure category e.g. AUTHENTICATION_FAILURE"),
    payment_method: Optional[str] = Query("card", description="Payment method e.g. card, upi"),
    amount_range: Optional[str] = Query(None, description="Amount range e.g. MID"),
    amount_paise: Optional[int] = Query(None, description="Transaction amount in integer paise"),
    customer_type: Optional[str] = Query("NEW", description="Customer type e.g. NEW, RETURNING"),
    db: Session = Depends(get_db),
):
    """Lookup or auto-create a canonical 4D segment by its dimensional parameters."""
    amt_param = amount_paise if amount_paise is not None else (amount_range or "MID")
    segment = SegmentationService.get_or_create_segment(
        db=db,
        failure_category=failure_category,
        payment_method=payment_method,
        amount_range_or_paise=amt_param,
        customer_type=customer_type,
    )
    db.commit()

    strats = db.query(RecoveryStrategy).filter_by(segment_id=segment.id).all()
    strategies_summary = [
        {
            "strategy_type": st.strategy_type,
            "attempt_count": st.attempt_count,
            "success_count": st.success_count,
            "recovery_rate": st.recovery_rate,
            "wilson_lower_bound": st.wilson_lower_bound,
            "confidence_level": st.confidence_level,
        }
        for st in strats
    ]

    return {
        "id": segment.id,
        "name": segment.name,
        "failure_category": segment.failure_category,
        "payment_method": segment.payment_method,
        "amount_range": segment.amount_range,
        "customer_type": segment.customer_type,
        "description": segment.description,
        "strategies": strategies_summary,
    }

@router.get("/{segment_id}", response_model=Dict[str, Any])
def get_segment_detail(
    segment_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed information and strategy performance records for a specific segment ID."""
    segment = db.query(Segment).filter_by(id=segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail=f"Segment '{segment_id}' not found")

    strats = db.query(RecoveryStrategy).filter_by(segment_id=segment.id).all()
    strategies_detail = [
        {
            "id": st.id,
            "strategy_type": st.strategy_type,
            "attempt_count": st.attempt_count,
            "success_count": st.success_count,
            "total_recovered_paise": st.total_recovered_paise,
            "recovery_rate": st.recovery_rate,
            "wilson_lower_bound": st.wilson_lower_bound,
            "sample_size_sufficient": st.sample_size_sufficient,
            "confidence_level": st.confidence_level,
            "data_source": st.data_source,
        }
        for st in strats
    ]

    return {
        "id": segment.id,
        "name": segment.name,
        "failure_category": segment.failure_category,
        "payment_method": segment.payment_method,
        "amount_range": segment.amount_range,
        "customer_type": segment.customer_type,
        "description": segment.description,
        "created_at": segment.created_at.isoformat() if segment.created_at else None,
        "strategies": strategies_detail,
    }
