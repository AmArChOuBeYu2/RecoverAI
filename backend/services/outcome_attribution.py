"""
Outcome Attribution Service — RecoverAI Milestone 15
Attributes verified and simulated recovery outcomes, creates StrategyOutcome records,
updates RecoveryStrategy empirical metrics, advances state machine to terminal states,
and logs audit events.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from sqlalchemy.exc import IntegrityError
from backend.models.recovery_case import RecoveryCase
from backend.models.recovery_action import RecoveryAction
from backend.models.recovery_strategy import RecoveryStrategy
from backend.models.strategy_outcome import StrategyOutcome
from backend.models.audit_event import AuditEvent
from backend.models.enums import (
    RecoveryCaseStatus,
    OutcomeSource,
    DataCategory,
    ConfidenceLevel,
)
from backend.services.state_machine import StateMachineService
from backend.services.wilson_score import calculate_wilson_lower_bound
from backend.services.verification import VerificationResult
from backend.services.sanitization import sanitize_payload

logger = logging.getLogger(__name__)

class OutcomeAttributionService:
    """
    Causal outcome attribution engine closing the learning feedback loop.
    
    Invariants:
    1. StrategyOutcome is created ONLY when a verified or simulated outcome is determined.
    2. Explicit outcome_source (VERIFIED vs SIMULATED) is preserved.
    3. SIMULATED outcomes DO NOT modify RecoveryStrategy empirical metrics used by StrategyRanker.
    4. State machine transitions from AWAITING_VERIFICATION -> RECOVERED or UNRECOVERED.
    """

    @classmethod
    def attribute_verification_result(
        cls,
        db: Session,
        case: RecoveryCase,
        action: RecoveryAction,
        verification: VerificationResult,
        actor: str = "SYSTEM",
    ) -> Dict[str, Any]:
        """
        Process verification result and attribute outcome to case, strategy, and segment.
        """
        # Return early if outcome is still PENDING
        if verification.outcome == "PENDING":
            return {
                "case_id": case.id,
                "status": case.status,
                "outcome": "PENDING",
                "attributed": False,
                "reason": "Verification status is still PENDING",
            }

        # Terminal state & existing outcome protection: Idempotent return
        existing_outcome = db.query(StrategyOutcome).filter_by(recovery_case_id=case.id).first()
        if existing_outcome or case.status in (RecoveryCaseStatus.RECOVERED.value, RecoveryCaseStatus.UNRECOVERED.value) or case.is_terminal:
            logger.info(f"Case '{case.id}' already has an attributed outcome or is in terminal state '{case.status}'. Returning existing status.")
            outcome_val = existing_outcome.outcome if existing_outcome else case.status
            amount_val = existing_outcome.amount_recovered_paise if existing_outcome else 0
            source_val = existing_outcome.outcome_source if existing_outcome else OutcomeSource.SIMULATED.value
            out_id = existing_outcome.id if existing_outcome else None
            return {
                "case_id": case.id,
                "status": case.status,
                "outcome": outcome_val,
                "amount_recovered_paise": amount_val,
                "outcome_source": source_val,
                "attributed": False,
                "action_id": action.id,
                "outcome_id": out_id,
                "reason": f"Case already has attributed outcome or is in terminal state '{case.status}'",
            }

        # Update action status
        if verification.outcome == "RECOVERED":
            action.status = "PAID"
        else:
            action.status = "EXPIRED"

        try:
            # 1. Create StrategyOutcome record inside nested savepoint/transaction
            outcome_record = StrategyOutcome(
                recovery_case_id=case.id,
                segment_id=case.segment_id,
                strategy_type=action.action_type,
                outcome=verification.outcome,
                amount_recovered_paise=verification.amount_recovered_paise if verification.outcome == "RECOVERED" else 0,
                outcome_source=verification.outcome_source,
                attributed_at=datetime.now(timezone.utc),
            )
            db.add(outcome_record)
            db.flush()

            # 2. Update RecoveryStrategy empirical statistics ONLY IF outcome source is empirical (VERIFIED / OBSERVED)
            is_empirical = verification.outcome_source in (
                OutcomeSource.VERIFIED.value,
                DataCategory.OBSERVED.value,
                "TEST_MODE_VERIFIED",
            )

            if is_empirical and case.segment_id:
                strat = db.query(RecoveryStrategy).filter_by(
                    segment_id=case.segment_id, strategy_type=action.action_type
                ).first()
                if not strat:
                    strat = RecoveryStrategy(
                        segment_id=case.segment_id,
                        strategy_type=action.action_type,
                        attempt_count=0,
                        success_count=0,
                        total_recovered_paise=0,
                        data_source=verification.outcome_source,
                    )
                    db.add(strat)
                    db.flush()

                strat.attempt_count += 1
                if verification.outcome == "RECOVERED":
                    strat.success_count += 1
                    strat.total_recovered_paise += verification.amount_recovered_paise

                strat.recovery_rate = strat.success_count / strat.attempt_count if strat.attempt_count > 0 else 0.0
                strat.wilson_lower_bound = calculate_wilson_lower_bound(strat.success_count, strat.attempt_count)
                strat.sample_size_sufficient = (strat.attempt_count >= 10)

                if strat.attempt_count >= 100:
                    strat.confidence_level = ConfidenceLevel.HIGH.value
                elif strat.attempt_count >= 31:
                    strat.confidence_level = ConfidenceLevel.MEDIUM.value
                elif strat.attempt_count >= 10:
                    strat.confidence_level = ConfidenceLevel.LOW.value
                else:
                    strat.confidence_level = ConfidenceLevel.INSUFFICIENT.value

                strat.updated_at = datetime.now(timezone.utc)
                db.flush()

            # 3. Transition State Machine to terminal state
            target_status = (
                RecoveryCaseStatus.RECOVERED.value
                if verification.outcome == "RECOVERED"
                else RecoveryCaseStatus.UNRECOVERED.value
            )

            StateMachineService.transition_to(
                db,
                case,
                target_status,
                actor=actor,
                reason=f"Outcome attributed as {verification.outcome} (Source: {verification.outcome_source})",
            )

            # 4. Record Audit Event
            db.add(AuditEvent(
                recovery_case_id=case.id,
                event_type="OUTCOME_ATTRIBUTED",
                actor=actor,
                description=f"Attributed outcome '{verification.outcome}' to strategy '{action.action_type}' (Amount: ₹{verification.amount_recovered_paise / 100:.2f}, Source: {verification.outcome_source})",
                details=sanitize_payload({
                    "outcome_id": outcome_record.id,
                    "strategy_type": action.action_type,
                    "outcome": verification.outcome,
                    "amount_recovered_paise": verification.amount_recovered_paise,
                    "outcome_source": verification.outcome_source,
                    "details": verification.details,
                }),
            ))
            db.flush()

            return {
                "case_id": case.id,
                "status": case.status,
                "outcome": verification.outcome,
                "amount_recovered_paise": verification.amount_recovered_paise,
                "outcome_source": verification.outcome_source,
                "attributed": True,
                "action_id": action.id,
                "outcome_id": outcome_record.id,
            }
        except IntegrityError:
            # Handle DB unique constraint violation (concurrent race condition)
            logger.warning(f"IntegrityError on attribution for case '{case.id}'. Rolling back and returning existing outcome.")
            db.rollback()
            existing = db.query(StrategyOutcome).filter_by(recovery_case_id=case.id).first()
            out_id = existing.id if existing else None
            out_val = existing.outcome if existing else "UNKNOWN"
            amt_val = existing.amount_recovered_paise if existing else 0
            src_val = existing.outcome_source if existing else OutcomeSource.SIMULATED.value
            return {
                "case_id": case.id,
                "status": case.status,
                "outcome": out_val,
                "amount_recovered_paise": amt_val,
                "outcome_source": src_val,
                "attributed": False,
                "action_id": action.id,
                "outcome_id": out_id,
                "reason": "Duplicate attribution prevented by database unique constraint",
            }

