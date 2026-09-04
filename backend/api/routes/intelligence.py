"""
Recovery Intelligence API Routes for RecoverAI
Provides endpoints for portfolio revenue-at-risk analysis, strategy comparison & Wilson rankings,
explainable recoverability scoring, and hierarchical evidence traces.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.services.recovery_intelligence import RecoveryIntelligenceService

router = APIRouter(prefix="/api/intelligence", tags=["Recovery Intelligence"])

# Load observed dataset for fallback in-memory intelligence
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OBSERVED_OUTCOMES_PATH = PROJECT_ROOT / "data" / "observed" / "outcomes.json"
OBSERVED_TXNS_PATH = PROJECT_ROOT / "data" / "observed" / "transactions.json"
OBSERVED_CUSTS_PATH = PROJECT_ROOT / "data" / "observed" / "customers.json"

def _load_observed_dataset():
    outcomes = []
    transactions = []
    customers_map = {}
    if OBSERVED_OUTCOMES_PATH.exists():
        with open(OBSERVED_OUTCOMES_PATH, "r", encoding="utf-8") as f:
            outcomes = json.load(f)
    if OBSERVED_TXNS_PATH.exists():
        with open(OBSERVED_TXNS_PATH, "r", encoding="utf-8") as f:
            transactions = json.load(f)
    if OBSERVED_CUSTS_PATH.exists():
        with open(OBSERVED_CUSTS_PATH, "r", encoding="utf-8") as f:
            custs = json.load(f)
            customers_map = {c["id"]: c for c in custs}
    return outcomes, transactions, customers_map

class RecoverabilityRequest(BaseModel):
    id: Optional[str] = "txn_demo_001"
    failure_category: str = Field(..., json_schema_extra={"example": "AUTHENTICATION_FAILURE"})
    payment_method: Optional[str] = Field("card", json_schema_extra={"example": "card"})
    amount_paise: int = Field(..., json_schema_extra={"example": 150000})
    customer_type: Optional[str] = Field("RETURNING", json_schema_extra={"example": "RETURNING"})
    attempt_count: int = Field(0, json_schema_extra={"example": 1})
    failed_at: Optional[str] = None
    contacts_count_24h: Optional[int] = 0

@router.get("/portfolio", summary="Fetch portfolio revenue at risk & recovery opportunities")
def get_portfolio_intelligence(db: Session = Depends(get_db)):
    outcomes, transactions, cust_map = _load_observed_dataset()
    service = RecoveryIntelligenceService(observed_outcomes=outcomes, db=db)
    return service.get_portfolio_opportunity(transactions, cust_map)

@router.get("/segments", summary="List canonical 4D segment profiles")
def list_segment_profiles(db: Session = Depends(get_db)):
    outcomes, transactions, cust_map = _load_observed_dataset()
    service = RecoveryIntelligenceService(observed_outcomes=outcomes, db=db)
    metrics = service.get_portfolio_opportunity(transactions, cust_map)
    return {
        "total_canonical_segments": metrics["total_canonical_segments"],
        "sample_size_tiers": metrics["sample_size_tiers"],
        "top_segments": metrics["top_opportunity_segments"],
    }

@router.get("/strategies/compare", summary="Compare candidate strategies using Wilson lower bounds")
def compare_strategies(
    failure_category: str = Query("AUTHENTICATION_FAILURE"),
    payment_method: Optional[str] = Query("card"),
    amount_range: str = Query("MID"),
    customer_type: Optional[str] = Query("RETURNING"),
    db: Session = Depends(get_db),
):
    outcomes, _, _ = _load_observed_dataset()
    service = RecoveryIntelligenceService(observed_outcomes=outcomes, db=db)
    return service.compare_strategies(
        failure_category=failure_category,
        payment_method=payment_method,
        amount_range=amount_range,
        customer_type=customer_type,
    )

@router.post("/recoverability", summary="Compute transparent recoverability propensity score")
def compute_recoverability(payload: RecoverabilityRequest):
    service = RecoveryIntelligenceService()
    txn_dict = payload.model_dump()
    cust_dict = {"contacts_count_24h": payload.contacts_count_24h or 0}
    return service.get_recoverability(txn_dict, cust_dict)

@router.get("/evidence-trace", summary="Fetch step-by-step fallback evidence trace for a strategy")
def get_evidence_trace(
    failure_category: str = Query("AUTHENTICATION_FAILURE"),
    payment_method: Optional[str] = Query("card"),
    amount_range: str = Query("MID"),
    customer_type: Optional[str] = Query("RETURNING"),
    strategy_type: str = Query("PAYMENT_LINK"),
    db: Session = Depends(get_db),
):
    outcomes, _, _ = _load_observed_dataset()
    service = RecoveryIntelligenceService(observed_outcomes=outcomes, db=db)
    return service.get_evidence_trace(
        failure_category=failure_category,
        payment_method=payment_method,
        amount_range=amount_range,
        customer_type=customer_type,
        strategy_type=strategy_type,
    )
