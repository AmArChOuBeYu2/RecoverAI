"""
Centralized Recovery State Machine Service
Enforces strict valid state transitions, terminal state immutability, and failure auditing.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session
from backend.models.recovery_case import RecoveryCase
from backend.models.enums import RecoveryCaseStatus
from backend.models.audit_event import AuditEvent

logger = logging.getLogger(__name__)

class InvalidStateTransitionError(Exception):
    """Raised when an illegal state transition is attempted on a RecoveryCase."""
    def __init__(self, current_status: str, target_status: str):
        message = f"Invalid state transition from '{current_status}' to '{target_status}'"
        super().__init__(message)
        self.current_status = current_status
        self.target_status = target_status

class StateMachineService:
    """Centralized State Machine controller for RecoveryCase entity transitions."""

    VALID_TRANSITIONS = {
        RecoveryCaseStatus.DETECTED.value: {RecoveryCaseStatus.ANALYZED.value},
        RecoveryCaseStatus.ANALYZED.value: {RecoveryCaseStatus.SEGMENTED.value},
        RecoveryCaseStatus.SEGMENTED.value: {
            RecoveryCaseStatus.ELIGIBLE.value,
            RecoveryCaseStatus.INELIGIBLE.value,
        },
        RecoveryCaseStatus.ELIGIBLE.value: {RecoveryCaseStatus.STRATEGIES_EVALUATED.value},
        RecoveryCaseStatus.STRATEGIES_EVALUATED.value: {
            RecoveryCaseStatus.POLICY_APPROVED.value,
            RecoveryCaseStatus.POLICY_BLOCKED.value,
            RecoveryCaseStatus.ESCALATED.value,
        },
        RecoveryCaseStatus.POLICY_APPROVED.value: {RecoveryCaseStatus.ACTION_ATTEMPTED.value},
        RecoveryCaseStatus.ACTION_ATTEMPTED.value: {
            RecoveryCaseStatus.AWAITING_VERIFICATION.value,
            RecoveryCaseStatus.ESCALATED.value,
        },


        RecoveryCaseStatus.AWAITING_VERIFICATION.value: {
            RecoveryCaseStatus.RECOVERED.value,
            RecoveryCaseStatus.UNRECOVERED.value,
            RecoveryCaseStatus.ESCALATED.value,
        },
    }

    TERMINAL_STATES = {
        RecoveryCaseStatus.RECOVERED.value,
        RecoveryCaseStatus.UNRECOVERED.value,
        RecoveryCaseStatus.INELIGIBLE.value,
        RecoveryCaseStatus.POLICY_BLOCKED.value,
        RecoveryCaseStatus.ESCALATED.value,
    }

    @classmethod
    def can_transition(cls, current_status: str, target_status: str) -> bool:
        """Check if a transition from current_status to target_status is valid."""
        allowed = cls.VALID_TRANSITIONS.get(current_status, set())
        return target_status in allowed

    @classmethod
    def transition_to(
        cls,
        db: Session,
        case: RecoveryCase,
        target_status: str,
        actor: str = "SYSTEM",
        reason: Optional[str] = None,
    ) -> RecoveryCase:
        """
        Transition a RecoveryCase to target_status.
        Enforces validity rules:
        - If invalid: raises InvalidStateTransitionError, leaves case.status unchanged, logs audit event.
        - If valid: updates case.status, sets is_terminal if applicable, logs state transition audit.
        """
        current_status = case.status

        # If already in a terminal state, reject further transitions
        if case.is_terminal or current_status in cls.TERMINAL_STATES:
            err_msg = f"Cannot transition case '{case.id}' from terminal state '{current_status}' to '{target_status}'"
            logger.warning(err_msg)
            cls._log_blocked_transition(db, case, current_status, target_status, actor, "Terminal state protection")
            raise InvalidStateTransitionError(current_status, target_status)

        # Validate allowed graph transition
        if not cls.can_transition(current_status, target_status):
            err_msg = f"Illegal transition from '{current_status}' to '{target_status}' for case '{case.id}'"
            logger.warning(err_msg)
            cls._log_blocked_transition(db, case, current_status, target_status, actor, reason or "Graph constraint violation")
            raise InvalidStateTransitionError(current_status, target_status)

        # Execute valid transition
        case.status = target_status
        if target_status in cls.TERMINAL_STATES:
            case.is_terminal = True

        audit_event = AuditEvent(
            recovery_case_id=case.id,
            event_type="STATE_TRANSITION",
            actor=actor,
            description=f"State transitioned from {current_status} -> {target_status}",
            details={"from": current_status, "to": target_status, "reason": reason},
        )
        db.add(audit_event)
        db.flush()
        return case

    @classmethod
    def _log_blocked_transition(
        cls, db: Session, case: RecoveryCase, current_status: str, target_status: str, actor: str, reason: str
    ):
        """Log an immutable audit event for a blocked invalid state transition attempt."""
        audit_event = AuditEvent(
            recovery_case_id=case.id,
            event_type="INVALID_STATE_TRANSITION_BLOCKED",
            actor=actor,
            description=f"Blocked invalid state transition from {current_status} -> {target_status}",
            details={"current_status": current_status, "attempted_status": target_status, "reason": reason},
        )
        db.add(audit_event)
        db.flush()
