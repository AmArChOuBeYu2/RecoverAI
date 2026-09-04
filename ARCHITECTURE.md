# ARCHITECTURE.md — RecoverAI

## System Overview
RecoverAI is an AI-powered revenue recovery optimization and execution system. It detects failed payments, segments them, scores recoverability, evaluates candidate recovery strategies using historical performance data, enforces deterministic safety policies, executes bounded interventions, verifies outcomes, attributes results back to strategies, and continuously improves recommendations.

Track: 03 — AI Revenue Recovery
Stack: Python 3.14 · FastAPI · SQLAlchemy (SQLite) · OpenAI + Gemini · Razorpay SDK

## Architecture Diagram
```ascii
                            +-------------------+
                            |  FAILED PAYMENT   |
                            +---------+---------+
                                      |
                                      v
                            +-------------------+
                            | Detection Engine  |
                            +---------+---------+
                                      |
                                      v
                            +-------------------+
                            |  Context Builder  |
                            +---------+---------+
                                      |
                                      v
                            +-------------------+
                            |Segmentation Engine|
                            +---------+---------+
                                      |
                                      v
                            +-------------------+
                            | Eligibility Check |
                            +---------+---------+
                                      |
                                      v
  +----------------------+  +-------------------+  +-----------------------+
  | Strategy Performance |->|  Strategy Engine  |<-|   AI Recommendation   |
  +----------------------+  +---------+---------+  +-----------------------+
            ^                         |
            |                         v
            |               +-------------------+
            |               |Policy/Safety Gate |
            |               +---------+---------+
            |                         |
            |                         v
            |               +-------------------+
            |               |  Action Executor  | (REAL or SIMULATED)
            |               +---------+---------+
            |                         |
            |                         v
            |               +-------------------+
            |               |    Verification   |
            |               +---------+---------+
            |                         |
            |                         v
            |               +-------------------+
            +---------------|Outcome Attribution|
                            +---------+---------+
                                      |
                                      v
                            +-------------------+
                            | Metrics & Audits  |
                            +-------------------+
```

## Core Principle: AI Recommends, Code Authorizes

```ascii
+-----------------------+          +-------------------------+          +------------------------+
|       AI LAYER        |          |      POLICY LAYER       |          |    EXECUTION LAYER     |
|  (Non-Deterministic)  |          |     (Deterministic)     |          |    (Deterministic)     |
|                       |          |                         |          |                        |
| 1. Analyze Context    |          | 1. Evaluate Rule 1..9   |          | 1. Create Payment Link |
| 2. Score Propensity   | ======>  | 2. Check Rate Limits    | ======>  | 2. Dispatch Email/SMS  |
| 3. Propose Strategy   | Proposal | 3. Enforce Safeguards   | Approved | 3. Call Razorpay API   |
| 4. Draft Content      |          | 4. Approve / Block      | Action   | 4. Record DB State     |
+-----------------------+          +-------------------------+          +------------------------+
```

## Project Structure
```text
Project 7 (Razor Pay)/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── errors.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── customer.py
│   │   ├── transaction.py
│   │   ├── segment.py
│   │   ├── recovery_case.py
│   │   ├── recovery_strategy.py
│   │   ├── strategy_outcome.py
│   │   ├── recovery_decision.py
│   │   ├── recovery_action.py
│   │   ├── policy_decision.py
│   │   ├── policy_simulation.py
│   │   ├── audit_event.py
│   │   ├── batch_run.py
│   │   └── llm_invocation.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── transaction_repo.py
│   │   ├── recovery_repo.py
│   │   ├── strategy_repo.py
│   │   └── audit_repo.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── detection.py
│   │   ├── segmentation.py          # NEW
│   │   ├── eligibility.py
│   │   ├── diagnosis.py
│   │   ├── strategy_engine.py       # NEW
│   │   ├── strategy_optimizer.py    # NEW
│   │   ├── policy_engine.py
│   │   ├── policy_simulator.py      # NEW
│   │   ├── executor.py
│   │   ├── verification.py
│   │   ├── outcome_attribution.py   # NEW
│   │   ├── metrics.py
│   │   ├── audit.py
│   │   └── orchestrator.py
│   ├── integrations/
│   │   ├── razorpay/
│   │   └── llm/
│   ├── api/
│   │   └── routes/
│   │       ├── dashboard.py
│   │       ├── recovery.py
│   │       ├── transactions.py
│   │       ├── segments.py          # NEW
│   │       ├── strategies.py        # NEW
│   │       ├── simulator.py         # NEW
│   │       ├── audit.py
│   │       ├── webhooks.py
│   │       └── health.py
│   └── seed/
│       └── generator.py
├── frontend/
├── tests/
└── docs/
```

