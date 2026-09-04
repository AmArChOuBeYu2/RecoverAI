"""
Dashboard REST API Routes — RecoverAI Milestone 20
Provides executive dashboard metrics, portfolio recovery performance indicators,
and unrecovered failure root cause breakdowns.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.services.metrics import MetricsService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/summary", response_model=Dict[str, Any])
def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    Get executive dashboard summary KPIs, portfolio monetary totals (in integer paise and rupees),
    case & revenue recovery rates, action success rate, duplicate action preventions, and API error rates.
    """
    return MetricsService.compute_portfolio_metrics(db)

@router.get("/failure-breakdown", response_model=Dict[str, Any])
def get_failure_breakdown(db: Session = Depends(get_db)):
    """
    Get detailed breakdown of unrecovered revenue categorized by root cause and policy block reason.
    """
    return MetricsService.get_failure_analysis_breakdown(db)
