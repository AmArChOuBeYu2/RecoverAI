"""
Recovery REST API Routes — RecoverAI Milestone 10
Provides endpoints for payment failure detection, recovery case retrieval,
rich context assembly, and deterministic eligibility evaluation.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.models.recovery_case import RecoveryCase
from backend.models.enums import RecoveryCaseStatus
from backend.services.detection import DetectionEngine
from backend.services.context_builder import ContextBuilder
from backend.services.eligibility import EligibilityChecker, EligibilityResult

router = APIRouter(prefix="/api/recovery", tags=["recovery"])

@router.post("/detect", response_model=Dict[str, Any])
def run_detection(
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Run DetectionEngine to scan database for unhandled payment failures and initialize recovery cases."""
    cases = DetectionEngine.detect_unhandled_failures(db, limit=limit)
    db.commit()
    return {
        "detected_count": len(cases),
        "cases": [{"id": c.id, "status": c.status, "segment_name": c.segment.name if c.segment else None} for c in cases],
    }

@router.get("/cases", response_model=Dict[str, Any])
def list_recovery_cases(
    status: Optional[str] = Query(None, description="Filter by RecoveryCaseStatus"),
    segment_id: Optional[str] = Query(None, description="Filter by segment ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List recovery cases with optional status and segment filtering."""
    query = db.query(RecoveryCase)
    if status:
        query = query.filter(RecoveryCase.status == status.upper())
    if segment_id:
        query = query.filter(RecoveryCase.segment_id == segment_id)

    total_count = query.count()
    cases = query.order_by(RecoveryCase.detected_at.desc()).offset(offset).limit(limit).all()

    items = []
    for c in cases:
        items.append({
            "id": c.id,
            "transaction_id": c.transaction_id,
            "customer_id": c.customer_id,
            "segment_id": c.segment_id,
            "segment_name": c.segment.name if c.segment else None,
            "status": c.status,
            "attempt_count": c.attempt_count,
            "is_terminal": c.is_terminal,
            "detected_at": c.detected_at.isoformat() if c.detected_at else None,
        })

    return {
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "cases": items,
    }

@router.get("/cases/{case_id}", response_model=Dict[str, Any])
def get_recovery_case_detail(
    case_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed information and assembled context for a specific recovery case ID."""
    case = db.query(RecoveryCase).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")

    context = ContextBuilder.assemble_case_context(db, case)
    return context

@router.get("/context/{case_id}", response_model=Dict[str, Any])
def get_case_context(
    case_id: str,
    db: Session = Depends(get_db),
):
    """Assemble structured context (transaction, customer history, 4D segment, prior actions) for a case."""
    case = db.query(RecoveryCase).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")

    return ContextBuilder.assemble_case_context(db, case)

@router.post("/eligibility/{case_id}", response_model=EligibilityResult)
def evaluate_case_eligibility(
    case_id: str,
    db: Session = Depends(get_db),
):
    """Evaluate deterministic eligibility criteria for a recovery case and advance state machine."""
    case = db.query(RecoveryCase).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")

    result = EligibilityChecker.evaluate_eligibility(db, case)
    db.commit()
    return result

@router.post("/evaluate/{case_id}", response_model=Dict[str, Any])
def evaluate_case_strategy(
    case_id: str,
    force_reevaluate: bool = Query(False, description="Force re-evaluation even if decision exists"),
    db: Session = Depends(get_db),
):
    """
    Run AI Diagnosis & Strategy Engine for an ELIGIBLE recovery case.
    Synthesizes AI recommendation + empirical evidence, persists RecoveryDecision,
    and advances state machine from ELIGIBLE -> STRATEGIES_EVALUATED.
    """
    from backend.services.strategy_engine import StrategyEngine
    from backend.models.recovery_decision import RecoveryDecision
    from backend.services.state_machine import InvalidStateTransitionError

    case = db.query(RecoveryCase).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")

    try:
        decision = StrategyEngine.evaluate_case_strategies(
            db=db,
            case=case,
            force_reevaluate=force_reevaluate,
        )
        db.commit()
        return {
            "case_id": case.id,
            "status": case.status,
            "decision_id": decision.id,
            "selected_strategy": decision.selected_strategy,
            "ai_recommended_strategy": decision.ai_recommended_strategy,
            "ai_confidence": decision.ai_confidence,
            "ai_diagnosis": decision.ai_diagnosis,
            "reasoning_summary": decision.reasoning_summary,
            "strategy_evidence": decision.strategy_evidence,
            "competing_strategies": decision.competing_strategies,
            "llm_provider": decision.llm_provider,
            "created_at": decision.created_at.isoformat() if decision.created_at else None,
        }
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=f"Cannot evaluate strategy for case '{case_id}' in status '{case.status}'. Case must be in ELIGIBLE state.")

@router.get("/decisions/{case_id}", response_model=Dict[str, Any])
def get_case_decision(
    case_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve decision evidence details for a evaluated recovery case."""
    from backend.models.recovery_decision import RecoveryDecision

    case = db.query(RecoveryCase).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")

    decision = (
        db.query(RecoveryDecision)
        .filter_by(recovery_case_id=case_id)
        .order_by(RecoveryDecision.created_at.desc())
        .first()
    )
    if not decision:
        raise HTTPException(status_code=404, detail=f"No decision found for case '{case_id}'")

    return {
        "id": decision.id,
        "case_id": case.id,
        "case_status": case.status,
        "selected_strategy": decision.selected_strategy,
        "ai_recommended_strategy": decision.ai_recommended_strategy,
        "ai_confidence": decision.ai_confidence,
        "ai_diagnosis": decision.ai_diagnosis,
        "reasoning_summary": decision.reasoning_summary,
        "strategy_evidence": decision.strategy_evidence,
        "competing_strategies": decision.competing_strategies,
        "llm_provider": decision.llm_provider,
        "created_at": decision.created_at.isoformat() if decision.created_at else None,
    }

@router.post("/{case_id}/execute", response_model=Dict[str, Any])
def execute_recovery_action(
    case_id: str,
    db: Session = Depends(get_db),
):
    """
    Execute an authorized recovery action for a recovery case.
    Enforces Policy Engine approval, Trust Gate safety, execution limits,
    state machine transitions, and audit trail records.
    """
    from backend.models.recovery_decision import RecoveryDecision
    from backend.services.policy_engine import PolicyEngine
    from backend.services.state_machine import StateMachineService, InvalidStateTransitionError
    from backend.services.executor import ActionExecutor, ActionExecutionError
    from backend.services.authorization import ActionAuthorizationError
    from backend.models.enums import PolicyDecisionType

    case = db.query(RecoveryCase).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")

    decision = (
        db.query(RecoveryDecision)
        .filter_by(recovery_case_id=case_id)
        .order_by(RecoveryDecision.created_at.desc())
        .first()
    )
    if not decision:
        raise HTTPException(
            status_code=400,
            detail=f"Recovery case '{case_id}' has not been evaluated by strategy engine yet.",
        )

    # Evaluate policy if case is in STRATEGIES_EVALUATED state
    if case.status == RecoveryCaseStatus.STRATEGIES_EVALUATED.value:
        policy_result = PolicyEngine.evaluate(
            case=case,
            proposed_strategy=decision.selected_strategy,
            ai_confidence=decision.ai_confidence,
            db=db,
            persist_decision=True,
        )
        if policy_result.decision == PolicyDecisionType.APPROVE.value:
            StateMachineService.transition_to(
                db, case, RecoveryCaseStatus.POLICY_APPROVED.value, actor="POLICY_ENGINE"
            )
        elif policy_result.decision == PolicyDecisionType.DENY.value:
            StateMachineService.transition_to(
                db, case, RecoveryCaseStatus.POLICY_BLOCKED.value, actor="POLICY_ENGINE", reason=policy_result.reason
            )
            db.commit()
            raise HTTPException(
                status_code=400,
                detail=f"Action execution blocked by policy: {policy_result.reason}",
            )
        elif policy_result.decision == PolicyDecisionType.ESCALATE.value:
            StateMachineService.transition_to(
                db, case, RecoveryCaseStatus.ESCALATED.value, actor="POLICY_ENGINE", reason=policy_result.reason
            )
            db.commit()
            raise HTTPException(
                status_code=400,
                detail=f"Action execution escalated by policy: {policy_result.reason}",
            )

    if case.status != RecoveryCaseStatus.POLICY_APPROVED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot execute action for case '{case_id}' in status '{case.status}'. Case must be in POLICY_APPROVED state.",
        )

    try:
        executor = ActionExecutor()
        action = executor.execute(db, case, decision)
        db.commit()
        return {
            "case_id": case.id,
            "case_status": case.status,
            "action_id": action.id,
            "action_type": action.action_type,
            "execution_mode": action.execution_mode,
            "status": action.status,
            "razorpay_payment_link_id": action.razorpay_payment_link_id,
            "payment_link_url": action.payment_link_url,
            "payload": action.payload,
            "executed_at": action.executed_at.isoformat() if action.executed_at else None,
        }
    except (ActionAuthorizationError, ActionExecutionError, ValueError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{case_id}/verify", response_model=Dict[str, Any])
def verify_case_outcome(
    case_id: str,
    db: Session = Depends(get_db),
):
    """
    Verify action outcome for a recovery case, attribute strategy performance feedback,
    and transition state machine to terminal states (RECOVERED or UNRECOVERED).
    """
    from backend.models.recovery_action import RecoveryAction
    from backend.services.verification import VerificationService
    from backend.services.outcome_attribution import OutcomeAttributionService

    case = db.query(RecoveryCase).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Recovery case '{case_id}' not found")

    action = (
        db.query(RecoveryAction)
        .filter_by(recovery_case_id=case_id)
        .filter(RecoveryAction.status != "FAILED")
        .order_by(RecoveryAction.executed_at.desc())
        .first()
    )
    if not action:
        raise HTTPException(
            status_code=400,
            detail=f"Recovery case '{case_id}' has no active attempted recovery action to verify.",
        )

    verification_service = VerificationService()
    v_res = verification_service.verify_action_outcome(db, case, action)
    attribution_res = OutcomeAttributionService.attribute_verification_result(db, case, action, v_res)
    db.commit()

    return attribution_res



