"""
Audit Service — RecoverAI Milestone 19
Provides centralized immutable audit logging, event querying, correlation tracking,
and chronological case timeline generation across all domain pipeline steps.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.models.audit_event import AuditEvent
from backend.models.recovery_case import RecoveryCase
from backend.services.sanitization import sanitize_payload

logger = logging.getLogger(__name__)

# Standardized Event Types
EVENT_TYPE_DETECTED = "DETECTED"
EVENT_TYPE_SEGMENTED = "SEGMENTED"
EVENT_TYPE_ELIGIBILITY_CHECKED = "ELIGIBILITY_CHECKED"
EVENT_TYPE_AI_DIAGNOSIS = "AI_DIAGNOSIS"
EVENT_TYPE_STRATEGY_EVALUATED = "STRATEGY_EVALUATED"
EVENT_TYPE_STRATEGY_SELECTED = "STRATEGY_SELECTED"
EVENT_TYPE_POLICY_EVALUATED = "POLICY_EVALUATED"
EVENT_TYPE_POLICY_APPROVED = "POLICY_APPROVED"
EVENT_TYPE_POLICY_BLOCKED = "POLICY_BLOCKED"
EVENT_TYPE_ACTION_EXECUTED = "ACTION_EXECUTED"
EVENT_TYPE_ACTION_EXECUTION_FAILED = "ACTION_EXECUTION_FAILED"
EVENT_TYPE_VERIFICATION_CHECKED = "VERIFICATION_CHECKED"
EVENT_TYPE_OUTCOME_ATTRIBUTED = "OUTCOME_ATTRIBUTED"
EVENT_TYPE_RECOVERY_RESULT = "RECOVERY_RESULT"
EVENT_TYPE_WEBHOOK_RECEIVED = "WEBHOOK_RECEIVED"
EVENT_TYPE_FALLBACK_USED = "FALLBACK_USED"
EVENT_TYPE_BATCH_PROCESSING_ERROR = "BATCH_PROCESSING_ERROR"

# Standardized Actors
ACTOR_SYSTEM = "system"
ACTOR_AI_OPENAI = "ai:openai"
ACTOR_AI_GEMINI = "ai:gemini"
ACTOR_AI_DETERMINISTIC = "ai:deterministic"
ACTOR_POLICY = "policy"
ACTOR_RAZORPAY = "razorpay"
ACTOR_SIMULATOR = "simulator"

class AuditService:
    """
    Centralized Audit Engine for RecoverAI.
    Manages audit event recording, timeline construction, and context correlation.
    """

    @classmethod
    def log_event(
        cls,
        db: Session,
        event_type: str,
        description: str,
        recovery_case_id: Optional[str] = None,
        actor: str = ACTOR_SYSTEM,
        details: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
        batch_run_id: Optional[str] = None,
    ) -> AuditEvent:
        """
        Record a new immutable AuditEvent in the database.
        
        Guarantees:
        1. Non-null description and event_type.
        2. Sanitized details payload.
        3. Webhook idempotency via unique event_id when provided.
        4. Batch run correlation stored in details if batch_run_id provided.
        """
        payload = sanitize_payload(details) if details else {}
        if batch_run_id and "batch_run_id" not in payload:
            payload["batch_run_id"] = batch_run_id

        audit_entry = AuditEvent(
            recovery_case_id=recovery_case_id,
            event_type=event_type,
            event_id=event_id,
            actor=actor,
            description=description,
            details=payload,
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit_entry)
        db.flush()
        logger.debug(f"Audit event logged: [{event_type}] {description} (Case: {recovery_case_id})")
        return audit_entry

    @classmethod
    def get_events_for_case(
        cls,
        db: Session,
        recovery_case_id: str,
        limit: int = 100,
        event_type: Optional[str] = None,
    ) -> List[AuditEvent]:
        """
        Retrieve chronological audit events for a specific recovery case.
        """
        query = db.query(AuditEvent).filter_by(recovery_case_id=recovery_case_id)
        if event_type:
            query = query.filter_by(event_type=event_type)
        return query.order_by(AuditEvent.created_at.asc()).limit(limit).all()

    @classmethod
    def get_timeline_for_case(
        cls,
        db: Session,
        recovery_case_id: str,
    ) -> Dict[str, Any]:
        """
        Generate a structured, human-readable timeline for a recovery case,
        grouping events into key lifecycle milestones.
        """
        case = db.query(RecoveryCase).filter_by(id=recovery_case_id).first()
        if not case:
            raise ValueError(f"RecoveryCase with ID '{recovery_case_id}' not found.")

        events = cls.get_events_for_case(db, recovery_case_id, limit=500)

        milestones: List[Dict[str, Any]] = []
        for e in events:
            milestones.append({
                "id": e.id,
                "event_type": e.event_type,
                "actor": e.actor,
                "description": e.description,
                "timestamp": e.created_at.isoformat(),
                "details": e.details,
            })

        return {
            "case_id": case.id,
            "transaction_id": case.transaction_id,
            "status": case.status,
            "is_terminal": case.is_terminal,
            "total_events": len(events),
            "detected_at": case.detected_at.isoformat() if case.detected_at else None,
            "updated_at": case.updated_at.isoformat() if case.updated_at else None,
            "timeline": milestones,
        }

    @classmethod
    def query_events(
        cls,
        db: Session,
        recovery_case_id: Optional[str] = None,
        batch_run_id: Optional[str] = None,
        event_type: Optional[str] = None,
        actor: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEvent]:
        """
        Query audit events with flexible filtering, correlation matching, and pagination.
        """
        query = db.query(AuditEvent)

        if recovery_case_id:
            query = query.filter(AuditEvent.recovery_case_id == recovery_case_id)
        if event_type:
            query = query.filter(AuditEvent.event_type == event_type)
        if actor:
            query = query.filter(AuditEvent.actor == actor)
        if start_time:
            query = query.filter(AuditEvent.created_at >= start_time)
        if end_time:
            query = query.filter(AuditEvent.created_at <= end_time)
        if batch_run_id:
            query = query.filter(AuditEvent.details.like(f'%"batch_run_id": "{batch_run_id}"%'))

        return query.order_by(desc(AuditEvent.created_at)).offset(offset).limit(limit).all()
