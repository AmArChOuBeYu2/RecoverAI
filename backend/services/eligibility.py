"""
Eligibility Checker Service — RecoverAI Milestone 10
Evaluates deterministic eligibility criteria for RecoveryCase processing and advances state machine
(SEGMENTED -> ELIGIBLE or SEGMENTED -> INELIGIBLE).
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models.recovery_case import RecoveryCase
from backend.models.audit_event import AuditEvent
from backend.models.enums import RecoveryCaseStatus, TransactionStatus
from backend.services.context_builder import ContextBuilder
from backend.services.state_machine import StateMachineService, InvalidStateTransitionError
from backend.services.policy_config import PolicyConfig

logger = logging.getLogger(__name__)

class EligibilityCheckDetail(BaseModel):
    check_name: str
    passed: bool
    description: str

class EligibilityResult(BaseModel):
    case_id: str
    is_eligible: bool
    status: str
    reasons: List[str]
    primary_blocking_reason: Optional[str] = None
    checks: List[EligibilityCheckDetail]

class EligibilityChecker:
    """Deterministic eligibility evaluator for recovery cases."""

    @classmethod
    def evaluate_eligibility(
        cls,
        db: Session,
        case: RecoveryCase,
        as_of_time: Optional[datetime] = None,
        config_override: Optional[PolicyConfig] = None,
    ) -> EligibilityResult:
        """
        Evaluate deterministic eligibility criteria:
        1. Transaction age <= MAX_TRANSACTION_AGE_HOURS (default 72h)
        2. Case/Transaction not already recovered or captured
        3. Case not in a terminal state (INELIGIBLE, RECOVERED, UNRECOVERED, ESCALATED, POLICY_BLOCKED)
        4. Transaction amount_paise > 0
        5. Customer contact info present (email or phone)
        6. Attempt count < MAX_RECOVERY_ATTEMPTS (default 2)
        """
        cfg = config_override or PolicyConfig.from_settings()
        ctx = ContextBuilder.assemble_case_context(db, case, as_of_time=as_of_time)
        
        txn_ctx = ctx["transaction"]
        cust_ctx = ctx["customer"]
        case_ctx = ctx["case"]

        checks: List[EligibilityCheckDetail] = []
        reasons: List[str] = []
        primary_blocking_reason: Optional[str] = None

        # Check 1: Non-terminal state check
        is_terminal = case_ctx["is_terminal"] or case.status in StateMachineService.TERMINAL_STATES
        check_terminal = EligibilityCheckDetail(
            check_name="NON_TERMINAL_STATE",
            passed=not is_terminal,
            description=f"Case status '{case.status}' is terminal" if is_terminal else "Case is in non-terminal active pipeline",
        )
        checks.append(check_terminal)
        if is_terminal and not primary_blocking_reason:
            primary_blocking_reason = check_terminal.description

        # Check 2: Already recovered check
        is_recovered = (case.status == RecoveryCaseStatus.RECOVERED.value or txn_ctx["status"] == TransactionStatus.CAPTURED.value)
        check_recovered = EligibilityCheckDetail(
            check_name="NOT_ALREADY_RECOVERED",
            passed=not is_recovered,
            description="Transaction/case is already recovered or captured" if is_recovered else "Case is not yet recovered",
        )
        checks.append(check_recovered)
        if is_recovered and not primary_blocking_reason:
            primary_blocking_reason = check_recovered.description

        # Check 3: Positive monetary amount check
        amount_paise = txn_ctx["amount_paise"]
        has_positive_amount = amount_paise > 0
        check_amount = EligibilityCheckDetail(
            check_name="POSITIVE_AMOUNT",
            passed=has_positive_amount,
            description=f"Transaction amount must be > 0 (got {amount_paise} paise)" if not has_positive_amount else f"Valid monetary amount: ₹{amount_paise/100:.2f}",
        )
        checks.append(check_amount)
        if not has_positive_amount and not primary_blocking_reason:
            primary_blocking_reason = check_amount.description

        # Check 4: Transaction age check
        age_hours = txn_ctx["age_hours"]
        within_age_limit = age_hours <= cfg.max_transaction_age_hours
        check_age = EligibilityCheckDetail(
            check_name="TRANSACTION_AGE",
            passed=within_age_limit,
            description=f"Transaction age {age_hours}h exceeds max allowed {cfg.max_transaction_age_hours}h" if not within_age_limit else f"Transaction age {age_hours}h is within allowed {cfg.max_transaction_age_hours}h limit",
        )
        checks.append(check_age)
        if not within_age_limit and not primary_blocking_reason:
            primary_blocking_reason = check_age.description

        # Check 5: Customer contact information present
        has_contact = bool(cust_ctx["email"] or cust_ctx["phone"])
        check_contact = EligibilityCheckDetail(
            check_name="CUSTOMER_CONTACT",
            passed=has_contact,
            description="No customer contact information (email/phone) available for recovery" if not has_contact else "Customer contact details present",
        )
        checks.append(check_contact)
        if not has_contact and not primary_blocking_reason:
            primary_blocking_reason = check_contact.description

        # Check 6: Retry count limit
        attempt_count = case_ctx["attempt_count"]
        within_retry_limit = attempt_count < cfg.max_retries
        check_retries = EligibilityCheckDetail(
            check_name="RETRY_LIMIT",
            passed=within_retry_limit,
            description=f"Attempt count {attempt_count} reached maximum allowed {cfg.max_retries}" if not within_retry_limit else f"Attempt count {attempt_count} is within limit {cfg.max_retries}",
        )
        checks.append(check_retries)
        if not within_retry_limit and not primary_blocking_reason:
            primary_blocking_reason = check_retries.description

        # Aggregate decision
        is_eligible = all(c.passed for c in checks)
        target_status = RecoveryCaseStatus.ELIGIBLE.value if is_eligible else RecoveryCaseStatus.INELIGIBLE.value

        for c in checks:
            status_str = "PASS" if c.passed else "FAIL"
            reasons.append(f"[{status_str}] {c.check_name}: {c.description}")

        # Transition state machine if case is in DETECTED / ANALYZED / SEGMENTED status
        if case.status in (RecoveryCaseStatus.DETECTED.value, RecoveryCaseStatus.ANALYZED.value, RecoveryCaseStatus.SEGMENTED.value):
            # Ensure case is at SEGMENTED state before transition to ELIGIBLE / INELIGIBLE
            if case.status != RecoveryCaseStatus.SEGMENTED.value:
                case.status = RecoveryCaseStatus.SEGMENTED.value
                db.flush()

            StateMachineService.transition_to(
                db,
                case,
                target_status,
                actor="SYSTEM",
                reason=f"Eligibility evaluation: {'ELIGIBLE' if is_eligible else 'INELIGIBLE'} ({primary_blocking_reason or 'All checks passed'})"
            )

        db.add(AuditEvent(
            recovery_case_id=case.id,
            event_type="CASE_ELIGIBILITY_EVALUATED",
            actor="SYSTEM",
            description=f"Case eligibility evaluated: {target_status}",
            details={
                "is_eligible": is_eligible,
                "status": target_status,
                "primary_blocking_reason": primary_blocking_reason,
                "checks": [c.model_dump() for c in checks],
            },
        ))
        db.flush()

        return EligibilityResult(
            case_id=case.id,
            is_eligible=is_eligible,
            status=target_status,
            reasons=reasons,
            primary_blocking_reason=primary_blocking_reason,
            checks=checks,
        )
