"""
Core Deterministic Policy Engine for RecoverAI
Evaluates 14 explicit safety rules in strict precedence order. Independent of LLM.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.models.recovery_case import RecoveryCase
from backend.models.recovery_action import RecoveryAction
from backend.models.policy_decision import PolicyDecision
from backend.models.enums import (
    PolicyDecisionType,
    StrategyType,
    RecoveryCaseStatus,
)
from backend.models.audit_event import AuditEvent
from backend.services.policy_config import PolicyConfig
from backend.services.trust_gate import TrustGateService, TrustGateResult

logger = logging.getLogger(__name__)

class RuleEvaluationDetail(BaseModel):
    """Detailed evaluation log for an individual policy rule."""
    model_config = ConfigDict(populate_by_name=True)

    rule_name: str
    passed: bool
    current_value: Any
    threshold_value: Any
    decision_impact: str # APPROVE, DENY, ESCALATE, PASS
    explanation: str

class PolicyEvaluationResult(BaseModel):
    """Structured result returned by PolicyEngine."""
    model_config = ConfigDict(populate_by_name=True)

    policy_version: str = "v1.0"
    decision: str # PolicyDecisionType (APPROVE, DENY, ESCALATE)
    strategy: str
    rules_evaluated: List[RuleEvaluationDetail]
    failed_rules: List[RuleEvaluationDetail]
    blocking_rule: Optional[str] = None
    reason: str
    requires_human: bool
    can_execute_action: bool

class PolicyEngine:
    """Independent, deterministic policy engine enforcing RecoverAI safety rules."""

    @classmethod
    def evaluate(
        cls,
        case: RecoveryCase,
        proposed_strategy: str,
        ai_confidence: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
        config_override: Optional[PolicyConfig] = None,
        db: Optional[Session] = None,
        persist_decision: bool = False,
    ) -> PolicyEvaluationResult:
        """
        Evaluate proposed_strategy against case context using explicit rule precedence:
        1. Terminal state check
        2. Already recovered check
        3. Trust Gate check
        4. Strategy enum validation
        5. Max automated action amount check
        6. High value escalation threshold check
        7. Low AI confidence / recoverability check
        8. Max retries check
        9. Max 24h customer contacts check
        10. Cooldown period check
        11. Allowed communication hours check
        12. Duplicate active action / link check
        13. Strategy specific constraint check
        """
        cfg = config_override or PolicyConfig.from_settings()
        ctx = context or {}
        rules_evaluated: List[RuleEvaluationDetail] = []
        failed_rules: List[RuleEvaluationDetail] = []

        now_utc = ctx.get("current_time_utc") or datetime.now(timezone.utc)
        # Convert UTC to IST (+5:30) for communication window check
        ist_time = now_utc + timedelta(hours=5, minutes=30)
        current_hour_ist = ist_time.hour

        # ---------------------------------------------------------
        # PRECEDENCE 1: Invalid / Terminal State Protection
        # ---------------------------------------------------------
        rule_terminal = RuleEvaluationDetail(
            rule_name="TERMINAL_STATE",
            passed=not case.is_terminal,
            current_value=case.status,
            threshold_value="non-terminal",
            decision_impact="DENY" if case.is_terminal else "PASS",
            explanation=f"Case state is '{case.status}' (is_terminal={case.is_terminal})"
            + (" - FAIL: Cannot process terminal case" if case.is_terminal else " - PASS"),
        )
        rules_evaluated.append(rule_terminal)
        if case.is_terminal:
            failed_rules.append(rule_terminal)
            return cls._build_result(cfg.policy_version, PolicyDecisionType.DENY.value, proposed_strategy, rules_evaluated, failed_rules, rule_terminal.rule_name, case, db, persist_decision)

        # ---------------------------------------------------------
        # PRECEDENCE 2: Already Recovered Check
        # ---------------------------------------------------------
        is_recovered = (case.status == RecoveryCaseStatus.RECOVERED.value)
        rule_already_recovered = RuleEvaluationDetail(
            rule_name="ALREADY_RECOVERED",
            passed=not is_recovered,
            current_value=case.status,
            threshold_value=f"not {RecoveryCaseStatus.RECOVERED.value}",
            decision_impact="DENY" if is_recovered else "PASS",
            explanation="Case is already marked as RECOVERED" if is_recovered else "Case is not recovered - PASS",
        )
        rules_evaluated.append(rule_already_recovered)
        if is_recovered:
            failed_rules.append(rule_already_recovered)
            return cls._build_result(cfg.policy_version, PolicyDecisionType.DENY.value, proposed_strategy, rules_evaluated, failed_rules, rule_already_recovered.rule_name, case, db, persist_decision)

        # ---------------------------------------------------------
        # PRECEDENCE 3: Trust Gate Check
        # ---------------------------------------------------------
        trust_result: TrustGateResult = TrustGateService.evaluate(
            transaction=case.transaction,
            customer=case.customer,
            context=ctx,
        )
        rule_trust = RuleEvaluationDetail(
            rule_name="TRUST_GATE_SUSPICIOUS",
            passed=trust_result.passed,
            current_value=trust_result.reason,
            threshold_value="no suspicious pattern",
            decision_impact="DENY" if not trust_result.passed else "PASS",
            explanation=trust_result.reason,
        )
        rules_evaluated.append(rule_trust)
        if not trust_result.passed:
            failed_rules.append(rule_trust)
            return cls._build_result(cfg.policy_version, PolicyDecisionType.DENY.value, proposed_strategy, rules_evaluated, failed_rules, rule_trust.rule_name, case, db, persist_decision)

        # ---------------------------------------------------------
        # PRECEDENCE 4: Strategy Enum Validation
        # ---------------------------------------------------------
        valid_strategies = {s.value for s in StrategyType}
        is_valid_strategy = proposed_strategy in valid_strategies
        rule_strategy_enum = RuleEvaluationDetail(
            rule_name="UNSUPPORTED_STRATEGY",
            passed=is_valid_strategy,
            current_value=proposed_strategy,
            threshold_value=list(valid_strategies),
            decision_impact="DENY" if not is_valid_strategy else "PASS",
            explanation=f"Strategy '{proposed_strategy}' is unsupported" if not is_valid_strategy else f"Strategy '{proposed_strategy}' is valid - PASS",
        )
        rules_evaluated.append(rule_strategy_enum)
        if not is_valid_strategy:
            failed_rules.append(rule_strategy_enum)
            return cls._build_result(cfg.policy_version, PolicyDecisionType.DENY.value, proposed_strategy, rules_evaluated, failed_rules, rule_strategy_enum.rule_name, case, db, persist_decision)

        # ---------------------------------------------------------
        # PRECEDENCE 5: Maximum Automated Action Amount Cap
        # ---------------------------------------------------------
        amount_paise = case.transaction.amount_paise
        exceeds_max_auto = amount_paise > cfg.max_automated_action_amount_paise
        rule_max_amount = RuleEvaluationDetail(
            rule_name="MAX_AUTOMATED_AMOUNT",
            passed=not exceeds_max_auto,
            current_value=f"₹{amount_paise / 100:.2f}",
            threshold_value=f"₹{cfg.max_automated_action_amount_paise / 100:.2f}",
            decision_impact="DENY" if exceeds_max_auto else "PASS",
            explanation=f"Transaction amount ₹{amount_paise / 100:.2f} exceeds maximum automated action limit of ₹{cfg.max_automated_action_amount_paise / 100:.2f}"
            if exceeds_max_auto else "Amount is within automated action limit - PASS",
        )
        rules_evaluated.append(rule_max_amount)
        if exceeds_max_auto:
            failed_rules.append(rule_max_amount)
            return cls._build_result(cfg.policy_version, PolicyDecisionType.DENY.value, proposed_strategy, rules_evaluated, failed_rules, rule_max_amount.rule_name, case, db, persist_decision)

        # ---------------------------------------------------------
        # PRECEDENCE 6: High-Value Human Escalation Threshold
        # ---------------------------------------------------------
        is_high_value = amount_paise > cfg.high_value_threshold_paise
        rule_high_value = RuleEvaluationDetail(
            rule_name="HIGH_VALUE",
            passed=not is_high_value,
            current_value=f"₹{amount_paise / 100:.2f}",
            threshold_value=f"₹{cfg.high_value_threshold_paise / 100:.2f}",
            decision_impact="ESCALATE" if is_high_value else "PASS",
            explanation=f"Transaction amount ₹{amount_paise / 100:.2f} exceeds high-value escalation threshold ₹{cfg.high_value_threshold_paise / 100:.2f}"
            if is_high_value else "Amount is below high-value threshold - PASS",
        )
        rules_evaluated.append(rule_high_value)
        if is_high_value:
            failed_rules.append(rule_high_value)
            return cls._build_result(cfg.policy_version, PolicyDecisionType.ESCALATE.value, proposed_strategy, rules_evaluated, failed_rules, rule_high_value.rule_name, case, db, persist_decision)

        # ---------------------------------------------------------
        # PRECEDENCE 7: Low AI Confidence / Recoverability Check
        # ---------------------------------------------------------
        conf_val = ai_confidence if ai_confidence is not None else case.recoverability_score
        is_low_conf = (conf_val is not None and conf_val < cfg.min_ai_confidence)
        rule_low_conf = RuleEvaluationDetail(
            rule_name="LOW_CONFIDENCE",
            passed=not is_low_conf,
            current_value=f"{conf_val:.2f}" if conf_val is not None else "N/A",
            threshold_value=f"{cfg.min_ai_confidence:.2f}",
            decision_impact="ESCALATE" if is_low_conf else "PASS",
            explanation=f"AI confidence {conf_val:.2f} is below minimum threshold {cfg.min_ai_confidence:.2f}"
            if is_low_conf else "AI confidence meets minimum threshold - PASS",
        )
        rules_evaluated.append(rule_low_conf)
        if is_low_conf:
            failed_rules.append(rule_low_conf)
            return cls._build_result(cfg.policy_version, PolicyDecisionType.ESCALATE.value, proposed_strategy, rules_evaluated, failed_rules, rule_low_conf.rule_name, case, db, persist_decision)

        # ---------------------------------------------------------
        # PRECEDENCE 8: Retry Limit Check
        # ---------------------------------------------------------
        attempts = case.attempt_count
        retry_exceeded = attempts >= cfg.max_retries
        rule_retry = RuleEvaluationDetail(
            rule_name="MAX_RETRIES",
            passed=not retry_exceeded,
            current_value=attempts,
            threshold_value=cfg.max_retries,
            decision_impact="DENY" if retry_exceeded else "PASS",
            explanation=f"Attempt count {attempts} reaches or exceeds max retries limit {cfg.max_retries}"
            if retry_exceeded else f"Attempt count {attempts} is below limit {cfg.max_retries} - PASS",
        )
        rules_evaluated.append(rule_retry)
        if retry_exceeded:
            failed_rules.append(rule_retry)
            return cls._build_result(cfg.policy_version, PolicyDecisionType.DENY.value, proposed_strategy, rules_evaluated, failed_rules, rule_retry.rule_name, case, db, persist_decision)

        # ---------------------------------------------------------
        # PRECEDENCE 9: Customer 24h Contact Limit Check
        # ---------------------------------------------------------
        contacts_24h = case.customer.contacts_count_24h if case.customer else 0
        contact_exceeded = contacts_24h >= cfg.max_contacts_24h
        rule_contact = RuleEvaluationDetail(
            rule_name="MAX_CONTACTS_24H",
            passed=not contact_exceeded,
            current_value=contacts_24h,
            threshold_value=cfg.max_contacts_24h,
            decision_impact="DENY" if contact_exceeded else "PASS",
            explanation=f"Customer contacts in 24h ({contacts_24h}) reaches or exceeds limit {cfg.max_contacts_24h}"
            if contact_exceeded else f"Contacts count ({contacts_24h}) is within limit - PASS",
        )
        rules_evaluated.append(rule_contact)
        if contact_exceeded:
            failed_rules.append(rule_contact)
            return cls._build_result(cfg.policy_version, PolicyDecisionType.DENY.value, proposed_strategy, rules_evaluated, failed_rules, rule_contact.rule_name, case, db, persist_decision)

        # ---------------------------------------------------------
        # PRECEDENCE 10: Cooldown Period Check
        # ---------------------------------------------------------
        cooldown_active = False
        if case.actions:
            last_action = max(case.actions, key=lambda a: a.executed_at)
            elapsed_sec = (now_utc - last_action.executed_at).total_seconds()
            cooldown_sec = cfg.cooldown_minutes * 60
            if elapsed_sec < cooldown_sec:
                cooldown_active = True
                elapsed_min = int(elapsed_sec // 60)

        rule_cooldown = RuleEvaluationDetail(
            rule_name="COOLDOWN_ACTIVE",
            passed=not cooldown_active,
            current_value=f"{elapsed_min}m elapsed" if cooldown_active else "no recent attempt",
            threshold_value=f"{cfg.cooldown_minutes}m cooldown",
            decision_impact="DENY" if cooldown_active else "PASS",
            explanation=f"Cooldown active: {elapsed_min}m elapsed since last attempt (minimum {cfg.cooldown_minutes}m required)"
            if cooldown_active else "Cooldown period satisfied - PASS",
        )
        rules_evaluated.append(rule_cooldown)
        if cooldown_active:
            failed_rules.append(rule_cooldown)
            return cls._build_result(cfg.policy_version, PolicyDecisionType.DENY.value, proposed_strategy, rules_evaluated, failed_rules, rule_cooldown.rule_name, case, db, persist_decision)

        # ---------------------------------------------------------
        # PRECEDENCE 11: Allowed Communication Hours (IST)
        # ---------------------------------------------------------
        outside_hours = not (cfg.contact_start_hour <= current_hour_ist < cfg.contact_end_hour)
        rule_hours = RuleEvaluationDetail(
            rule_name="CONTACT_HOURS",
            passed=not outside_hours,
            current_value=f"{current_hour_ist:02d}:00 IST",
            threshold_value=f"{cfg.contact_start_hour:02d}:00 - {cfg.contact_end_hour:02d}:00 IST",
            decision_impact="DENY" if outside_hours else "PASS",
            explanation=f"Current time {current_hour_ist:02d}:00 IST is outside allowed window {cfg.contact_start_hour:02d}:00–{cfg.contact_end_hour:02d}:00 IST"
            if outside_hours else "Time is within allowed communication window - PASS",
        )
        rules_evaluated.append(rule_hours)
        if outside_hours:
            failed_rules.append(rule_hours)
            return cls._build_result(cfg.policy_version, PolicyDecisionType.DENY.value, proposed_strategy, rules_evaluated, failed_rules, rule_hours.rule_name, case, db, persist_decision)

        # ---------------------------------------------------------
        # PRECEDENCE 12: Active Payment Link Duplicate Protection
        # ---------------------------------------------------------
        has_active_link = any(
            a.action_type == StrategyType.PAYMENT_LINK.value and a.status in ("PENDING", "SENT")
            for a in case.actions
        )
        duplicate_link_blocked = (proposed_strategy == StrategyType.PAYMENT_LINK.value and has_active_link)
        rule_duplicate_link = RuleEvaluationDetail(
            rule_name="ACTIVE_PAYMENT_LINK",
            passed=not duplicate_link_blocked,
            current_value="active link exists" if has_active_link else "none",
            threshold_value="no active pending/sent link",
            decision_impact="DENY" if duplicate_link_blocked else "PASS",
            explanation="An active Payment Link is already pending/sent for this case" if duplicate_link_blocked else "No duplicate active link - PASS",
        )
        rules_evaluated.append(rule_duplicate_link)
        if duplicate_link_blocked:
            failed_rules.append(rule_duplicate_link)
            return cls._build_result(cfg.policy_version, PolicyDecisionType.DENY.value, proposed_strategy, rules_evaluated, failed_rules, rule_duplicate_link.rule_name, case, db, persist_decision)

        # ---------------------------------------------------------
        # PRECEDENCE 13: Strategy-Specific Constraints
        # ---------------------------------------------------------
        if proposed_strategy == StrategyType.HUMAN_REVIEW.value:
            rule_human_review = RuleEvaluationDetail(
                rule_name="STRATEGY_CONSTRAINTS",
                passed=False,
                current_value=proposed_strategy,
                threshold_value="Automated strategy",
                decision_impact="ESCALATE",
                explanation="Strategy 'HUMAN_REVIEW' explicitly mandates human escalation",
            )
            rules_evaluated.append(rule_human_review)
            failed_rules.append(rule_human_review)
            return cls._build_result(cfg.policy_version, PolicyDecisionType.ESCALATE.value, proposed_strategy, rules_evaluated, failed_rules, rule_human_review.rule_name, case, db, persist_decision)

        # ---------------------------------------------------------
        # PRECEDENCE 14: Final Approval
        # ---------------------------------------------------------
        rule_approve = RuleEvaluationDetail(
            rule_name="POLICY_APPROVAL",
            passed=True,
            current_value="all rules passed",
            threshold_value="all rules passed",
            decision_impact="APPROVE",
            explanation="All policy safety checks passed cleanly",
        )
        rules_evaluated.append(rule_approve)
        return cls._build_result(cfg.policy_version, PolicyDecisionType.APPROVE.value, proposed_strategy, rules_evaluated, failed_rules, None, case, db, persist_decision)

    @classmethod
    def _build_result(
        cls,
        policy_version: str,
        decision: str,
        strategy: str,
        rules_evaluated: List[RuleEvaluationDetail],
        failed_rules: List[RuleEvaluationDetail],
        blocking_rule: Optional[str],
        case: RecoveryCase,
        db: Optional[Session] = None,
        persist_decision: bool = False,
    ) -> PolicyEvaluationResult:
        """Construct structured PolicyEvaluationResult and optionally persist to database."""
        requires_human = (decision == PolicyDecisionType.ESCALATE.value)
        can_execute = (decision == PolicyDecisionType.APPROVE.value)
        
        reason = (
            f"Policy {decision}: Blocked by rule '{blocking_rule}' - {failed_rules[-1].explanation}"
            if failed_rules and blocking_rule
            else f"Policy {decision}: All checks passed for strategy '{strategy}'"
        )

        result = PolicyEvaluationResult(
            policy_version=policy_version,
            decision=decision,
            strategy=strategy,
            rules_evaluated=rules_evaluated,
            failed_rules=failed_rules,
            blocking_rule=blocking_rule,
            reason=reason,
            requires_human=requires_human,
            can_execute_action=can_execute,
        )

        if persist_decision and db is not None:
            cls.persist_policy_decision(db, case, result)

        return result

    @classmethod
    def persist_policy_decision(
        cls, db: Session, case: RecoveryCase, result: PolicyEvaluationResult
    ) -> PolicyDecision:
        """Persist PolicyDecision record and audit event to database."""
        policy_record = PolicyDecision(
            recovery_case_id=case.id,
            decision=result.decision,
            evaluated_rules=[r.model_dump() for r in result.rules_evaluated],
            blocking_rule=result.blocking_rule,
            reason=result.reason,
        )
        db.add(policy_record)

        audit_event = AuditEvent(
            recovery_case_id=case.id,
            event_type="POLICY_EVALUATED",
            actor="POLICY_ENGINE",
            description=f"Policy decision '{result.decision}' for strategy '{result.strategy}' (Version: {result.policy_version})",
            details={
                "policy_version": result.policy_version,
                "decision": result.decision,
                "strategy": result.strategy,
                "blocking_rule": result.blocking_rule,
                "failed_rules": [r.rule_name for r in result.failed_rules],
            },
        )
        db.add(audit_event)
        db.flush()
        return policy_record