## Database Schema

### Existing Tables
- `customers`
- `transactions`
- `recovery_cases` (Updated)
- `recovery_decisions` (Updated)
- `recovery_actions`
- `policy_decisions`
- `audit_events`
- `batch_runs`
- `llm_invocations`

### `segments`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | String unique | e.g. `auth_failure_card_mid_value` |
| failure_category | String | AUTHENTICATION_FAILURE, BANK_TIMEOUT, etc. |
| payment_method | String nullable | card, upi, netbanking, wallet, or null (any) |
| amount_range | String | LOW (<₹500), MID (₹500-₹5000), HIGH (₹5000-₹50000), PREMIUM (>₹50000) |
| customer_type | String nullable | NEW, RETURNING, FATIGUED, or null |
| description | Text | Human-readable segment description |
| created_at | DateTime | |

### `recovery_strategies`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| segment_id | UUID FK | Which segment this tracks |
| strategy_type | String | PAYMENT_LINK, RETRY, REMINDER, DELAYED_RETRY, METHOD_SWITCH, NO_ACTION, HUMAN_REVIEW |
| attempt_count | Integer default 0 | Total times this strategy was attempted for this segment |
| success_count | Integer default 0 | Times it resulted in verified recovery |
| total_recovered_paise | Integer default 0 | Total ₹ recovered |
| recovery_rate | Float nullable | success_count / attempt_count |
| avg_recovery_amount_paise | Float nullable | |
| sample_size_sufficient | Boolean default false | True when attempt_count >= minimum threshold (e.g. 10) |
| data_source | String | OBSERVED, SIMULATED, PROJECTED |
| confidence_level | String nullable | LOW, MEDIUM, HIGH based on sample size |
| created_at | DateTime | |
| updated_at | DateTime | |

### `strategy_outcomes`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| recovery_case_id | UUID FK | |
| recovery_strategy_id | UUID FK | |
| strategy_type | String | Which strategy was used |
| segment_id | UUID FK | Which segment |
| outcome | String | RECOVERED, NOT_RECOVERED, PENDING, EXPIRED |
| amount_recovered_paise | Integer nullable | |
| outcome_source | String | TEST_MODE_VERIFIED, SIMULATED, PROJECTED |
| attributed_at | DateTime nullable | When outcome was attributed |
| created_at | DateTime | |

### `policy_simulations`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| batch_run_id | UUID FK nullable | |
| policy_name | String | e.g. 'current_baseline', 'recoverai_optimized' |
| total_transactions | Integer | |
| revenue_at_risk_paise | Integer | |
| eligible_count | Integer | |
| eligible_revenue_paise | Integer | |
| projected_recovered_paise | Integer | |
| projected_recovery_rate | Float | |
| actions_projected | Integer | |
| policy_blocks_projected | Integer | |
| escalations_projected | Integer | |
| contacts_projected | Integer | |
| simulation_mode | String | SIMULATED or PROJECTED |
| created_at | DateTime | |

### Updated Existing Tables

