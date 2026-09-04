# Recovery Intelligence Foundations (Milestone 8)

## System Overview
The **Recovery Intelligence Foundation** (`RecoveryIntelligenceService`) provides the deterministic, data-driven optimization and analytics backbone for RecoverAI. It operates strictly on observed historical strategy outcomes, applying Wilson score lower-bound confidence intervals, sample-size tier gating, hierarchical 4D $\to$ 3D $\to$ Baseline fallback tracing, and transparent propensity scoring.

The intelligence layer is provider-independent and does not invoke external LLMs (OpenAI or Gemini) or depend on frontend UI components.

---

## Key Principles & Architectural Constraints

1. **Zero LLM Execution Dependency**:
   - Strategy performance, Wilson lower bounds, recoverability propensity scores, and fallback traces are 100% deterministic code.

2. **Strict Data Isolation**:
   - The intelligence layer accesses ONLY historical `OBSERVED` outcomes available at decision time (`data/observed/` or DB `strategy_outcomes`).
   - Hidden simulation ground truth (`data/simulation_truth/`) and future holdout datasets (`data/holdout/`) are **strictly inaccessible**.

3. **Temporal Leakage Prevention (Cutoff Invariant)**:
   - When evaluating strategy evidence for a decision timestamp $T_{\text{decision}}$, only outcomes recorded before $T_{\text{decision}}$ are aggregated ($T_{\text{failed}} \le T_{\text{decision}}$). Future outcomes are excluded.

4. **Source Category Separation**:
   - Evidence sources (`OBSERVED`, `VERIFIED`, `SIMULATED`, `PROJECTED`) are tracked independently and never silently merged into single metrics.

---

## Core Components & Architecture

### 1. Wilson Score Lower Bound Calculator (`backend/services/wilson_score.py`)
To prevent small-sample anomalies (e.g. $1/1 = 100\%$ naive rate) from displacing well-supported strategies (e.g. $40/150 = 26.7\%$), strategy ranking uses the Wilson score interval lower bound at $z = 1.96$ ($95\%$ confidence level):

$$\hat{p} = \frac{\text{successes}}{\text{attempts}}$$

$$\text{Wilson LB} = \frac{\hat{p} + \frac{z^2}{2n} - z \sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$

#### Small-Sample Trap Protection (Case G):
- **Strategy A** (1/1 = 100% rate): Wilson LB $\approx 0.025$ (2.5%), `INSUFFICIENT` tier.
- **Strategy B** (40/150 = 26.7% rate): Wilson LB $\approx 0.201$ (20.1%), `HIGH` tier.
- **Result**: `StrategyRanker` ranks Strategy B above Strategy A, preventing small-sample noise from driving financial execution.

---

### 2. Sample-Size Confidence Tiers
Attempt counts dictate statistical confidence tiers:
- **`INSUFFICIENT`** ($< 10$ attempts): Cannot rely on segment rate alone; triggers fallback.
- **`LOW`** ($10 – 30$ attempts): Uses lower-bound estimate with uncertainty warning.
- **`MEDIUM`** ($31 – 100$ attempts): Balanced observed evidence.
- **`HIGH`** ($> 100$ attempts): Observed rate takes primary precedence.

---

### 3. Hierarchical Fallback Engine (`backend/services/fallback_engine.py`)
When canonical 4D segment evidence is sparse ($<10$ attempts), the engine cascades down a 4-level fallback hierarchy:

```ascii
Level 1: 4D Canonical Segment (failure x method x amount x customer)
   |
   +---> Attempts >= 10? Use 4D Canonical Evidence
   |
   v (<10 attempts)
Level 2: 3D Aggregate Segment (failure x method x amount)
   |
   +---> Attempts >= 10? Use 3D Aggregate Evidence (FALLBACK_3D)
   |
   v (<10 attempts)
Level 3: Failure Category Baseline (failure)
   |
   +---> Attempts >= 10? Use Category Baseline Evidence (FALLBACK_CATEGORY)
   |
   v (<10 attempts)
Level 4: Global Safe Default / Insufficient Evidence
   |
   +---> Return INSUFFICIENT_EVIDENCE & safe default (PAYMENT_LINK / DELAYED_RETRY)
```

Every evaluation emits a structured `EvidenceTrace` logging the fallback steps, reasons, and effective segment name.

---

### 4. Deterministic Strategy Ranker (`backend/services/strategy_ranker.py`)
Ranks candidate recovery strategies (`PAYMENT_LINK`, `DELAYED_RETRY`, `REMINDER`, `METHOD_SWITCH`, `NO_ACTION`) using a 4-tier deterministic sort key:
1. **Primary**: Sample Size Tier Precedence (`HIGH` > `MEDIUM` > `LOW` > `INSUFFICIENT`)
2. **Secondary**: Wilson Lower Bound (descending)
3. **Tertiary**: Success Count (descending)
4. **Quaternary**: Strategy Name alphabetical (deterministic tie-breaker)

---

### 5. Transparent Recoverability Scorer (`backend/services/recoverability_scorer.py`)
Computes an explainable propensity score $R \in [0.01, 0.99]$ by combining deterministic factors:
- **Base Failure Category Recoverability**: `AUTHENTICATION_FAILURE` (0.65), `BANK_TIMEOUT` (0.70), `NETWORK_FAILURE` (0.68), `CHECKOUT_ABANDONMENT` (0.55), `INSUFFICIENT_FUNDS` (0.35), `REPEATED_FAILURE` (0.20).
- **Recency Bonus/Penalty**: $<1\text{h}$ (+10%), $1-6\text{h}$ (+5%), $>24\text{h}$ (-10%).
- **Customer Type Modifier**: `RETURNING` (+8%), `FATIGUED` (-15%).
- **Attempt Count Penalty**: 1 attempt (-5%), $\ge 2$ attempts (-18%).
- **24h Contact Fatigue Penalty**: $\ge 3$ contacts (-15%).
- **High Amount Penalty**: $> ₹50,000$ (-10%).

---

### 6. Portfolio Revenue-at-Risk Engine (`backend/services/portfolio_intelligence.py`)
Aggregates portfolio financial metrics in integer paise:
- **Total Revenue at Risk**: Sum of amounts for all failed/abandoned payments.
- **Eligible Revenue**: Revenue for payments $\le ₹50,000$ and non-`REPEATED_FAILURE`.
- **Projected Recoverable Revenue**: Sum of $(\text{amount\_paise} \times \text{recoverability\_score})$.

---

## API Endpoints (`backend/api/routes/intelligence.py`)

- `GET /api/intelligence/portfolio`: Returns total revenue at risk, eligible revenue, projected recoverable revenue, and sample size tier counts.
- `GET /api/intelligence/segments`: Returns canonical 4D segment profiles and sample size tier distribution.
- `GET /api/intelligence/strategies/compare`: Returns deterministic Wilson strategy rankings, winner, and rationale for a given failure context.
- `POST /api/intelligence/recoverability`: Computes transparent recoverability score and factor breakdown.
- `GET /api/intelligence/evidence-trace`: Returns step-by-step fallback trace for decision auditing.

---

## Verification & Testing Suite
All 101 unit and integration tests pass cleanly (`tests/test_recovery_intelligence.py`):
- Wilson mathematical accuracy against standard $95\%$ CI values.
- Case G small-sample trap protection ($40/150$ ranks above $1/1$).
- Tier boundary transitions ($0, 1, 9, 10, 30, 31, 100, 101$).
- Fallback hierarchy execution and step-by-step trace logging.
- Temporal cutoff filtering & holdout data isolation.
- Transparent recoverability factor attribution.
- API integration endpoints.
