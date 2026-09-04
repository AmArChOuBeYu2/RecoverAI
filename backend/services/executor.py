"""
Action Executor Service
Executes policy-authorized recovery actions (PAYMENT_LINK, REMINDER, DELAYED_RETRY, etc.),
enforces REAL vs SIMULATED execution mode caps (MAX_REAL_PAYMENT_LINKS), integrates Razorpay SDK,
preserves state machine transitions, and logs audit events.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.recovery_case import RecoveryCase
from backend.models.recovery_decision import RecoveryDecision
from backend.models.recovery_action import RecoveryAction
from backend.models.audit_event import AuditEvent
from backend.models.enums import (
    RecoveryCaseStatus,
    ActionExecutionMode,
    PolicyDecisionType,
    StrategyType,
)
from backend.services.authorization import ActionAuthorizationService, ActionAuthorizationError
from backend.services.trust_gate import TrustGateService, TrustGateResult
from backend.services.state_machine import StateMachineService

from backend.services.sanitization import sanitize_payload
from backend.integrations.razorpay.payment_links import RazorpayPaymentLinkService
from backend.integrations.razorpay.schemas import CreatePaymentLinkRequest
from backend.integrations.razorpay.exceptions import RazorpayIntegrationError


logger = logging.getLogger(__name__)

class ActionExecutionError(Exception):
    """Raised when action execution fails due to system error or API failure."""
    pass

class ActionExecutor:
    """
    Centralized execution engine for recovery actions.
    
    Invariants:
    1. AI Recommends -> Policy Decides -> Code Authorizes -> Action Executes.
    2. Zero execution occurs without PolicyDecisionType.APPROVE.
    3. TrustGate safety verification must pass.
    4. Bounded REAL payment link creation (MAX_REAL_PAYMENT_LINKS).
    5. Integer-paise amounts preserved in all payment link payloads.
    6. Valid state transitions: POLICY_APPROVED -> ACTION_ATTEMPTED -> AWAITING_VERIFICATION (or ESCALATED).
    """

    def __init__(self, payment_link_service: Optional[RazorpayPaymentLinkService] = None):
        self.payment_link_service = payment_link_service or RazorpayPaymentLinkService()

    def get_real_payment_link_count(self, db: Session) -> int:
        """Count total REAL_TEST_MODE payment link actions executed across all cases."""
        return db.query(RecoveryAction).filter(
            RecoveryAction.action_type == StrategyType.PAYMENT_LINK.value,
            RecoveryAction.execution_mode == ActionExecutionMode.REAL_TEST_MODE.value,
            RecoveryAction.razorpay_payment_link_id.isnot(None)
        ).count()

    def determine_execution_mode(self, db: Session, action_type: str) -> Tuple[str, str]:
        """
        Determine execution_mode and notification_mode based on action_type and config limits.
        
        Returns:
            (execution_mode, notification_mode)
        """
        if action_type != StrategyType.PAYMENT_LINK.value:
            return ActionExecutionMode.SIMULATED.value, "SIMULATED"

        # Check if Razorpay credentials exist
        has_credentials = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
        if not has_credentials:
            return ActionExecutionMode.SIMULATED.value, "SIMULATED"

        # Check real payment links cap
        real_count = self.get_real_payment_link_count(db)
        if real_count >= settings.MAX_REAL_PAYMENT_LINKS:
            logger.info(
                f"MAX_REAL_PAYMENT_LINKS limit ({settings.MAX_REAL_PAYMENT_LINKS}) reached (current: {real_count}). "
                "Executing PAYMENT_LINK in SIMULATED mode."
            )
            return ActionExecutionMode.SIMULATED.value, "SIMULATED"

        return ActionExecutionMode.REAL_TEST_MODE.value, "RAZORPAY_TEST"

    def execute(
        self,
        db: Session,
        case: RecoveryCase,
        decision: RecoveryDecision,
        actor: str = "SYSTEM",
    ) -> RecoveryAction:
        """
        Execute an authorized recovery action for a recovery case.
        
        Steps:
        1. Verify TrustGate safety for execution.
        2. Verify ActionAuthorizationService policy decision == APPROVE.
        3. Transition state machine POLICY_APPROVED -> ACTION_ATTEMPTED.
        4. Route to specific strategy handler (PAYMENT_LINK, REMINDER, DELAYED_RETRY, ESCALATION, HUMAN_REVIEW, NO_ACTION).
        5. Save RecoveryAction and transition to AWAITING_VERIFICATION (or ESCALATED for escalations/reviews).
        6. Record audit event ACTION_EXECUTED.
        """
        # 1. TrustGate Safety check
        if case.transaction:
            trust_res = TrustGateService.evaluate(case.transaction, case.customer)
            if not trust_res.passed:
                raise ActionAuthorizationError("TRUST_GATE_REJECTED", trust_res.reason)


        # 2. Action Authorization check
        from backend.services.policy_engine import PolicyEngine
        policy_eval_result = PolicyEngine.evaluate(
            case=case,
            proposed_strategy=decision.selected_strategy,
            ai_confidence=decision.ai_confidence,
            db=db,
            persist_decision=True,
        )
        ActionAuthorizationService.authorize_action(case, policy_eval_result)


        # 3. Transition to ACTION_ATTEMPTED if currently in POLICY_APPROVED
        if case.status == RecoveryCaseStatus.POLICY_APPROVED.value:
            StateMachineService.transition_to(
                db, case, RecoveryCaseStatus.ACTION_ATTEMPTED.value, actor=actor, reason="Starting action execution"
            )

        strategy_type = decision.selected_strategy or decision.ai_recommended_strategy or StrategyType.PAYMENT_LINK.value

        execution_mode, notification_mode = self.determine_execution_mode(db, strategy_type)

        # 4. Route strategy handlers
        if strategy_type == StrategyType.PAYMENT_LINK.value:
            action = self._execute_payment_link(db, case, decision, execution_mode, notification_mode)
        elif strategy_type == StrategyType.REMINDER.value:
            action = self._execute_reminder(db, case, decision)
        elif strategy_type == StrategyType.DELAYED_RETRY.value:
            action = self._execute_delayed_retry(db, case, decision)
        elif strategy_type == StrategyType.ESCALATION.value:
            action = self._execute_escalation(db, case, decision)
        elif strategy_type == StrategyType.HUMAN_REVIEW.value:
            action = self._execute_human_review(db, case, decision)
        elif strategy_type == StrategyType.NO_ACTION.value:
            action = self._execute_no_action(db, case, decision)
        else:
            # Fallback to simulated payment link or reminder
            action = self._execute_payment_link(db, case, decision, ActionExecutionMode.SIMULATED.value, "SIMULATED")

        # Increment case attempt count
        case.attempt_count += 1
        db.flush()

        # 5. Transition state machine from ACTION_ATTEMPTED to next state
        if strategy_type in (StrategyType.ESCALATION.value, StrategyType.HUMAN_REVIEW.value):
            StateMachineService.transition_to(
                db, case, RecoveryCaseStatus.ESCALATED.value, actor=actor, reason=f"Action '{strategy_type}' escalated case"
            )
        else:
            StateMachineService.transition_to(
                db, case, RecoveryCaseStatus.AWAITING_VERIFICATION.value, actor=actor, reason=f"Action '{strategy_type}' executed successfully"
            )

        # 6. Audit event
        db.add(AuditEvent(
            recovery_case_id=case.id,
            event_type="ACTION_EXECUTED",
            actor=actor,
            description=f"Executed recovery action '{strategy_type}' in mode '{execution_mode}'",
            details=sanitize_payload({
                "action_id": action.id,
                "action_type": action.action_type,
                "execution_mode": action.execution_mode,
                "razorpay_payment_link_id": action.razorpay_payment_link_id,
                "status": action.status,
                "notification_mode": notification_mode,
            }),
        ))
        db.flush()
        return action

    def _execute_payment_link(
        self,
        db: Session,
        case: RecoveryCase,
        decision: RecoveryDecision,
        execution_mode: str,
        notification_mode: str,
    ) -> RecoveryAction:
        """Execute PAYMENT_LINK action in REAL_TEST_MODE or SIMULATED mode."""
        txn = case.transaction
        amount_paise = txn.amount_paise if txn else 0
        customer_email = case.customer.email if case.customer else None
        customer_contact = case.customer.phone if case.customer else None
        customer_name = case.customer.name if case.customer else "Valued Customer"

        if execution_mode == ActionExecutionMode.REAL_TEST_MODE.value:
            try:
                # 24-hour payment link expiry
                expire_timestamp = int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())
                
                link_req = CreatePaymentLinkRequest(
                    amount_paise=amount_paise,
                    currency=txn.currency if txn else "INR",
                    description=f"RecoverAI Payment Link for Case {case.id[:8]}",
                    reference_id=case.id,
                    customer_name=customer_name,
                    customer_email=customer_email,
                    customer_contact=customer_contact,
                    notify_sms=True,
                    notify_email=True,
                    reminder_enable=True,
                    expire_by=expire_timestamp,
                    notes={
                        "recovery_case_id": case.id,
                        "transaction_id": txn.id if txn else "",
                        "strategy_type": StrategyType.PAYMENT_LINK.value,
                    },
                )

                link_res = self.payment_link_service.create_payment_link(link_req)

                action = RecoveryAction(
                    recovery_case_id=case.id,
                    action_type=StrategyType.PAYMENT_LINK.value,
                    execution_mode=ActionExecutionMode.REAL_TEST_MODE.value,
                    razorpay_payment_link_id=link_res.id,
                    payment_link_url=link_res.short_url,
                    status="SENT",
                    expires_at=datetime.fromtimestamp(expire_timestamp, timezone.utc) if expire_timestamp else None,
                    payload=sanitize_payload({
                        "raw_response": link_res.raw_payload,
                        "notification_mode": notification_mode,
                        "amount_paise": amount_paise,
                    }),
                )
                db.add(action)
                db.flush()
                return action

            except Exception as e:
                logger.error(f"Failed to create REAL Razorpay payment link for case '{case.id}': {e}. Falling back to SIMULATED mode.")
                # Fallback to simulated payment link execution
                execution_mode = ActionExecutionMode.SIMULATED.value
                notification_mode = "SIMULATED"

        # SIMULATED PAYMENT LINK EXECUTION
        sim_plink_id = f"plink_sim_{uuid.uuid4().hex[:12]}"
        sim_short_url = f"https://checkout.razorpay.com/v1/simulated_{sim_plink_id}"

        action = RecoveryAction(
            recovery_case_id=case.id,
            action_type=StrategyType.PAYMENT_LINK.value,
            execution_mode=ActionExecutionMode.SIMULATED.value,
            razorpay_payment_link_id=sim_plink_id,
            payment_link_url=sim_short_url,
            status="SENT",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            payload=sanitize_payload({
                "simulation_label": "SIMULATED_PAYMENT_LINK",
                "notification_mode": notification_mode,
                "amount_paise": amount_paise,
                "reason": "Simulated mode active or real link cap reached",
            }),
        )
        db.add(action)
        db.flush()
        return action

    def _execute_reminder(
        self,
        db: Session,
        case: RecoveryCase,
        decision: RecoveryDecision,
    ) -> RecoveryAction:
        """Execute REMINDER action in SIMULATED mode."""
        action = RecoveryAction(
            recovery_case_id=case.id,
            action_type=StrategyType.REMINDER.value,
            execution_mode=ActionExecutionMode.SIMULATED.value,
            status="SENT",
            payload=sanitize_payload({
                "simulation_label": "SIMULATED_REMINDER_NOTIFICATION",
                "notification_mode": "SIMULATED",
                "message": "Payment reminder notification sent to customer",
            }),
        )
        db.add(action)
        db.flush()
        return action

    def _execute_delayed_retry(
        self,
        db: Session,
        case: RecoveryCase,
        decision: RecoveryDecision,
    ) -> RecoveryAction:
        """Execute DELAYED_RETRY action in SIMULATED mode (scheduled retry)."""
        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=24)
        action = RecoveryAction(
            recovery_case_id=case.id,
            action_type=StrategyType.DELAYED_RETRY.value,
            execution_mode=ActionExecutionMode.SIMULATED.value,
            status="SCHEDULED",
            expires_at=scheduled_time,
            payload=sanitize_payload({
                "simulation_label": "SIMULATED_DELAYED_RETRY",
                "scheduled_for": scheduled_time.isoformat(),
                "delay_hours": 24,
            }),
        )
        db.add(action)
        db.flush()
        return action

    def _execute_escalation(
        self,
        db: Session,
        case: RecoveryCase,
        decision: RecoveryDecision,
    ) -> RecoveryAction:
        """Execute ESCALATION action (flags case for support escalation)."""
        action = RecoveryAction(
            recovery_case_id=case.id,
            action_type=StrategyType.ESCALATION.value,
            execution_mode=ActionExecutionMode.SIMULATED.value,
            status="ESCALATED",
            payload=sanitize_payload({
                "simulation_label": "CASE_ESCALATED",
                "reason": decision.reasoning_summary or "Escalation requested by policy or decision engine",
            }),
        )
        db.add(action)
        db.flush()
        return action

    def _execute_human_review(
        self,
        db: Session,
        case: RecoveryCase,
        decision: RecoveryDecision,
    ) -> RecoveryAction:
        """Execute HUMAN_REVIEW action (flags case for manual review)."""
        action = RecoveryAction(
            recovery_case_id=case.id,
            action_type=StrategyType.HUMAN_REVIEW.value,
            execution_mode=ActionExecutionMode.SIMULATED.value,
            status="PENDING_REVIEW",
            payload=sanitize_payload({
                "simulation_label": "PENDING_HUMAN_REVIEW",
                "reason": decision.reasoning_summary or "Human review mandated by safety gate or low confidence",
            }),
        )
        db.add(action)
        db.flush()
        return action

    def _execute_no_action(
        self,
        db: Session,
        case: RecoveryCase,
        decision: RecoveryDecision,
    ) -> RecoveryAction:
        """Execute NO_ACTION record."""
        action = RecoveryAction(
            recovery_case_id=case.id,
            action_type=StrategyType.NO_ACTION.value,
            execution_mode=ActionExecutionMode.SIMULATED.value,
            status="COMPLETED",
            payload=sanitize_payload({
                "simulation_label": "NO_ACTION_EXECUTED",
                "reason": decision.reasoning_summary or "No action recommended by policy or engine",
            }),
        )
        db.add(action)

        db.flush()
        return action