**`recovery_cases`**
| Column | Type | Notes |
|---|---|---|
| segment_id | UUID FK nullable | Assigned segment |
| recoverability_score | Float nullable | 0.0-1.0 propensity score |

**`recovery_decisions`**
| Column | Type | Notes |
|---|---|---|
| strategy_evidence | JSON nullable | Historical performance data used in decision |
| competing_strategies | JSON nullable | Strategies considered with their scores |

## Recovery State Machine

```ascii
DETECTED 
   |
   v
ANALYZED 
   |
   v
SEGMENTED 
   |
   +---> INELIGIBLE (End)
   |
   v
ELIGIBLE 
   |
   v
STRATEGIES_EVALUATED 
   |
   +---> POLICY_BLOCKED (End)
   +---> ESCALATED (End)
   |
   v
POLICY_APPROVED 
   |
   v
ACTION_ATTEMPTED 
   |
   v
AWAITING_VERIFICATION 
   |
   +---> RECOVERED (End)
   +---> UNRECOVERED (End)
   +---> ESCALATED (End)
```
Invalid transitions: 
- `DETECTED` directly to `ACTION_ATTEMPTED`
- `POLICY_BLOCKED` to `ACTION_ATTEMPTED`

## Abandoned Checkout Detection

Razorpay does NOT provide a native `order.abandoned` webhook for standard checkout integrations.
(`order.abandoned` is available only for Razorpay Magic Checkout merchants, which is a separate product.)

RecoverAI infers checkout abandonment using the following mechanism:

**Method:** Server-side Orders API polling + elapsed-time threshold.

**Logic:**
```
Abandoned (no attempt):  order.status == "created" AND order.attempts == 0 AND age > ABANDONMENT_THRESHOLD
Abandoned (failed):      order.status == "attempted" AND order.amount_paid == 0 AND age > ABANDONMENT_THRESHOLD
```

**Data sources:**
- `GET /v1/orders` with `from`/`to` time filters (REAL — Razorpay API)
- `GET /v1/orders/:id/payments` to inspect failure reasons (REAL — Razorpay API)
- Elapsed time computed locally against `order.created_at`

**Limitations:**
- This is an **inferred condition**, not a native Razorpay event.
- The system cannot distinguish between "customer abandoned" and "customer is still deciding" — only elapsed time is used.
- Default `ABANDONMENT_THRESHOLD` is 30 minutes (configurable).
- False positives are possible for slow-deciding customers.
- In RecoverAI's synthetic data, abandoned checkouts are generated as orders with `status: created` and `attempts: 0`.

**Classification:** The abandonment detection mechanism is labeled `INFERRED` in audit events, not `VERIFIED`.

## Segmentation Engine
The Segmentation Engine groups transactions deterministically:
- Assigns each transaction to a segment based on: `failure_category` + `payment_method` + `amount_range` + `customer_type`
- Segments are pre-defined, deterministic (not AI-driven)
- Each segment has its own strategy performance history
- Example segments: `auth_failure_card_mid_value`, `gateway_timeout_upi_low_value`, `insufficient_funds_card_high_value`

## Strategy Engine
Strategy selection operates on a hybrid AI/observed data model with **small-sample protection**:

1. Retrieve historical strategy performance for this segment.
2. AI analyzes payment context and recommends a strategy.
3. **Apply small-sample protection** before comparing strategies.
4. Compare AI recommendation against observed performance data.
5. Select best strategy based on evidence quality.
6. Present competing strategies with performance comparison and evidence quality.

### Small-Sample Protection

Raw recovery rates on tiny samples are unreliable. A 1/1 = 100% rate must NOT beat a 50/200 = 25% rate automatically.

**Thresholds:**
| Sample Size | Confidence Level | Behavior |
|:---|:---|:---|
| < 10 attempts | `INSUFFICIENT` | Do not use this strategy's observed rate. Fall back to broader segment or AI recommendation. |
| 10–30 attempts | `LOW` | Use observed rate but flag uncertainty. Apply conservative lower-bound estimate. |
| 31–100 attempts | `MEDIUM` | Use observed rate. Weight against AI recommendation. |
| > 100 attempts | `HIGH` | Prefer observed rate over AI recommendation. |

