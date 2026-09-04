"""
Diagnosis Service — RecoverAI Milestone 12
Assembles case context, invokes LLMRouter, records audit trail, and manages AI root-cause diagnosis.
"""

import logging
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from backend.models.recovery_case import RecoveryCase
from backend.models.audit_event import AuditEvent
from backend.services.context_builder import ContextBuilder
from backend.integrations.llm import LLMRouter, RecoveryDiagnosis

logger = logging.getLogger(__name__)

class DiagnosisService:
    """Service for AI payment failure diagnosis and recoverability propensity scoring."""

    @classmethod
    def diagnose_case(
        cls,
        db: Session,
        case: RecoveryCase,
        router: Optional[LLMRouter] = None,
        as_of_time: Optional[Any] = None,
    ) -> Tuple[RecoveryDiagnosis, Dict[str, Any]]:
        """
        Assemble structured case context, invoke LLMRouter (cascading OpenAI -> Gemini -> Deterministic),
        update case recoverability score, log audit event, and return validated RecoveryDiagnosis.
        """
        active_router = router or LLMRouter()

        # 1. Assemble structured context (zero ground-truth leakage)
        context = ContextBuilder.assemble_case_context(db, case, as_of_time=as_of_time)

        # 2. Invoke LLMRouter (handles cascading provider fallbacks & DB invocation audit logging)
        diagnosis = active_router.diagnose_case(
            context=context,
            db=db,
            case_id=case.id,
        )

        # 3. Update case recoverability score with AI propensity score while preserving case state
        case.recoverability_score = diagnosis.recoverability_score
        db.flush()

        # 4. Record CASE_DIAGNOSED audit event
        audit = AuditEvent(
            recovery_case_id=case.id,
            event_type="CASE_DIAGNOSED",
            actor="SYSTEM",
            description=f"AI failure diagnosis completed: category='{diagnosis.failure_category}', recommended='{diagnosis.recommended_strategy}', score={diagnosis.recoverability_score}",
            details={
                "failure_category": diagnosis.failure_category,
                "ai_recommended_strategy": diagnosis.recommended_strategy,
                "recoverability_score": diagnosis.recoverability_score,
                "confidence": diagnosis.confidence,
                "reasoning_summary": diagnosis.reasoning_summary,
            },
        )
        db.add(audit)
        db.flush()

        logger.info(f"DiagnosisService successfully diagnosed case '{case.id}': {diagnosis.failure_category} -> {diagnosis.recommended_strategy}")
        return diagnosis, context
