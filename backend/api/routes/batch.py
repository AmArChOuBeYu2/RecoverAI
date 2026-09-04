"""
Batch Runs REST API Routes — RecoverAI Milestone 20
Provides endpoints for listing, filtering, and querying batch execution run records.
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.models.batch_run import BatchRun

router = APIRouter(prefix="/api/batch", tags=["batch"])

@router.get("/runs", response_model=Dict[str, Any])
def list_batch_runs(
    status: Optional[str] = Query(None, description="Filter by status e.g. COMPLETED, FAILED"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List historical batch processing execution runs."""
    query = db.query(BatchRun)
    if status:
        query = query.filter(BatchRun.status == status.upper())

    total_count = query.count()
    runs = query.order_by(BatchRun.started_at.desc()).offset(offset).limit(limit).all()

    items = []
    for r in runs:
        items.append({
            "id": r.id,
            "run_name": r.run_name,
            "status": r.status,
            "total_processed": r.total_processed,
            "success_count": r.success_count,
            "total_recovered_paise": r.total_recovered_paise,
            "total_recovered_rupees": round(r.total_recovered_paise / 100.0, 2),
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        })

    return {
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "runs": items,
    }

@router.get("/runs/{run_id}", response_model=Dict[str, Any])
def get_batch_run_detail(
    run_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed metrics and status for a specific batch run ID."""
    r = db.query(BatchRun).filter_by(id=run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"Batch run '{run_id}' not found")

    return {
        "id": r.id,
        "run_name": r.run_name,
        "status": r.status,
        "total_processed": r.total_processed,
        "success_count": r.success_count,
        "total_recovered_paise": r.total_recovered_paise,
        "total_recovered_rupees": round(r.total_recovered_paise / 100.0, 2),
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
    }