**Conservative estimate:** When sample is small, use the Wilson score interval lower bound instead of raw `successes / attempts`. This penalizes small samples appropriately.

**Fallback chain when evidence is insufficient:**
1. Broader segment statistics (same `failure_category`, any `payment_method`/`amount_range`)
2. Global strategy statistics (across all segments)
3. Deterministic baseline strategy (PAYMENT_LINK for auth failures, RETRY for gateway errors)
4. HUMAN_REVIEW if all else fails

**Every recommendation exposes:**
- Strategy name
- Observed attempts and successes
- Raw recovery rate
- Conservative lower-bound estimate
- Confidence level
- Evidence source (OBSERVED / SIMULATED / INSUFFICIENT)
- Sample size relative to minimum threshold

**Example Comparison:**
```text
Segment: auth_failure_card_mid_value

Strategy       | Attempts | Successes | Raw Rate | Lower Bound | Confidence   | Evidence
PAYMENT_LINK   | 120      | 53        | 44.2%    | 35.6%       | HIGH         | OBSERVED
RETRY          | 80       | 14        | 17.5%    | 10.8%       | MEDIUM       | OBSERVED
REMINDER       | 60       | 14        | 23.3%    | 14.7%       | MEDIUM       | OBSERVED
DELAYED_RETRY  | 3        | 2         | 66.7%    | —           | INSUFFICIENT | OBSERVED

Selected: PAYMENT_LINK
Reason: Highest lower-bound recovery rate (35.6%) with HIGH confidence (120 attempts)
Note: DELAYED_RETRY excluded — sample size (3) below minimum threshold (10)
```

## Policy Simulator
The read-only Policy Simulator enables risk-free strategy evaluation:
- Takes a batch of transactions (scaling to 500+ records)
- Runs two policy configurations against same data
- Policy A: baseline (e.g. simple retry-once + generic reminder)
- Policy B: RecoverAI optimized (segment-aware strategy selection)
- Compares projected outcomes
- NEVER mutates any Razorpay data or real state
- All results labeled PROJECTED

## Outcome Attribution
Closed-loop feedback enables continuous improvement:
1. Recovery action is executed.
2. Verification checks outcome (via Razorpay API or simulated).
3. Outcome (RECOVERED/NOT_RECOVERED) is attributed to the specific strategy + segment combination.
4. `recovery_strategies` table is updated (`attempt_count++`, `success_count++` if recovered).
5. `recovery_rate` is recomputed.
6. Next time this segment is encountered, the updated performance data is available.
7. This creates a continuous improvement loop.

## LLM Provider Architecture
RecoverAI uses a cascading LLM approach for reliability:
1. **Primary**: OpenAI (GPT-4o) - Used for primary diagnosis, strategy generation, and drafting communications.
2. **Fallback**: Google Gemini (Pro) - Activated if OpenAI is rate-limited, times out, or fails.
3. **Safety Net**: Deterministic Fallback - If both LLMs fail, the system falls back to a hardcoded logic tree (e.g., standard generic retry for all failures).

All LLM calls are logged in the `llm_invocations` table for auditing and cost tracking.

## Policy Engine Rules
The Deterministic Policy Engine enforces 9 configurable safety rules. No action is executed unless all applicable rules pass.

