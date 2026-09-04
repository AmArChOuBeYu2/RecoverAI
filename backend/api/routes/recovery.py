"""
Recovery REST API Routes — RecoverAI Milestone 10
Provides endpoints for payment failure detection, recovery case retrieval,
rich context assembly, and deterministic eligibility evaluation.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.models.recovery_case import RecoveryCase
from backend.models.enums import RecoveryCaseStatus
from backend.services.detection import DetectionEngine
from backend.services.context_builder import ContextBuilder
from backend.services.eligibility import EligibilityChecker, EligibilityResult

router = APIRouter(prefix="/api/recovery", tags=["recovery"])

@router.post("/detect", response_model=Dict[str, Any])
def run_detection(
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Run DetectionEngine to scan database for unhandled payment failures and initialize recovery cases."""
    cases = DetectionEngine.detect_unhandled_failures(db, limit=limit)
    db.commit()
    return {
        "detected_count": len(cases),
        "cases": [{"id": c.id, "status": c.status, "segment_name": c.segment.name if c.segment else None} for c in cases],
    }

@router.get("/cases", response_model=Dict[str, Any])
def list_recovery_cases(
    status: Optional[str] = Query(None, description="Filter by RecoveryCaseStatus"),
    segment_id: Optional[str] = Query(None, description="Filter by segment ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List recovery cases with optional status and segment filtering."""
    query = db.query(RecoveryCase)
    if status:
        query = query.filter(RecoveryCase.status == status.upper())
    if segment_id:
        query = query.filter(RecoveryCase.segment_id == segment_id)

    total_count = query.count()
    cases = query.order_by(RecoveryCase.detected_at.desc()).offset(offset).limit(limit).all()

    items = []
    for c in cases:
        items.append({
            "id": c.id,
            "transaction_id": c.transaction_id,
            "customer_id": c.customer_id,
            "segment_id": c.segment_id,
            "segment_name": c.segment.name if c.segment else None,
            "status": c.status,
            "attempt_count": c.attempt_count,
            "is_terminal": c.is_terminal,
            "detected_at": c.detected_at.isoformat() if c.detected_at else None,
        })

    return {
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "cases": items,
    }

@router.get("/cases/{case_id}", response_model=Dict[str, Any])
def get_recovery_case_detail(
    case_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed information and assembled context for a specific recovery case ID."""
    case = db.query(RecoveryCase).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")

    context = ContextBuilder.assemble_case_context(db, case)
    return context

@router.get("/context/{case_id}", response_model=Dict[str, Any])
def get_case_context(
    case_id: str,
    db: Session = Depends(get_db),
):
    """Assemble structured context (transaction, customer history, 4D segment, prior actions) for a case."""
    case = db.query(RecoveryCase).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")

    return ContextBuilder.assemble_case_context(db, case)

@router.post("/eligibility/{case_id}", response_model=EligibilityResult)
def evaluate_case_eligibility(
    case_id: str,
    db: Session = Depends(get_db),
):
    """Evaluate deterministic eligibility criteria for a recovery case and advance state machine."""
    case = db.query(RecoveryCase).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")

    result = EligibilityChecker.evaluate_eligibility(db, case)
    db.commit()
    return result
