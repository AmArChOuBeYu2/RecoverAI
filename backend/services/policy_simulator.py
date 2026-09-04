"""
Policy Simulator Service — RecoverAI Milestone 16
Provides read-only simulation comparing baseline policy vs. RecoverAI optimized policy.
NEVER writes to Razorpay API or mutates real transaction/case states.
All results labeled simulation_mode = DataCategory.PROJECTED.value.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.models.customer import Customer
from backend.models.recovery_case import RecoveryCase
from backend.models.transaction import Transaction
from backend.models.policy_simulation import PolicySimulation
from backend.models.enums import (
    FailureCategory,
    StrategyType,
    PolicyDecisionType,
    DataCategory,
    CustomerType,
    AmountRange,
    RecoveryCaseStatus,
)
from backend.services.segmentation import SegmentationService
from backend.services.verification import SIMULATED_CONVERSION_RATES, VerificationService
from backend.services.policy_engine import PolicyEngine

logger = logging.getLogger(__name__)

# Strategy conversion multipliers relative to failure category baseline
STRATEGY_CONVERSION_MULTIPLIERS: Dict[str, float] = {
    StrategyType.PAYMENT_LINK.value: 1.15,
    StrategyType.DELAYED_RETRY.value: 1.10,
    StrategyType.METHOD_SWITCH.value: 0.95,
    StrategyType.REMINDER.value: 0.85,
    StrategyType.NO_ACTION.value: 0.00,
    StrategyType.HUMAN_REVIEW.value: 0.50,
    StrategyType.ESCALATION.value: 0.00,
}

class PolicySimulator:
    """
    Read-only policy simulator comparing current baseline policy vs RecoverAI optimized policy.
    
    Invariants:
    1. Read-only: Zero Razorpay API calls, zero state mutations on live cases/transactions.
    2. Runs against the same transaction set for fair side-by-side comparison.
    3. Evaluates two policy configurations: 'current_baseline' and 'recoverai_optimized'.
    4. Labels all outputs with simulation_mode = PROJECTED.
    """

    @classmethod
    def run_simulation(
        cls,
        db: Session,
        batch_run_id: Optional[str] = None,
        limit: int = 500,
        as_of_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Run side-by-side policy simulation comparing baseline vs RecoverAI optimized policy.
        """
        now = as_of_time or datetime.now(timezone.utc)

        # 1. Fetch transactions for simulation
        txns = db.query(Transaction).order_by(Transaction.created_at.desc()).limit(limit).all()
        if not txns:
            logger.warning("No transactions found for policy simulation.")
            empty_sim_baseline = cls._create_empty_simulation("current_baseline", batch_run_id)
            empty_sim_optimized = cls._create_empty_simulation("recoverai_optimized", batch_run_id)
            db.add_all([empty_sim_baseline, empty_sim_optimized])
            db.flush()
            return cls._format_comparison_result(empty_sim_baseline, empty_sim_optimized)

        # 2. Run Baseline Policy Simulation
        baseline_sim = cls._evaluate_baseline_policy(db, txns, batch_run_id, now)

        # 3. Run RecoverAI Optimized Policy Simulation
        optimized_sim = cls._evaluate_recoverai_policy(db, txns, batch_run_id, now)

        db.add_all([baseline_sim, optimized_sim])
        db.flush()

        return cls._format_comparison_result(baseline_sim, optimized_sim)

    @classmethod
    def _evaluate_baseline_policy(
        cls,
        db: Session,
        txns: List[Transaction],
        batch_run_id: Optional[str],
        as_of_time: datetime,
    ) -> PolicySimulation:
        """
        Evaluate Baseline Policy ('current_baseline'):
        Naive policy that sends a generic Payment Link for all failed transactions without segment awareness or eligibility bounds.
        """
        total_txns = len(txns)
        revenue_at_risk_paise = sum(t.amount_paise for t in txns)

        eligible_count = 0
        eligible_revenue_paise = 0
        projected_recovered_paise = 0
        actions_projected = 0
        policy_blocks_projected = 0
        escalations_projected = 0
        contacts_projected = 0

        for t in txns:
            # Baseline treats all failed transactions with amount > 0 as eligible
            if t.amount_paise > 0:
                eligible_count += 1
                eligible_revenue_paise += t.amount_paise

                # Baseline sends payment link to everyone
                actions_projected += 1
                contacts_projected += 1

                # Baseline conversion rate = unweighted baseline category rate * 0.85 (due to lack of targeting)
                base_rate = VerificationService.get_simulated_conversion_probability(t.failure_category)
                effective_rate = min(0.95, base_rate * 0.85)

                expected_paise = int(round(t.amount_paise * effective_rate))
                projected_recovered_paise += expected_paise

        recovery_rate = (projected_recovered_paise / revenue_at_risk_paise) if revenue_at_risk_paise > 0 else 0.0

        return PolicySimulation(
            batch_run_id=batch_run_id,
            policy_name="current_baseline",
            total_transactions=total_txns,
            revenue_at_risk_paise=revenue_at_risk_paise,
            eligible_count=eligible_count,
            eligible_revenue_paise=eligible_revenue_paise,
            projected_recovered_paise=projected_recovered_paise,
            projected_recovery_rate=round(recovery_rate, 4),
            actions_projected=actions_projected,
            policy_blocks_projected=policy_blocks_projected,
            escalations_projected=escalations_projected,
            contacts_projected=contacts_projected,
            simulation_mode=DataCategory.PROJECTED.value,
        )

    @classmethod
    def _evaluate_recoverai_policy(
        cls,
        db: Session,
        txns: List[Transaction],
        batch_run_id: Optional[str],
        as_of_time: datetime,
    ) -> PolicySimulation:
        """
        Evaluate RecoverAI Policy ('recoverai_optimized'):
        Segment-aware strategy selection utilizing 4D canonical segmentation, policy engine safety rules, and strategy optimization.
        """
        total_txns = len(txns)
        revenue_at_risk_paise = sum(t.amount_paise for t in txns)

        eligible_count = 0
        eligible_revenue_paise = 0
        projected_recovered_paise = 0
        actions_projected = 0
        policy_blocks_projected = 0
        escalations_projected = 0
        contacts_projected = 0

        for t in txns:
            # Derive 4D segment
            cust_type = t.customer.customer_type if t.customer and t.customer.customer_type else CustomerType.NEW.value
            amt_range = SegmentationService.derive_amount_range(t.amount_paise)
            fc = t.failure_category or FailureCategory.UNKNOWN.value
            pm = t.payment_method or "card"

            # Create transient in-memory objects for read-only policy evaluation
            transient_cust = Customer(
                id=t.customer_id or f"sim_cust_{t.id}",
                customer_type=cust_type,
                contacts_count_24h=0,
                failed_transactions=0,
                successful_transactions=0,
            )
            transient_case = RecoveryCase(
                id=f"sim_case_{t.id}",
                transaction_id=t.id,
                customer_id=t.customer_id,
                transaction=t,
                customer=transient_cust,
                status=RecoveryCaseStatus.ELIGIBLE.value,
                attempt_count=0,
                is_terminal=False,
                actions=[],
            )

            # Strategy Selection Optimization: Select optimal strategy per segment failure category
            selected_strat = cls._select_optimal_strategy_for_sim(fc, pm, amt_range)

            # Evaluate PolicyEngine rules in memory (persist_decision=False)
            p_decision = PolicyEngine.evaluate(
                case=transient_case,
                proposed_strategy=selected_strat,
                context={"current_time_utc": as_of_time},
                persist_decision=False,
            )

            # Clear transient relationship backref so SQLAlchemy doesn't warn on flush
            transient_case.transaction = None

            if p_decision.decision == PolicyDecisionType.DENY.value:
                policy_blocks_projected += 1
                continue
            elif p_decision.decision == PolicyDecisionType.ESCALATE.value:
                escalations_projected += 1
                continue

            # Eligible & Approved under RecoverAI Policy
            eligible_count += 1
            eligible_revenue_paise += t.amount_paise
            actions_projected += 1

            if selected_strat in (StrategyType.PAYMENT_LINK.value, StrategyType.REMINDER.value, StrategyType.METHOD_SWITCH.value):
                contacts_projected += 1

            # Compute segment-optimized conversion rate
            base_conv = VerificationService.get_simulated_conversion_probability(fc)
            strat_mult = STRATEGY_CONVERSION_MULTIPLIERS.get(selected_strat, 1.0)
            effective_conv = min(0.95, base_conv * strat_mult)

            expected_paise = int(round(t.amount_paise * effective_conv))
            projected_recovered_paise += expected_paise

        recovery_rate = (projected_recovered_paise / revenue_at_risk_paise) if revenue_at_risk_paise > 0 else 0.0

        return PolicySimulation(
            batch_run_id=batch_run_id,
            policy_name="recoverai_optimized",
            total_transactions=total_txns,
            revenue_at_risk_paise=revenue_at_risk_paise,
            eligible_count=eligible_count,
            eligible_revenue_paise=eligible_revenue_paise,
            projected_recovered_paise=projected_recovered_paise,
            projected_recovery_rate=round(recovery_rate, 4),
            actions_projected=actions_projected,
            policy_blocks_projected=policy_blocks_projected,
            escalations_projected=escalations_projected,
            contacts_projected=contacts_projected,
            simulation_mode=DataCategory.PROJECTED.value,
        )

    @classmethod
    def _select_optimal_strategy_for_sim(cls, failure_category: str, payment_method: str, amount_range: str) -> str:
        """Select optimal strategy for simulation based on failure category."""
        if failure_category == FailureCategory.AUTHENTICATION_FAILURE.value:
            return StrategyType.PAYMENT_LINK.value
        elif failure_category in (FailureCategory.BANK_TIMEOUT.value, FailureCategory.NETWORK_FAILURE.value):
            return StrategyType.DELAYED_RETRY.value
        elif failure_category == FailureCategory.CHECKOUT_ABANDONMENT.value:
            return StrategyType.PAYMENT_LINK.value
        elif failure_category == FailureCategory.INSUFFICIENT_FUNDS.value:
            return StrategyType.REMINDER.value
        elif failure_category == FailureCategory.REPEATED_FAILURE.value:
            return StrategyType.NO_ACTION.value
        else:
            return StrategyType.PAYMENT_LINK.value

    @classmethod
    def _create_empty_simulation(cls, policy_name: str, batch_run_id: Optional[str]) -> PolicySimulation:
        """Helper to create empty simulation record."""
        return PolicySimulation(
            batch_run_id=batch_run_id,
            policy_name=policy_name,
            total_transactions=0,
            revenue_at_risk_paise=0,
            eligible_count=0,
            eligible_revenue_paise=0,
            projected_recovered_paise=0,
            projected_recovery_rate=0.0,
            actions_projected=0,
            policy_blocks_projected=0,
            escalations_projected=0,
            contacts_projected=0,
            simulation_mode=DataCategory.PROJECTED.value,
        )

    @classmethod
    def _format_comparison_result(cls, baseline: PolicySimulation, optimized: PolicySimulation) -> Dict[str, Any]:
        """Format comparison dictionary between baseline and optimized policy simulations."""
        incremental_recovered_paise = max(0, optimized.projected_recovered_paise - baseline.projected_recovered_paise)
        incremental_recovery_rate_diff = round(optimized.projected_recovery_rate - baseline.projected_recovery_rate, 4)

        return {
            "simulation_mode": DataCategory.PROJECTED.value,
            "baseline": {
                "id": baseline.id,
                "policy_name": baseline.policy_name,
                "total_transactions": baseline.total_transactions,
                "revenue_at_risk_paise": baseline.revenue_at_risk_paise,
                "revenue_at_risk_rupees": round(baseline.revenue_at_risk_paise / 100.0, 2),
                "eligible_count": baseline.eligible_count,
                "eligible_revenue_paise": baseline.eligible_revenue_paise,
                "projected_recovered_paise": baseline.projected_recovered_paise,
                "projected_recovered_rupees": round(baseline.projected_recovered_paise / 100.0, 2),
                "projected_recovery_rate": baseline.projected_recovery_rate,
                "actions_projected": baseline.actions_projected,
                "policy_blocks_projected": baseline.policy_blocks_projected,
                "escalations_projected": baseline.escalations_projected,
                "contacts_projected": baseline.contacts_projected,
            },
            "recoverai_optimized": {
                "id": optimized.id,
                "policy_name": optimized.policy_name,
                "total_transactions": optimized.total_transactions,
                "revenue_at_risk_paise": optimized.revenue_at_risk_paise,
                "revenue_at_risk_rupees": round(optimized.revenue_at_risk_paise / 100.0, 2),
                "eligible_count": optimized.eligible_count,
                "eligible_revenue_paise": optimized.eligible_revenue_paise,
                "projected_recovered_paise": optimized.projected_recovered_paise,
                "projected_recovered_rupees": round(optimized.projected_recovered_paise / 100.0, 2),
                "projected_recovery_rate": optimized.projected_recovery_rate,
                "actions_projected": optimized.actions_projected,
                "policy_blocks_projected": optimized.policy_blocks_projected,
                "escalations_projected": optimized.escalations_projected,
                "contacts_projected": optimized.contacts_projected,
            },
            "incremental_comparison": {
                "incremental_recovered_paise": incremental_recovered_paise,
                "incremental_recovered_rupees": round(incremental_recovered_paise / 100.0, 2),
                "incremental_recovery_rate_diff": incremental_recovery_rate_diff,
                "contact_reduction_count": baseline.contacts_projected - optimized.contacts_projected,
                "policy_block_safety_additions": optimized.policy_blocks_projected - baseline.policy_blocks_projected,
            },
        }
