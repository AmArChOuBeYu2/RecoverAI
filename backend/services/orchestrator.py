"""
Orchestrator Service — RecoverAI Milestone 17
Main Agent Loop tying together all domain services:
Detection → Context Building → Segmentation → Eligibility → AI Diagnosis → Strategy Synthesis → Policy Gate → Action Execution → Verification → Outcome Attribution.

Provides batch run tracking, fault tolerance, and idempotency guarantees.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.models.batch_run import BatchRun
from backend.models.transaction import Transaction
from backend.models.recovery_case import RecoveryCase
from backend.models.audit_event import AuditEvent
from backend.models.enums import (
    FailureCategory,
    TransactionStatus,
    RecoveryCaseStatus,
    PolicyDecisionType,
    DataCategory,
    OutcomeSource,
)
from backend.services.context_builder import ContextBuilder
from backend.services.segmentation import SegmentationService
from backend.services.eligibility import EligibilityChecker
from backend.services.diagnosis import DiagnosisService
from backend.services.strategy_engine import StrategyEngine
from backend.services.policy_engine import PolicyEngine
from backend.services.executor import ActionExecutor
from backend.services.verification import VerificationService
from backend.services.outcome_attribution import OutcomeAttributionService
from backend.services.state_machine import StateMachineService

logger = logging.getLogger(__name__)

class OrchestratorService:
    """
    Main Orchestration Agent Loop for RecoverAI.
    Ties together all pipeline steps into a fault-tolerant batch run loop:
    Detection → Context → Segmentation → Eligibility → Diagnosis → Strategy → Policy → Authorization → Execution → Verification → Attribution.
    """

    @classmethod
    def run_batch(
        cls,
        db: Session,
        batch_run_name: Optional[str] = None,
        limit: int = 500,
        transaction_ids: Optional[List[str]] = None,
        force_reprocess: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute batch recovery pipeline across failed transactions.
        
        Guarantees:
        1. Fault tolerance: per-case exception handling prevents batch crashes.
        2. Idempotency: skips terminal or previously completed cases unless force_reprocess=True.
        3. Batch tracking: creates and updates a BatchRun database record.
        """
        start_time = datetime.now(timezone.utc)
        run_name = batch_run_name or f"batch_{start_time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        # 1. Create BatchRun database record
        batch_run = BatchRun(
            run_name=run_name,
            status="RUNNING",
            started_at=start_time,
            total_processed=0,
            success_count=0,
            total_recovered_paise=0,
        )
        db.add(batch_run)
        db.flush()

        # 2. Query target transactions
        query = db.query(Transaction).filter(Transaction.status == TransactionStatus.FAILED.value)
        if transaction_ids:
            query = query.filter(Transaction.id.in_(transaction_ids))
        
        txns = query.order_by(Transaction.created_at.desc()).limit(limit).all()

        processed_count = 0
        success_count = 0
        error_count = 0
        total_recovered_paise = 0
        case_summaries: List[Dict[str, Any]] = []

        logger.info(f"Starting batch run '{run_name}' with {len(txns)} target transactions.")

        # 3. Process each transaction through pipeline
        for t in txns:
            nested = db.begin_nested()
            try:
                result = cls._process_single_transaction(
                    db=db,
                    transaction=t,
                    batch_run_id=batch_run.id,
                    force_reprocess=force_reprocess,
                )
                nested.commit()
                processed_count += 1
                if result.get("recovered"):
                    success_count += 1
                    total_recovered_paise += result.get("amount_recovered_paise", 0)
                
                case_summaries.append(result)

            except Exception as e:
                nested.rollback()
                logger.error(f"Error processing transaction {t.id} in batch {batch_run.id}: {str(e)}", exc_info=True)
                error_count += 1
                processed_count += 1
                
                # Log audit event for case failure in isolated session context
                try:
                    case_id = t.recovery_case.id if t.recovery_case else None
                    if case_id:
                        db.add(AuditEvent(
                            recovery_case_id=case_id,
                            event_type="BATCH_PROCESSING_ERROR",
                            actor="system",
                            description=f"Batch error for transaction '{t.id}': {str(e)}",
                            details={"error": str(e), "transaction_id": t.id, "batch_run_id": batch_run.id},
                        ))
                        db.flush()
                except Exception as audit_exc:
                    logger.warning(f"Failed to record BATCH_PROCESSING_ERROR audit event: {audit_exc}")
                    db.rollback()

                case_summaries.append({
                    "transaction_id": t.id,
                    "case_id": t.recovery_case.id if t.recovery_case else None,
                    "status": "ERROR",
                    "error": str(e),
                })

        # 4. Finalize BatchRun record
        completed_time = datetime.now(timezone.utc)
        batch_run.status = "COMPLETED" if error_count == 0 else "COMPLETED_WITH_ERRORS"
        batch_run.completed_at = completed_time
        batch_run.total_processed = processed_count
        batch_run.success_count = success_count
        batch_run.total_recovered_paise = total_recovered_paise

        db.flush()

        logger.info(f"Batch run '{run_name}' finished: processed={processed_count}, success={success_count}, errors={error_count}.")

        return {
            "batch_run_id": batch_run.id,
            "run_name": batch_run.run_name,
            "status": batch_run.status,
            "started_at": start_time.isoformat(),
            "completed_at": completed_time.isoformat(),
            "total_target_transactions": len(txns),
            "total_processed": processed_count,
            "success_count": success_count,
            "error_count": error_count,
            "total_recovered_paise": total_recovered_paise,
            "total_recovered_rupees": round(total_recovered_paise / 100.0, 2),
            "case_summaries": case_summaries,
        }

    @classmethod
    def process_single_case(
        cls,
        db: Session,
        case_id: str,
        force_reprocess: bool = False,
    ) -> Dict[str, Any]:
        """
        Process a single RecoveryCase end-to-end through the orchestrator pipeline.
        """
        case = db.query(RecoveryCase).filter_by(id=case_id).first()
        if not case:
            raise ValueError(f"RecoveryCase with ID '{case_id}' not found.")

        return cls._process_single_transaction(
            db=db,
            transaction=case.transaction,
            batch_run_id=None,
            force_reprocess=force_reprocess,
        )

    @classmethod
    def _process_single_transaction(
        cls,
        db: Session,
        transaction: Transaction,
        batch_run_id: Optional[str] = None,
        force_reprocess: bool = False,
        as_of_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Execute complete pipeline for one transaction:
        Detect → Context → Segment → Eligibility → AI Diagnosis → Strategy → Policy → Execute → Verify → Attribute
        """
        # Step 1: Ensure RecoveryCase exists
        case = transaction.recovery_case
        if not case:
            case = RecoveryCase(
                transaction_id=transaction.id,
                customer_id=transaction.customer_id,
                status=RecoveryCaseStatus.DETECTED.value,
            )
            db.add(case)
            db.flush()

        # Step 2: Immutable Terminal State Protection (RECOVERED and UNRECOVERED cannot be rerun)
        if case.status in (RecoveryCaseStatus.RECOVERED.value, RecoveryCaseStatus.UNRECOVERED.value):
            logger.info(f"Case {case.id} is in terminal state '{case.status}'. Skipping re-processing.")
            return {
                "case_id": case.id,
                "transaction_id": transaction.id,
                "status": case.status,
                "skipped": True,
                "reason": f"Case is in terminal state '{case.status}'",
                "recovered": case.status == RecoveryCaseStatus.RECOVERED.value,
                "amount_recovered_paise": transaction.amount_paise if case.status == RecoveryCaseStatus.RECOVERED.value else 0,
            }

        if case.is_terminal and not force_reprocess:
            logger.info(f"Skipping terminal case {case.id} (status={case.status}).")
            return {
                "case_id": case.id,
                "transaction_id": transaction.id,
                "status": case.status,
                "skipped": True,
                "reason": f"Case is in terminal state '{case.status}'",
                "recovered": False,
                "amount_recovered_paise": 0,
            }

        # Step 3: Failure Category Classification Verification
        if transaction.failure_category in (FailureCategory.BUSINESS_ERROR.value, FailureCategory.REPEATED_FAILURE.value) and not force_reprocess:
            case.status = RecoveryCaseStatus.INELIGIBLE.value
            case.is_terminal = True
            db.flush()
            return {
                "case_id": case.id,
                "transaction_id": transaction.id,
                "status": case.status,
                "skipped": True,
                "reason": f"Failure category '{transaction.failure_category}' deemed unrecoverable",
                "recovered": False,
                "amount_recovered_paise": 0,
            }

        # Step 4: Build Structured Context with Business-Hours Evaluation Timestamp
        from datetime import timedelta
        now_eval = as_of_time or datetime.now(timezone.utc)
        if as_of_time is None:
            ist_h = (now_eval + timedelta(hours=5, minutes=30)).hour
            if not (9 <= ist_h < 21):
                now_eval = now_eval.replace(hour=8, minute=30, second=0, microsecond=0)

        context = ContextBuilder.assemble_case_context(db=db, case=case, as_of_time=now_eval)
        context["current_time_utc"] = now_eval

        # Step 5: Segmentation Engine
        segment = SegmentationService.assign_segment_to_case(db=db, case=case)

        # Step 6: Eligibility Check
        eligibility = EligibilityChecker.evaluate_eligibility(db=db, case=case)
        if not eligibility.is_eligible:
            case.status = RecoveryCaseStatus.INELIGIBLE.value
            case.is_terminal = True
            db.flush()
            return {
                "case_id": case.id,
                "transaction_id": transaction.id,
                "status": case.status,
                "eligible": False,
                "reason": eligibility.reasons[0] if eligibility.reasons else "Ineligible for recovery",
                "recovered": False,
                "amount_recovered_paise": 0,
            }

        # Step 7: AI Diagnosis & Scoring
        DiagnosisService.diagnose_case(db=db, case=case)

        # Step 8: Strategy Synthesis & Recommendation
        decision = StrategyEngine.evaluate_case_strategies(db=db, case=case, force_reevaluate=force_reprocess)
        proposed_strategy = decision.selected_strategy or "PAYMENT_LINK"

        # Step 9: Policy Engine Gate
        policy_res = PolicyEngine.evaluate(
            case=case,
            proposed_strategy=proposed_strategy,
            ai_confidence=case.recoverability_score,
            context=context,
            db=db,
            persist_decision=True,
        )

        if not policy_res.can_execute_action:
            if policy_res.decision == PolicyDecisionType.DENY.value:
                StateMachineService.transition_to(db, case, RecoveryCaseStatus.POLICY_BLOCKED.value, actor="SYSTEM", reason=policy_res.reason)
            elif policy_res.decision == PolicyDecisionType.ESCALATE.value:
                StateMachineService.transition_to(db, case, RecoveryCaseStatus.ESCALATED.value, actor="SYSTEM", reason=policy_res.reason)
            db.flush()
            return {
                "case_id": case.id,
                "transaction_id": transaction.id,
                "status": case.status,
                "policy_decision": policy_res.decision,
                "policy_reason": policy_res.reason,
                "proposed_strategy": proposed_strategy,
                "executed": False,
                "recovered": False,
                "amount_recovered_paise": 0,
            }

        # Advance state machine to POLICY_APPROVED
        StateMachineService.transition_to(db, case, RecoveryCaseStatus.POLICY_APPROVED.value, actor="SYSTEM", reason="Policy engine approved strategy execution")

        # Step 10: Authorized Action Execution
        executor = ActionExecutor()
        action = executor.execute(
            db=db,
            case=case,
            decision=decision,
            context=context,
            policy_decision=policy_res,
            actor="SYSTEM",
        )

        # Step 11: Action Outcome Verification
        verifier = VerificationService()
        verification = verifier.verify_action_outcome(
            db=db,
            case=case,
            action=action,
        )

        # Step 12: Outcome Attribution & Strategy Feedback Update
        attribution = OutcomeAttributionService.attribute_verification_result(
            db=db,
            case=case,
            action=action,
            verification=verification,
        )

        db.flush()

        is_authoritative_recovered = (
            attribution.get("outcome") == "RECOVERED"
            and attribution.get("outcome_source") in (OutcomeSource.VERIFIED.value, "TEST_MODE_VERIFIED", DataCategory.OBSERVED.value)
        )
        amount_authoritative_recovered = attribution.get("amount_recovered_paise", 0) if is_authoritative_recovered else 0

        return {
            "case_id": case.id,
            "transaction_id": transaction.id,
            "segment_name": segment.name if segment else None,
            "status": case.status,
            "proposed_strategy": proposed_strategy,
            "action_id": action.id,
            "action_mode": action.execution_mode,
            "verification_status": verification.outcome,
            "verification_source": verification.outcome_source,
            "executed": True,
            "recovered": is_authoritative_recovered,
            "simulated_recovered": (attribution.get("outcome") == "RECOVERED" and attribution.get("outcome_source") == OutcomeSource.SIMULATED.value),
            "amount_recovered_paise": amount_authoritative_recovered,
            "amount_recovered_rupees": round(amount_authoritative_recovered / 100.0, 2),
        }
