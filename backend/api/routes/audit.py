"""
Audit Trail REST API Routes — RecoverAI Milestone 20
Provides endpoints for querying audit logs, filtering by correlation IDs,
and retrieving structured case timelines.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.services.audit import AuditService

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("/events", response_model=Dict[str, Any])
def query_audit_events(
    recovery_case_id: Optional[str] = Query(None, description="Filter by recovery case ID"),
    batch_run_id: Optional[str] = Query(None, description="Filter by batch run correlation ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    actor: Optional[str] = Query(None, description="Filter by canonical actor"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Query audit events with flexible filtering, correlation matching, and pagination."""
    try:
        events = AuditService.query_events(
            db=db,
            recovery_case_id=recovery_case_id,
            batch_run_id=batch_run_id,
            event_type=event_type,
            actor=actor,
            limit=limit,
            offset=offset,
        )

        items = []
        for e in events:
            items.append({
                "id": e.id,
                "recovery_case_id": e.recovery_case_id,
                "event_type": e.event_type,
                "event_id": e.event_id,
                "actor": e.actor,
                "description": e.description,
                "details": e.details,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            })

        return {
            "count": len(items),
            "offset": offset,
            "limit": limit,
            "events": items,
        }
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

@router.get("/events/{recovery_case_id}", response_model=Dict[str, Any])
def get_case_audit_events(
    recovery_case_id: str,
    event_type: Optional[str] = Query(None, description="Filter by specific event type"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get chronological audit log events for a specific recovery case."""
    events = AuditService.get_events_for_case(
        db=db,
        recovery_case_id=recovery_case_id,
        limit=limit,
        event_type=event_type,
    )

    items = []
    for e in events:
        items.append({
            "id": e.id,
            "recovery_case_id": e.recovery_case_id,
            "event_type": e.event_type,
            "actor": e.actor,
            "description": e.description,
            "details": e.details,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        })

    return {
        "recovery_case_id": recovery_case_id,
        "count": len(items),
        "events": items,
    }

@router.get("/timeline/{recovery_case_id}", response_model=Dict[str, Any])
def get_case_timeline(
    recovery_case_id: str,
    db: Session = Depends(get_db),
):
    """Get structured chronological case timeline with grouped milestone events."""
    try:
        timeline = AuditService.get_timeline_for_case(db=db, recovery_case_id=recovery_case_id)
        return timeline
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