| # | Rule | Parameter | Default |
|:---|:---|:---|:---|
| 1 | Max recovery attempts per transaction | `MAX_RECOVERY_ATTEMPTS` | 2 |
| 2 | Max contacts per customer per 24h | `MAX_CONTACTS_PER_DAY` | 3 |
| 3 | Cooldown between recovery attempts | `COOLDOWN_MINUTES` | 60 |
| 4 | Communication start hour (IST) | `CONTACT_START_HOUR` | 9 |
| 5 | Communication end hour (IST) | `CONTACT_END_HOUR` | 21 |
| 6 | Duplicate action prevention | — | Always enforced |
| 7 | Terminal state protection | — | Always enforced |
| 8 | High-value escalation threshold | `ESCALATION_THRESHOLD_PAISE` | 1000000 (₹10,000) |
| 9 | Transaction age limit | `MAX_TRANSACTION_AGE_HOURS` | 72 |

## API Endpoints

### Segments
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/segments` | List all segments with stats |
| GET | `/api/segments/{id}` | Segment detail with strategy performance |

### Strategies  
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/strategies` | Strategy performance across all segments |
| GET | `/api/strategies/segment/{segment_id}` | Strategies for a specific segment |
| GET | `/api/strategies/compare` | Side-by-side strategy comparison |

