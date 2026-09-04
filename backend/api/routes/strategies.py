"""
Strategies REST API Routes — RecoverAI Milestone 13
Provides endpoints for strategy performance breakdown, segment-level strategy ranking,
and side-by-side strategy comparison.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.services.strategy_optimizer import StrategyOptimizer
from backend.models.enums import FailureCategory

router = APIRouter(prefix="/api/strategies", tags=["strategies"])

@router.get("", response_model=Dict[str, Any])
def list_strategy_performance(
    failure_category: Optional[str] = Query(None, description="Optional failure category filter"),
    payment_method: Optional[str] = Query(None, description="Optional payment method filter"),
    db: Session = Depends(get_db),
):
    """
    Get portfolio-wide strategy performance breakdown with attempt-weighted recovery rates,
    integer-paise monetary totals, sample size tiers, and evidence category/provenance.
    """
    if failure_category:
        valid_cats = {e.value for e in FailureCategory}
        if failure_category.upper() not in valid_cats:
            raise HTTPException(status_code=400, detail=f"Invalid failure_category '{failure_category}'. Must be one of {valid_cats}")

    summary = StrategyOptimizer.get_strategy_performance_summary(
        db=db,
        failure_category=failure_category,
        payment_method=payment_method,
    )
    return summary

@router.get("/compare", response_model=Dict[str, Any])
def compare_candidate_strategies(
    failure_category: str = Query(..., description="Failure category e.g. AUTHENTICATION_FAILURE"),
    payment_method: Optional[str] = Query("card", description="Payment method e.g. card, upi"),
    amount_range: Optional[str] = Query("MID", description="Amount range e.g. LOW, MID, HIGH, PREMIUM"),
    customer_type: Optional[str] = Query("NEW", description="Customer type e.g. NEW, RETURNING, FATIGUED"),
    db: Session = Depends(get_db),
):
    """
    Compare candidate recovery strategies side-by-side for a 4D dimensional lookup.
    Displays recovery rate, Wilson lower bound, expected recovered paise per attempt,
    Economic Strategy Value score, sample tier, and evidence provenance.
    """
    try:
        res = StrategyOptimizer.compare_strategies(
            db=db,
            failure_category=failure_category,
            payment_method=payment_method,
            amount_range=amount_range,
            customer_type=customer_type,
        )
        return res
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

@router.get("/segment/{segment_id}", response_model=Dict[str, Any])
def get_segment_strategy_performance(
    segment_id: str,
    db: Session = Depends(get_db),
):
    """
    Get strategy performance breakdown and ranked candidate strategies for a specific segment ID.
    Differentiates nonexistent segment (HTTP 404) from segment with zero attempts (HTTP 200 with INSUFFICIENT evidence).
    """
    res = StrategyOptimizer.get_segment_strategy_performance(db=db, segment_id=segment_id)
    if res is None:
        raise HTTPException(status_code=404, detail=f"Segment '{segment_id}' not found")
    return res
