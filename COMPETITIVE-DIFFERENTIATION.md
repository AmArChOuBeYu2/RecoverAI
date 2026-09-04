# COMPETITIVE-DIFFERENTIATION.md — RecoverAI vs Reven

## Executive Summary
Both systems implement Track 03's core requirement: detect failed payments, diagnose root causes, apply safety policies, execute bounded recovery actions, and verify outcomes. The difference is in what happens AFTER recovery execution.

Reven focuses on: case-level evidence-first recovery with strong safety controls.
RecoverAI focuses on: portfolio-level strategy optimization with a closed feedback loop from verified outcomes.

Reven answers: "Was this recovery safe and justified?"
RecoverAI answers: "Which recovery strategy works best for this type of failure, and how do we know?"

## Feature Comparison Table

| Dimension | Reven | RecoverAI |
| :--- | :--- | :--- |
| Payment failure detection | Yes | Yes |
| Webhook ingestion + verification | Yes | Yes |
| AI-powered diagnosis | Yes | Yes |
| Deterministic policy gate | Yes | Yes |
| Payment Link recovery (real Razorpay) | Yes | Yes |
| Outcome verification | Yes | Yes |
| Full audit trail | Yes | Yes |
| Human review for ambiguous cases | Yes | Yes |
| Payment segmentation | No | Yes |
| Recoverability/propensity scoring | No | Yes |
| Multi-strategy evaluation | No | Yes |
| Strategy performance tracking | No | Yes |
| Strategy-vs-strategy comparison | No | Yes |
| Recovery policy simulation | No | Yes |
| Outcome attribution | No | Yes |
| Feedback loop (outcomes → strategy improvement) | No | Yes |
| Incremental recovery analysis | No | Yes |
| Portfolio-level intelligence | No | Yes |
| Evidence-based confidence scoring | Partial | Yes |
| LLM provider failover (OpenAI → Gemini → deterministic) | Partial | Yes |

## Architectural Comparison

Reven (Linear):
```
Failed Payment → Detect → Diagnose → Trust Gate → Recover → Verify → Audit
```

RecoverAI (Closed Loop):
```
Failed Payment → Detect → Segment → Score → Evaluate Strategies → Policy Gate → Act → Verify → Attribute Outcome → Update Strategy Performance → (feeds back into strategy evaluation)
```

## Where Reven Is Strong
- Strong evidence-first safety model
- Clean webhook → recovery → verification pipeline
- Trust Gate concept is well-designed
- Human review integration
- Case-level auditability

## Where RecoverAI Differentiates
1. **Portfolio Intelligence**: Not just recovering one payment, but understanding recovery patterns across the entire failed payment portfolio
2. **Segmentation**: Grouping failures by type, amount, method, customer history to identify where recovery investment has highest ROI
3. **Strategy Performance**: Tracking which strategy (Payment Link vs Retry vs Reminder vs Delayed Retry) actually works best per segment, backed by observed data not just AI opinion
4. **Policy Simulation**: Read-only simulator comparing current policy vs RecoverAI optimized policy, showing projected incremental recovery
5. **Outcome Attribution**: When a recovery succeeds/fails, attributing that result back to the strategy and segment, closing the learning loop
6. **Evidence-Based Confidence**: Every recommendation shows sample size, observed success rate, and confidence level rather than just AI confidence scores
7. **Continuous Improvement**: Strategy recommendations improve as more outcomes are observed

## What RecoverAI Does NOT Do
- Does not copy Reven's implementation, UI, or copywriting
- Does not claim AI-only differentiation
- Does not fabricate Razorpay capabilities
- Does not count simulated outcomes as verified recovery
- Does not bypass deterministic safety controls

## The Core Insight

Most recovery systems ask: "Can we recover this payment?"

RecoverAI asks: "Which recovery approach has the highest probability of success for this type of payment, based on what we've actually observed?"

This shifts the value proposition from reactive recovery to predictive recovery optimization.
