"""
Strategy Engine — RecoverAI Milestone 12
Synthesizes AI Diagnosis, Empirical Evidence (Wilson Lower Bound + Economic Strategy Value),
and Deterministic Baseline Fallback to select optimal recovery strategy.
Persists RecoveryDecision and advances state machine to STRATEGIES_EVALUATED.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.models.recovery_case import RecoveryCase
from backend.models.recovery_decision import RecoveryDecision
from backend.models.strategy_outcome import StrategyOutcome
from backend.models.audit_event import AuditEvent
from backend.models.enums import RecoveryCaseStatus, StrategyType, RecommendationType, OutcomeSource, DataCategory
from backend.services.diagnosis import DiagnosisService
from backend.services.strategy_ranker import StrategyRanker
from backend.services.eligibility import EligibilityChecker
from backend.services.state_machine import StateMachineService, InvalidStateTransitionError
from backend.services.segmentation import SegmentationService
from backend.integrations.llm import LLMRouter

logger = logging.getLogger(__name__)

class StrategyEngine:
    """Orchestrates AI diagnosis and empirical evidence ranking to produce RecoveryDecision."""

    @classmethod
    def evaluate_case_strategies(
        cls,
        db: Session,
        case: RecoveryCase,
        as_of_time: Optional[datetime] = None,
        router: Optional[LLMRouter] = None,
        force_reevaluate: bool = False,
    ) -> RecoveryDecision:
        """
        Evaluate candidate recovery strategies for a RecoveryCase:
        1. Check idempotency: Return existing decision if case already evaluated and force_reevaluate=False.
        2. Ensure case is in ELIGIBLE state (evaluates eligibility if currently in SEGMENTED state).
        3. Run DiagnosisService to obtain AI Diagnosis & recommendation.
        4. Query historical outcome evidence and run StrategyRanker.
        5. Apply deterministic synthesis logic (Empirical > AI when sample >= 10, AI > Baseline when sample < 10).
        6. Persist RecoveryDecision entity (with strategy_evidence & competing_strategies).
        7. Advance state machine from ELIGIBLE -> STRATEGIES_EVALUATED.
        """
        now = as_of_time or datetime.now(timezone.utc)

        # 1. Idempotency Check: Return existing decision if already present
        if not force_reevaluate:
            existing_decision = (
                db.query(RecoveryDecision)
                .filter_by(recovery_case_id=case.id)
                .order_by(RecoveryDecision.created_at.desc())
                .first()
            )
            if existing_decision and case.status not in (RecoveryCaseStatus.DETECTED.value, RecoveryCaseStatus.ANALYZED.value, RecoveryCaseStatus.SEGMENTED.value, RecoveryCaseStatus.ELIGIBLE.value):
                logger.info(f"StrategyEngine returning existing RecoveryDecision for case '{case.id}' (idempotency policy).")
                return existing_decision

        # 2. Eligibility & State Precondition Check
        if case.status in (RecoveryCaseStatus.DETECTED.value, RecoveryCaseStatus.ANALYZED.value, RecoveryCaseStatus.SEGMENTED.value):
            elig_res = EligibilityChecker.evaluate_eligibility(db, case, as_of_time=now)
            if not elig_res.is_eligible:
                raise InvalidStateTransitionError(case.status, RecoveryCaseStatus.STRATEGIES_EVALUATED.value)

        if case.status != RecoveryCaseStatus.ELIGIBLE.value:
            raise InvalidStateTransitionError(case.status, RecoveryCaseStatus.STRATEGIES_EVALUATED.value)

        # 3. AI Diagnosis Service Execution
        ai_diag, context = DiagnosisService.diagnose_case(db, case, router=router, as_of_time=now)
        txn_ctx = context["transaction"]
        cust_ctx = context["customer"]
        seg_ctx = context["segment"]

        # 4. Empirical Strategy Ranking Execution
        # Retrieve historical strategy outcomes strictly from empirical evidence sources (VERIFIED / OBSERVED)
        raw_outcomes = (
            db.query(StrategyOutcome)
            .filter(StrategyOutcome.outcome_source.in_([
                OutcomeSource.VERIFIED.value,
                DataCategory.OBSERVED.value,
                "TEST_MODE_VERIFIED",
            ]))
            .all()
        )
        outcomes_data = []
        for o in raw_outcomes:
            seg_name = ""
            if o.segment:
                seg_name = o.segment.name
            elif o.recovery_case and o.recovery_case.segment:
                seg_name = o.recovery_case.segment.name

            outcomes_data.append({
                "segment_id": o.segment_id,
                "segment_name": seg_name,
                "strategy_type": o.strategy_type,
                "outcome": o.outcome,
                "amount_recovered_paise": o.amount_recovered_paise,
                "outcome_source": o.outcome_source,
                "attributed_at": o.attributed_at or o.created_at,
            })

        ranking_res = StrategyRanker.compare_and_rank_strategies(
            outcomes=outcomes_data,
            failure_category=txn_ctx["failure_category"],
            payment_method=txn_ctx["payment_method"],
            amount_range=seg_ctx["amount_range"],
            customer_type=cust_ctx["customer_type"],
            as_of_time=now,
        )

        ranked_strategies = ranking_res["ranked_strategies"]
        winner_perf = ranking_res["winner_performance"]

        # 5. Deterministic Synthesis Logic
        ai_rec_strat = ai_diag.recommended_strategy
        empirical_winner_strat = winner_perf["strategy_type"]
        sample_sufficient = winner_perf["sample_size_sufficient"]

        if sample_sufficient:
            # Rule 1: Empirical evidence has sufficient sample size (>= 10 attempts).
            # Empirical sample-protected winner takes precedence over AI opinion!
            selected_strategy = empirical_winner_strat
            if ai_rec_strat == empirical_winner_strat:
                synthesis_rationale = (
                    f"EMPIRICAL_AGREEMENT: Selected empirical winner '{selected_strategy}' "
                    f"(Wilson LB {winner_perf['wilson_lower_bound']:.1%}, Economic Score {winner_perf['economic_strategy_value_score']} paise/attempt), "
                    f"which matches AI recommendation."
                )
            else:
                synthesis_rationale = (
                    f"EMPIRICAL_OVERRIDE: Selected sample-protected empirical winner '{selected_strategy}' "
                    f"(Wilson LB {winner_perf['wilson_lower_bound']:.1%}, Economic Score {winner_perf['economic_strategy_value_score']} paise/attempt) "
                    f"over AI recommendation '{ai_rec_strat}' due to sufficient observed sample size ({winner_perf['attempt_count']} attempts)."
                )
        else:
            # Rule 2: Empirical evidence is insufficient (< 10 attempts).
            # Adopt AI recommendation if valid, otherwise fallback to deterministic baseline.
            if ai_rec_strat and ai_rec_strat in {e.value for e in StrategyType} and ai_rec_strat != StrategyType.NO_ACTION.value:
                selected_strategy = ai_rec_strat
                synthesis_rationale = (
                    f"AI_GUIDED_LOW_SAMPLE: Adopted AI recommended strategy '{selected_strategy}' "
                    f"(AI confidence {ai_diag.confidence:.0%}) because empirical segment data is INSUFFICIENT "
                    f"({winner_perf['attempt_count']} attempts < 10 threshold)."
                )
            else:
                selected_strategy = empirical_winner_strat
                synthesis_rationale = (
                    f"DETERMINISTIC_BASELINE: Selected default strategy '{selected_strategy}' "
                    f"because segment evidence is INSUFFICIENT ({winner_perf['attempt_count']} attempts) and AI recommendation was inconclusive."
                )

        # Retrieve provider name from last LLM invocation if available
        last_invocation = (
            db.query(AuditEvent)
            .filter_by(recovery_case_id=case.id, event_type="CASE_DIAGNOSED")
            .order_by(AuditEvent.created_at.desc())
            .first()
        )
        provider_name = "deterministic"
        if last_invocation and last_invocation.details:
            provider_name = last_invocation.details.get("provider", "deterministic")

        # 6. Create & Persist RecoveryDecision
        decision = RecoveryDecision(
            recovery_case_id=case.id,
            ai_diagnosis=ai_diag.diagnosis,
            ai_recommended_strategy=ai_rec_strat,
            ai_confidence=ai_diag.confidence,
            selected_strategy=selected_strategy,
            reasoning_summary=synthesis_rationale,
            strategy_evidence=winner_perf,
            competing_strategies=ranked_strategies,
            llm_provider=provider_name,
        )
        db.add(decision)
        db.flush()

        # 7. Advance State Machine: ELIGIBLE -> STRATEGIES_EVALUATED
        StateMachineService.transition_to(
            db=db,
            case=case,
            target_status=RecoveryCaseStatus.STRATEGIES_EVALUATED.value,
            actor="SYSTEM",
            reason=f"Completed diagnosis & strategy synthesis: selected '{selected_strategy}'",
        )

        db.add(AuditEvent(
            recovery_case_id=case.id,
            event_type="STRATEGY_EVALUATION_COMPLETED",
            actor="SYSTEM",
            description=f"Strategy evaluation completed: selected_strategy='{selected_strategy}'",
            details={
                "decision_id": decision.id,
                "selected_strategy": selected_strategy,
                "ai_recommended_strategy": ai_rec_strat,
                "empirical_winner": empirical_winner_strat,
                "sample_sufficient": sample_sufficient,
                "reasoning_summary": synthesis_rationale,
            },
        ))
        db.flush()

        logger.info(f"StrategyEngine successfully evaluated case '{case.id}': selected_strategy='{selected_strategy}'")
        return decision
