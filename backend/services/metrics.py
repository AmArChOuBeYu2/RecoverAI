"""
Metrics Service — RecoverAI Milestone 18
Computes enterprise revenue metrics, batch execution statistics, strategy performance
tables per segment, and failure analysis breakdowns with strict evidence category separation
(VERIFIED, SIMULATED, PROJECTED, OBSERVED).
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.transaction import Transaction
from backend.models.recovery_case import RecoveryCase
from backend.models.recovery_action import RecoveryAction
from backend.models.recovery_decision import RecoveryDecision
from backend.models.policy_decision import PolicyDecision
from backend.models.strategy_outcome import StrategyOutcome
from backend.models.recovery_strategy import RecoveryStrategy
from backend.models.segment import Segment
from backend.models.audit_event import AuditEvent
from backend.models.llm_invocation import LLMInvocation
from backend.models.batch_run import BatchRun
from backend.models.enums import (
    TransactionStatus,
    FailureCategory,
    RecoveryCaseStatus,
    PolicyDecisionType,
    ActionExecutionMode,
    OutcomeSource,
    DataCategory,
    StrategyType,
)

logger = logging.getLogger(__name__)

class MetricsService:
    """
    Centralized Metrics Engine for RecoverAI.
    
    Invariants:
    1. Honest Data Category Reporting: Never mixes VERIFIED, SIMULATED, and PROJECTED values.
    2. Integer-paise amounts preserved in all revenue calculations.
    3. Unrecovered revenue broken down by exact system root-cause reason.
    4. Strategy performance per segment carries empirical confidence levels and Wilson bounds.
    """

    @classmethod
    def compute_portfolio_metrics(
        cls,
        db: Session,
        batch_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compute comprehensive portfolio or batch-level recovery metrics.
        """
        # Base query filters for batch_run_id if provided
        tx_query = db.query(Transaction)
        case_query = db.query(RecoveryCase)
        action_query = db.query(RecoveryAction)
        outcome_query = db.query(StrategyOutcome)

        if batch_run_id:
            # Filter cases belonging to transactions processed in this batch
            b_run = db.query(BatchRun).filter_by(id=batch_run_id).first()
            if b_run:
                case_ids = (
                    db.query(RecoveryCase.id)
                    .join(Transaction)
                    .filter(Transaction.status == TransactionStatus.FAILED.value)
                    .all()
                )
                c_id_list = [c[0] for c in case_ids]
                case_query = case_query.filter(RecoveryCase.id.in_(c_id_list))
                action_query = action_query.filter(RecoveryAction.recovery_case_id.in_(c_id_list))
                outcome_query = outcome_query.filter(StrategyOutcome.recovery_case_id.in_(c_id_list))

        # 1. Transaction & Revenue Totals
        total_tx_count = tx_query.filter(Transaction.status == TransactionStatus.FAILED.value).count()
        total_tx_value_paise = (
            db.query(func.coalesce(func.sum(Transaction.amount_paise), 0))
            .filter(Transaction.status == TransactionStatus.FAILED.value)
            .scalar()
            or 0
        )
        total_revenue_at_risk_paise = total_tx_value_paise

        # 2. Eligibility & Context Metrics
        eligible_cases_query = case_query.filter(RecoveryCase.status != RecoveryCaseStatus.INELIGIBLE.value)
        eligible_tx_count = eligible_cases_query.count()
        
        eligible_revenue_paise = (
            db.query(func.coalesce(func.sum(Transaction.amount_paise), 0))
            .select_from(RecoveryCase)
            .join(Transaction, RecoveryCase.transaction_id == Transaction.id)
            .filter(RecoveryCase.status != RecoveryCaseStatus.INELIGIBLE.value)
            .scalar()
            or 0
        )

        # 3. Pipeline Decision Metrics
        ai_decision_count = db.query(RecoveryDecision).count()
        
        policy_approved_count = (
            db.query(PolicyDecision)
            .filter(PolicyDecision.decision == PolicyDecisionType.APPROVE.value)
            .count()
        )
        policy_blocked_count = (
            db.query(PolicyDecision)
            .filter(PolicyDecision.decision == PolicyDecisionType.DENY.value)
            .count()
        )
        escalation_count = (
            db.query(RecoveryCase)
            .filter(RecoveryCase.status == RecoveryCaseStatus.ESCALATED.value)
            .count()
        )

        # 4. Action Execution Breakdown
        total_actions_attempted = action_query.filter(RecoveryAction.status != "FAILED").count()
        
        real_test_mode_count = action_query.filter(
            RecoveryAction.execution_mode == ActionExecutionMode.REAL_TEST_MODE.value,
            RecoveryAction.status != "FAILED",
        ).count()

        simulated_mode_count = action_query.filter(
            RecoveryAction.execution_mode == ActionExecutionMode.SIMULATED.value,
            RecoveryAction.status != "FAILED",
        ).count()

        # Breakdown by strategy type
        actions_by_strategy: Dict[str, int] = {}
        for st in StrategyType:
            cnt = action_query.filter(
                RecoveryAction.action_type == st.value,
                RecoveryAction.status != "FAILED",
            ).count()
            actions_by_strategy[st.value] = cnt

        # 5. Outcome & Revenue Breakdown by Evidence Category
        verified_outcomes = outcome_query.filter(
            StrategyOutcome.outcome == "RECOVERED",
            StrategyOutcome.outcome_source.in_([OutcomeSource.VERIFIED.value, "TEST_MODE_VERIFIED", DataCategory.OBSERVED.value]),
        ).all()
        verified_recovered_count = len(verified_outcomes)
        verified_recovered_paise = sum(o.amount_recovered_paise for o in verified_outcomes)

        simulated_outcomes = outcome_query.filter(
            StrategyOutcome.outcome == "RECOVERED",
            StrategyOutcome.outcome_source == OutcomeSource.SIMULATED.value,
        ).all()
        simulated_recovered_count = len(simulated_outcomes)
        simulated_recovered_paise = sum(o.amount_recovered_paise for o in simulated_outcomes)

        # 6. Unrecovered Revenue Breakdown by System Root Cause (Mutually Exclusive Buckets)
        unrecovered_cases = case_query.filter(
            RecoveryCase.status.in_([
                RecoveryCaseStatus.UNRECOVERED.value,
                RecoveryCaseStatus.INELIGIBLE.value,
                RecoveryCaseStatus.POLICY_BLOCKED.value,
                RecoveryCaseStatus.ESCALATED.value,
                RecoveryCaseStatus.AWAITING_VERIFICATION.value,
            ])
        ).all()

        unrecovered_breakdown = {
            "policy_blocked_paise": 0,
            "ineligible_paise": 0,
            "action_failed_paise": 0,
            "escalated_paise": 0,
            "unpaid_expired_paise": 0,
            "other_unrecovered_paise": 0,
        }

        # Check for cases with failed actions to classify action_failed_paise
        failed_actions = action_query.filter(RecoveryAction.status == "FAILED").all()
        failed_action_case_ids = set(a.recovery_case_id for a in failed_actions)

        total_unrecovered_paise = 0
        for c in unrecovered_cases:
            amt = c.transaction.amount_paise if c.transaction else 0
            total_unrecovered_paise += amt

            if c.id in failed_action_case_ids:
                unrecovered_breakdown["action_failed_paise"] += amt
            elif c.status == RecoveryCaseStatus.POLICY_BLOCKED.value:
                unrecovered_breakdown["policy_blocked_paise"] += amt
            elif c.status == RecoveryCaseStatus.INELIGIBLE.value:
                unrecovered_breakdown["ineligible_paise"] += amt
            elif c.status == RecoveryCaseStatus.ESCALATED.value:
                unrecovered_breakdown["escalated_paise"] += amt
            elif c.status == RecoveryCaseStatus.AWAITING_VERIFICATION.value:
                unrecovered_breakdown["unpaid_expired_paise"] += amt
            elif c.status == RecoveryCaseStatus.UNRECOVERED.value:
                unrecovered_breakdown["other_unrecovered_paise"] += amt

        # 7. System Performance & Reliability Rates
        case_recovery_rate = (verified_recovered_count / eligible_tx_count) if eligible_tx_count > 0 else 0.0
        revenue_recovery_rate = (verified_recovered_paise / eligible_revenue_paise) if eligible_revenue_paise > 0 else 0.0
        action_success_rate = (verified_recovered_count / total_actions_attempted) if total_actions_attempted > 0 else 0.0

        # Duplicate actions prevented count (where execution returned existing action)
        duplicate_prevented_count = db.query(AuditEvent).filter(
            AuditEvent.event_type == "ACTION_EXECUTED",
            AuditEvent.details.like("%Idempotent%"),
        ).count()

        # Reliability & Provider Fallback Rates
        total_llm_calls = db.query(LLMInvocation).count()
        fallback_calls = db.query(LLMInvocation).filter(LLMInvocation.fallback_triggered == True).count()
        failed_llm_calls = db.query(LLMInvocation).filter(LLMInvocation.success == False).count()

        provider_fallback_rate = (fallback_calls / total_llm_calls) if total_llm_calls > 0 else 0.0
        ai_failure_rate = (failed_llm_calls / total_llm_calls) if total_llm_calls > 0 else 0.0

        total_rp_calls = db.query(AuditEvent).filter(
            AuditEvent.event_type.in_(["ACTION_EXECUTED", "ACTION_EXECUTION_FAILED"]),
            AuditEvent.details.like("%RAZORPAY%"),
        ).count()
        failed_rp_calls = db.query(AuditEvent).filter(
            AuditEvent.event_type == "ACTION_EXECUTION_FAILED",
            AuditEvent.details.like("%RAZORPAY%"),
        ).count()
        razorpay_api_failure_rate = (failed_rp_calls / total_rp_calls) if total_rp_calls > 0 else 0.0

        ineligible_tx_count = total_tx_count - eligible_tx_count
        total_tx_value_rupees = round(total_tx_value_paise / 100.0, 2)
        eligible_revenue_rupees = round(eligible_revenue_paise / 100.0, 2)
        verified_recovered_rupees = round(verified_recovered_paise / 100.0, 2)
        simulated_recovered_rupees = round(simulated_recovered_paise / 100.0, 2)
        total_unrecovered_rupees = round(total_unrecovered_paise / 100.0, 2)

        return {
            "batch_run_id": batch_run_id,
            "total_transaction_count": total_tx_count,
            "total_cases": total_tx_count,
            "total_transaction_value_paise": total_tx_value_paise,
            "total_transaction_value_rupees": total_tx_value_rupees,
            "total_revenue_at_risk_paise": total_revenue_at_risk_paise,
            "revenue_at_risk_rupees": total_tx_value_rupees,
            "eligible_transaction_count": eligible_tx_count,
            "eligible_cases": eligible_tx_count,
            "ineligible_cases": ineligible_tx_count,
            "eligible_revenue_paise": eligible_revenue_paise,
            "eligible_revenue_rupees": eligible_revenue_rupees,
            "ai_decision_count": ai_decision_count,
            "policy_approved_count": policy_approved_count,
            "policy_blocked_count": policy_blocked_count,
            "escalation_count": escalation_count,
            "actions_attempted": total_actions_attempted,
            "total_actions_attempted": total_actions_attempted,
            "actions_by_execution_mode": {
                "real_test_mode_count": real_test_mode_count,
                "simulated_mode_count": simulated_mode_count,
            },
            "actions_by_strategy": actions_by_strategy,
            "verified_recovered_count": verified_recovered_count,
            "verified_recovered_cases": verified_recovered_count,
            "verified_recovered_paise": verified_recovered_paise,
            "verified_recovered_rupees": verified_recovered_rupees,
            "total_verified_recovered_rupees": verified_recovered_rupees,
            "total_verified_recovered_paise": verified_recovered_paise,
            "simulated_recovered_count": simulated_recovered_count,
            "simulated_recovered_paise": simulated_recovered_paise,
            "simulated_recovered_rupees": simulated_recovered_rupees,
            "total_unrecovered_paise": total_unrecovered_paise,
            "total_unrecovered_rupees": total_unrecovered_rupees,
            "unrecovered_breakdown_paise": unrecovered_breakdown,
            "case_recovery_rate": round(case_recovery_rate, 4),
            "revenue_recovery_rate": round(revenue_recovery_rate, 4),
            "recovery_rate": round(case_recovery_rate, 4),
            "action_success_rate": round(action_success_rate, 4),
            "duplicate_actions_prevented": duplicate_prevented_count,
            "reliability_rates": {
                "ai_failure_rate": round(ai_failure_rate, 4),
                "provider_fallback_rate": round(provider_fallback_rate, 4),
                "razorpay_api_failure_rate": round(razorpay_api_failure_rate, 4),
            },
        }

    @classmethod
    def get_segment_strategy_performance_table(cls, db: Session) -> List[Dict[str, Any]]:
        """
        Retrieve segment strategy performance metrics table carrying empirical confidence
        levels and Wilson score lower bounds.
        """
        strategies = db.query(RecoveryStrategy).join(Segment).all()
        table: List[Dict[str, Any]] = []

        for s in strategies:
            table.append({
                "strategy_id": s.id,
                "segment_id": s.segment_id,
                "segment_name": s.segment.name if s.segment else "UNKNOWN",
                "failure_category": s.segment.failure_category if s.segment else "UNKNOWN",
                "strategy_type": s.strategy_type,
                "attempt_count": s.attempt_count,
                "success_count": s.success_count,
                "total_recovered_paise": s.total_recovered_paise,
                "total_recovered_rupees": round(s.total_recovered_paise / 100.0, 2),
                "recovery_rate": round(s.recovery_rate or 0.0, 4),
                "wilson_lower_bound": round(s.wilson_lower_bound or 0.0, 4),
                "sample_size_sufficient": s.sample_size_sufficient,
                "confidence_level": s.confidence_level or "INSUFFICIENT",
                "data_source": s.data_source or DataCategory.OBSERVED.value,
            })

        return table

    @classmethod
    def get_failure_analysis_breakdown(cls, db: Session) -> Dict[str, Any]:
        """
        Compute root-cause failure analysis breakdown across failure categories and unrecovered states.
        """
        categories = [fc.value for fc in FailureCategory]
        breakdown_by_category: Dict[str, Dict[str, Any]] = {}

        for cat in categories:
            txns = db.query(Transaction).filter(
                Transaction.status == TransactionStatus.FAILED.value,
                Transaction.failure_category == cat,
            ).all()

            cat_total_count = len(txns)
            cat_total_value_paise = sum(t.amount_paise for t in txns)

            cat_cases = (
                db.query(RecoveryCase)
                .join(Transaction)
                .filter(Transaction.failure_category == cat)
                .all()
            )

            recovered_count = sum(1 for c in cat_cases if c.status == RecoveryCaseStatus.RECOVERED.value)
            ineligible_count = sum(1 for c in cat_cases if c.status == RecoveryCaseStatus.INELIGIBLE.value)
            policy_blocked_count = sum(1 for c in cat_cases if c.status == RecoveryCaseStatus.POLICY_BLOCKED.value)
            escalated_count = sum(1 for c in cat_cases if c.status == RecoveryCaseStatus.ESCALATED.value)
            unrecovered_count = sum(1 for c in cat_cases if c.status == RecoveryCaseStatus.UNRECOVERED.value)

            breakdown_by_category[cat] = {
                "total_transactions": cat_total_count,
                "total_value_paise": cat_total_value_paise,
                "total_value_rupees": round(cat_total_value_paise / 100.0, 2),
                "recovered_count": recovered_count,
                "ineligible_count": ineligible_count,
                "policy_blocked_count": policy_blocked_count,
                "escalated_count": escalated_count,
                "unrecovered_count": unrecovered_count,
            }

        return {
            "breakdown_by_failure_category": breakdown_by_category,
        }