### Simulator
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/simulator/run` | Run policy simulation |
| GET | `/api/simulator/results` | Get simulation results |
| GET | `/api/simulator/compare` | Compare baseline vs optimized |

*(Other existing endpoints for Dashboard, Recovery, Transactions, Audit, Webhooks, and Health are retained)*

## Frontend Dashboard

```ascii
[ Sidebar ]  | [ Main Content ]
- Overview   | 
- Queue      |  Segment: auth_failure_card_mid_value
- Segments   |  +-------------------------------------------------+
- Strategies |  | Strategy     | Attempts | Rate  | Evidence      |
- Simulator  |  | PAYMENT_LINK | 120      | 44.2% | OBSERVED      |
- Audit      |  | RETRY        | 80       | 17.5% | OBSERVED      |
- Settings   |  +-------------------------------------------------+
```

Key Pages:
1. **Overview**: Dashboard with recovery metrics and strategy performance summary.
2. **Recovery Opportunities**: List of recoverable transactions grouped by segment.
3. **Segments**: Segment cards showing failure distribution + recoverability.
4. **Strategy Performance** *(HERO FEATURE)*: Strategy comparison table per segment.
5. **Policy Simulator**: Current baseline vs optimized side-by-side comparison.
6. **Recovery Queue**: Transactions pending action.
7. **Transaction Detail**: Full reasoning chain including strategy evidence.
8. **Audit Trail**: Immutable logs of all decisions and actions.
9. **Batch Evaluation**: Review outcomes for a 500+ record run.
10. **System Health**: Infrastructure, API limits, LLM latencies.

## Data Evidence Categories

RecoverAI classifies every data point into exactly one of four evidence categories. These categories are never mixed in the same metric without explicit labeling.

| Category | Definition | Example |
|:---|:---|:---|
| **OBSERVED** | An actual recorded outcome from a prior batch run or available dataset. | Strategy recovered 53/120 attempts = 44.2% rate from previous runs. |
| **VERIFIED** | An outcome explicitly confirmed by Razorpay Test Mode through authoritative API or webhook evidence. | Payment Link `plink_test_xyz` confirmed `paid` via `payment_link.paid` webhook or `GET /v1/payment_links/:id` returning `status: paid`. |
| **SIMULATED** | A synthetic experiment or batch result generated locally. Not confirmed by any external authority. | Synthetic conversion rate of 45% applied to 80 authentication-failure transactions. |
| **PROJECTED** | An estimate or model output derived from observed evidence or simulation. | Policy simulator estimates ₹4.2L incremental recovery based on observed segment performance rates. |

**Critical distinctions:**
- Payment Link **creation** is not recovery. It is an ACTION.
- A successful Payment Link **payment confirmed by Razorpay** is VERIFIED.
- Synthetic conversion results applied locally are SIMULATED.
- Optimizer estimates based on observed or simulated data are PROJECTED.
- Strategy performance backed by actual run outcomes is OBSERVED.

Every metric in the UI, audit trail, and API response carries its evidence category.

## Honest Metrics Reporting

The dashboard tracks the following metrics, each tagged with its evidence category:

| Metric | Evidence Category | Definition |
|:---|:---|:---|
| Revenue At Risk | — | Total value of failed/abandoned payments in the batch. |
| Eligible Revenue | — | Value of payments that pass eligibility checks. |
| Recovery Attempts | — | Count of actions executed (broken down by VERIFIED vs SIMULATED). |
| Verified Recovered | **VERIFIED** | Revenue confirmed recovered via Razorpay Test Mode API/webhook. |
| Simulated Recovered | **SIMULATED** | Revenue assumed recovered using synthetic conversion rates. |
| Projected Recovery | **PROJECTED** | Revenue estimated recoverable by the policy simulator or optimizer. |
| Observed Recovery Rate | **OBSERVED** | Strategy success rate computed from prior batch outcomes. |
| Incremental Recovery | **PROJECTED** | (RecoverAI optimized) − (baseline policy) projected recovery. |
| Unrecovered Revenue | — | Breakdown by reason: policy blocked, ineligible, action failed, escalated, AI unavailable. |

No metric combines VERIFIED and SIMULATED values without explicit labeling.

---

## Ingestion & System Architecture Invariants (Milestone 5)

RecoverAI enforces six production-grade engineering invariants across ingestion, state management, transaction integrity, and causal attribution:

### 1. Ingestion Flow Architecture
```ascii
Raw Request Body -> HMAC SHA-256 Signature Verification -> DB-Enforced Event Idempotency -> Atomic Transaction Router -> Domain Recovery Service -> State Machine Transition -> Strategy Outcome & Audit Trail
```

### 2. Database-Enforced Webhook Idempotency
- Webhook idempotency is **database-enforced** via a unique constraint on `AuditEvent.event_id`.
- Application check-then-insert race conditions are strictly prevented. When concurrent duplicate webhook deliveries arrive, database-level unique constraint enforcement catches the duplicate `event_id`, rolls back the duplicate transaction, and returns `{"status": "duplicate", "processed": false}`.

### 3. Transactional Atomicity & Rollback
- Every webhook ingestion and domain update operates inside an explicit database transaction boundary.
- If domain processing fails at any point, the entire transaction (including audit event logs and transaction models) is completely **rolled back**. No event is marked as processed if the underlying domain update failed.

### 4. Centrally Enforced State Machine Invariants
- `RecoveryCase` state transitions are strictly governed by `StateMachineService`. Direct status field mutations outside the service are forbidden.
- Invalid state transitions (e.g. `DETECTED` $\rightarrow$ `RECOVERED`) fail safely: an `InvalidStateTransitionError` is raised, `case.status` remains completely unchanged, and an immutable `INVALID_STATE_TRANSITION_BLOCKED` audit event is recorded.
- Terminal states (`RECOVERED`, `UNRECOVERED`, `INELIGIBLE`, `POLICY_BLOCKED`, `ESCALATED`) are strictly immutable.

### 5. Causal Recovery Attribution Invariant
- RecoverAI credits revenue **only** when a valid causal chain exists:
  $$\text{Failed Payment / Recovery Case} \longrightarrow \text{RecoverAI Action} \longrightarrow \text{Razorpay Payment Outcome} \longrightarrow \text{Verification} \longrightarrow \text{Attribution}$$
- Successful payments received via Razorpay webhook that have **no matching RecoverAI action** are marked `unattributed` and **MUST NOT** be credited as RecoverAI revenue or update strategy stats.
- Already-recovered cases reject duplicate attribution.

### 6. Security & Credential Protection
- `sanitize_payload` recursively redacts sensitive payment credentials (`card_number`, `cvv`, `password`, `secret`, `token`, `auth_code`) before persistence or logging.
- Raw webhook payloads storing cardholder data are sanitized prior to audit storage.
- Credentials and secrets never appear in API responses, logs, or error tracebacks.

