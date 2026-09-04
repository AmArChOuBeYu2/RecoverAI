"""
Audit Service — RecoverAI Milestone 19
Provides centralized immutable audit logging, event querying, correlation tracking,
and chronological case timeline generation across all domain pipeline steps.
"""

import logging
import uuid
from enum import Enum
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


class AuditActor(str, Enum):
    """
    Canonical Actor Taxonomy for RecoverAI Audit Trail.
    Every audit event producer MUST map to one of these 6 canonical actors.
    """
    SYSTEM = "SYSTEM"
    AI_AGENT = "AI_AGENT"
    POLICY_ENGINE = "POLICY_ENGINE"
    ACTION_EXECUTOR = "ACTION_EXECUTOR"
    VERIFICATION_SERVICE = "VERIFICATION_SERVICE"
    HUMAN_OPERATOR = "HUMAN_OPERATOR"

    @classmethod
    def normalize(cls, actor_val: str) -> str:
        """
        Normalizes input actor strings to the canonical AuditActor enum value.
        Raises ValueError if the actor string cannot be resolved to a canonical actor.
        """
        if not actor_val or not isinstance(actor_val, str):
            raise ValueError(f"Actor must be a non-empty string. Got: {actor_val}")
        
        upper_val = actor_val.strip().upper()

        for member in cls:
            if upper_val == member.value:
                return member.value

        alias_map = {
            "SYSTEM": cls.SYSTEM.value,
            "RAZORPAY_WEBHOOK": cls.SYSTEM.value,
            "AI:OPENAI": cls.AI_AGENT.value,
            "AI:GEMINI": cls.AI_AGENT.value,
            "AI:DETERMINISTIC": cls.AI_AGENT.value,
            "AI_AGENT": cls.AI_AGENT.value,
            "POLICY": cls.POLICY_ENGINE.value,
            "POLICY_ENGINE": cls.POLICY_ENGINE.value,
            "RAZORPAY": cls.ACTION_EXECUTOR.value,
            "SIMULATOR": cls.ACTION_EXECUTOR.value,
            "ACTION_EXECUTOR": cls.ACTION_EXECUTOR.value,
            "VERIFICATION": cls.VERIFICATION_SERVICE.value,
            "VERIFICATION_SERVICE": cls.VERIFICATION_SERVICE.value,
            "HUMAN": cls.HUMAN_OPERATOR.value,
            "HUMAN_OPERATOR": cls.HUMAN_OPERATOR.value,
        }

        if upper_val in alias_map:
            return alias_map[upper_val]

        allowed = [a.value for a in cls]
        raise ValueError(f"Invalid actor '{actor_val}'. Allowed canonical actors: {allowed}")


# Legacy constant aliases for backwards compatibility
ACTOR_SYSTEM = AuditActor.SYSTEM.value
ACTOR_AI_OPENAI = AuditActor.AI_AGENT.value
ACTOR_AI_GEMINI = AuditActor.AI_AGENT.value
ACTOR_AI_DETERMINISTIC = AuditActor.AI_AGENT.value
ACTOR_POLICY = AuditActor.POLICY_ENGINE.value
ACTOR_RAZORPAY = AuditActor.ACTION_EXECUTOR.value
ACTOR_SIMULATOR = AuditActor.ACTION_EXECUTOR.value


class AuditService:
    """
    Centralized Audit Engine for RecoverAI.
    Manages audit event recording, timeline construction, and context correlation.

    Immutability & Transaction Semantics:
    - Append-only write model: Only appends new events; provides no update or delete operations.
    - Transactionally bound: Calls `db.flush()`. If audit creation fails, the database session
      flushes an exception, rolling back the current transaction and preventing silent audit omission.
    - Sanitization: All payload details are stripped of sensitive API keys, bearer tokens, credentials,
      and payment tokens via `sanitize_payload`.
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
        2. Actor normalized to canonical AuditActor enum taxonomy (raises ValueError on invalid actor).
        3. Sanitized details payload (zero credential leakage).
        4. Webhook idempotency via unique event_id when provided.
        5. Batch run correlation stored in details if batch_run_id provided.
        6. Transactional binding via db.flush().
        """
        canonical_actor = AuditActor.normalize(actor)

        payload = sanitize_payload(details) if details else {}
        if batch_run_id and "batch_run_id" not in payload:
            payload["batch_run_id"] = batch_run_id

        audit_entry = AuditEvent(
            recovery_case_id=recovery_case_id,
            event_type=event_type,
            event_id=event_id,
            actor=canonical_actor,
            description=description,
            details=payload,
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit_entry)
        db.flush()
        logger.debug(f"Audit event logged: [{event_type}] {description} (Case: {recovery_case_id}, Actor: {canonical_actor})")
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
        Uses deterministic tie-breaker (created_at asc, id asc).
        """
        query = db.query(AuditEvent).filter_by(recovery_case_id=recovery_case_id)
        if event_type:
            query = query.filter_by(event_type=event_type)
        return query.order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc()).limit(limit).all()

    @classmethod
    def get_timeline_for_case(
        cls,
        db: Session,
        recovery_case_id: str,
    ) -> Dict[str, Any]:
        """
        Generate a structured, human-readable timeline for a recovery case,
        grouping events into key lifecycle milestones in deterministic chronological order.
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
        Deterministic tie-breaker sorting (created_at desc, id desc).
        """
        query = db.query(AuditEvent)

        if recovery_case_id:
            query = query.filter(AuditEvent.recovery_case_id == recovery_case_id)
        if event_type:
            query = query.filter(AuditEvent.event_type == event_type)
        if actor:
            canonical_actor = AuditActor.normalize(actor)
            query = query.filter(AuditEvent.actor == canonical_actor)
        if start_time:
            query = query.filter(AuditEvent.created_at >= start_time)
        if end_time:
            query = query.filter(AuditEvent.created_at <= end_time)
        if batch_run_id:
            query = query.filter(AuditEvent.details.like(f'%"batch_run_id": "{batch_run_id}"%'))

        return query.order_by(desc(AuditEvent.created_at), desc(AuditEvent.id)).offset(offset).limit(limit).all()

