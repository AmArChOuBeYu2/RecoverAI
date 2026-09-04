"""
Action Authorization Boundary Service
Strictly enforces that financial recovery actions execute ONLY when policy decision is APPROVE.
"""

import logging
from backend.models.recovery_case import RecoveryCase
from backend.services.policy_engine import PolicyEvaluationResult
from backend.models.enums import PolicyDecisionType

logger = logging.getLogger(__name__)

class ActionAuthorizationError(Exception):
    """Raised when an attempt is made to execute an unauthorized recovery action."""
    def __init__(self, decision: str, reason: str):
        message = f"Action execution rejected by authorization boundary: Policy decision is '{decision}' - {reason}"
        super().__init__(message)
        self.decision = decision
        self.reason = reason

class ActionAuthorizationService:
    """Authorization boundary preventing non-APPROVED financial action execution."""

    @staticmethod
    def authorize_action(case: RecoveryCase, policy_result: PolicyEvaluationResult) -> bool:
        """
        Verify action authorization invariant:
        - Must be in non-terminal valid state
        - Policy decision MUST be APPROVE
        - can_execute_action MUST be True
        - DENY or ESCALATE strictly reject action execution
        """
        if policy_result.decision != PolicyDecisionType.APPROVE.value or not policy_result.can_execute_action:
            logger.warning(
                f"Action execution blocked for case '{case.id}': Policy decision '{policy_result.decision}' is not APPROVE"
            )
            raise ActionAuthorizationError(policy_result.decision, policy_result.reason)

        if case.is_terminal:
            logger.warning(f"Action execution blocked for case '{case.id}': Case is in terminal state '{case.status}'")
            raise ActionAuthorizationError("TERMINAL_STATE", f"Case is in terminal state '{case.status}'")

        return True
