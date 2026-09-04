# IMPLEMENTATION_PLAN.md — RecoverAI

## Product
RecoverAI — AI-powered revenue recovery optimization and execution system.

## Core Question
"Which recovery intervention is most likely to recover this revenue, for this type of customer/payment, under these constraints, and what evidence do we have that this strategy actually works?"

---

## Milestones

### Milestone 1: Research + Architecture ✅
- [x] Repository inspection
- [x] Razorpay documentation research
- [x] Capability verification (REAL/SIMULATED/PROJECTED/UNAVAILABLE)
- [x] Architecture design
- [x] Database schema design
- [x] Decision log
- [x] Competitive differentiation

### Milestone 2: Repository + Environment
- [ ] `.gitignore`
- [ ] `.env.example` with all required variables
- [ ] `requirements.txt` with pinned dependencies
- [ ] Install missing packages (`razorpay`, `openai`, `python-dotenv`)
- [ ] `run.py` CLI entry point (seed / recover / simulate / report)
- [ ] Verify environment works

### Milestone 3: Database + Models
- [ ] SQLAlchemy engine + session factory (`backend/models/base.py`)
- [ ] `Customer` model
- [ ] `Transaction` model (mirrors Razorpay payment object + `data_source` field)
- [ ] `Segment` model
- [ ] `RecoveryCase` model (with state machine, segment_id, recoverability_score)
- [ ] `RecoveryStrategy` model (per-segment strategy performance tracking)
- [ ] `StrategyOutcome` model (individual outcome attribution)
- [ ] `RecoveryDecision` model (AI diagnosis + strategy evidence + competing strategies)
- [ ] `RecoveryAction` model (with `execution_mode`: REAL/SIMULATED)
- [ ] `PolicyDecision` model
- [ ] `PolicySimulation` model
- [ ] `AuditEvent` model
- [ ] `BatchRun` model
- [ ] `LLMInvocation` model
- [ ] Table creation on startup
- [ ] Repository layer (`transaction_repo.py`, `recovery_repo.py`, `strategy_repo.py`, `audit_repo.py`)

### Milestone 4: Razorpay Integration Layer
- [ ] SDK client initialization with timeout + retry (`backend/integrations/razorpay/client.py`)
- [ ] Payment fetch operations (`payments.py`)
- [ ] Order operations (`orders.py`)
- [ ] Payment Link CRUD (`payment_links.py`) — create, fetch, cancel
- [ ] Webhook signature verification (`webhooks.py`)
- [ ] Razorpay-specific exceptions (`exceptions.py`)
- [ ] Response schemas (`schemas.py`)
- [ ] All external calls: timeout handling, error normalization, safe logging (no secrets)

### Milestone 5: Ingestion + Webhooks
- [ ] Webhook receiver endpoint (`POST /api/webhooks/razorpay`)
- [ ] Signature verification middleware
- [ ] `payment.failed` event handler
- [ ] `payment_link.paid` event handler
- [ ] `payment_link.expired` event handler
- [ ] Idempotency enforcement (deduplicate by event ID)
- [ ] Audit logging for all webhook events

### Milestone 6: Recovery Case Model + State Machine
- [ ] State machine implementation with valid transitions
- [ ] States: `DETECTED → ANALYZED → SEGMENTED → ELIGIBLE/INELIGIBLE → STRATEGIES_EVALUATED → POLICY_APPROVED/POLICY_BLOCKED/ESCALATED → ACTION_ATTEMPTED → AWAITING_VERIFICATION → RECOVERED/UNRECOVERED/ESCALATED`
- [ ] Invalid transition prevention (raise `InvalidStateTransitionError`)
- [ ] Terminal state protection (RECOVERED, INELIGIBLE, ESCALATED)
- [ ] Duplicate prevention (no re-processing of terminal cases)

### Milestone 7: Deterministic Policy Engine
- [ ] `PolicyEngine` class with configurable rules from env
- [ ] Rule 1: Max recovery attempts per transaction (default: 2)
- [ ] Rule 2: Max contacts per customer per 24h (default: 3)
- [ ] Rule 3: Cooldown between recovery attempts (default: 60 min)
- [ ] Rule 4: Communication start hour (default: 9 AM IST)
- [ ] Rule 5: Communication end hour (default: 9 PM IST)
- [ ] Rule 6: Duplicate action prevention
- [ ] Rule 7: Terminal state protection
- [ ] Rule 8: High-value escalation threshold (default: ₹10,000)
- [ ] Rule 9: Transaction age limit (default: 72h)
- [ ] Each rule returns `PolicyRuleResult` (rule_name, passed, reason)
- [ ] Aggregate `PolicyDecision` (APPROVE/DENY/ESCALATE + blocking rule)
- [ ] All policy evaluations logged to audit trail

### Milestone 8: Synthetic Data Generator (500+ records)
- [ ] Customer generator: realistic Indian names, emails, phone numbers
- [ ] Transaction generator with controlled failure distribution:
  - 35% customer errors (OTP, insufficient funds, cancelled, card expired)
  - 25% gateway errors (timeout, downtime, network failure)
  - 15% checkout abandonment (order created, no payment attempt)
  - 10% business errors (config, amount limits)
  - 10% repeated failures (same customer, 3+ attempts)
  - 5% ambiguous / edge cases (missing metadata, unknown errors)
- [ ] Amount distribution: 30% LOW, 35% MID, 25% HIGH, 10% PREMIUM
- [ ] Payment method distribution: 40% card, 30% UPI, 20% netbanking, 10% wallet
- [ ] Customer type distribution: 40% NEW, 40% RETURNING, 20% FATIGUED
- [ ] Deterministic seeding (same seed → same data)
- [ ] Include deliberate edge cases:
  - Already-recovered transactions
  - Transactions outside contact window
  - Customers at retry limit
  - High-value escalation candidates
  - AI failure simulation candidates

### Milestone 9: Segmentation Engine
- [ ] Segmentation service (`backend/services/segmentation.py`)
- [ ] Pre-defined segment definitions based on:
  - failure_category (7 categories)
  - payment_method (4 methods)
  - amount_range (4 ranges)
  - customer_type (3 types)
- [ ] Segment assignment: deterministic, reproducible
- [ ] Segment initialization in database
- [ ] Auto-create segments on first encounter if not pre-existing

### Milestone 10: Detection + Eligibility
- [ ] Detection engine: load batch, identify failed/abandoned
- [ ] Context builder: assemble payment details + customer history + prior recoveries
- [ ] Eligibility checker (deterministic):
  - Transaction age < 72 hours
  - Not already recovered
  - Not a duplicate recovery case
  - Amount > 0
  - Has customer contact info
  - Not in terminal state
- [ ] Eligibility reason recorded in recovery case

### Milestone 11: LLM Provider Abstraction
- [ ] `LLMProvider` abstract base with `diagnose()` and `recommend_strategy()` methods
- [ ] `OpenAIProvider` — structured output, Pydantic validation
- [ ] `GeminiProvider` — structured output, Pydantic validation
- [ ] `DeterministicFallback` — error_reason → strategy mapping (no AI)
- [ ] `LLMRouter` — try OpenAI → validate → Gemini fallback → validate → deterministic
- [ ] `RecoveryDiagnosis` Pydantic schema:
  - `failure_category` (strict enum)
  - `diagnosis` (string)
  - `recoverability_score` (0.0–1.0)
  - `confidence` (0.0–1.0)
  - `recommended_strategy` (strict enum)
  - `reasoning_summary` (string)
- [ ] `LLMInvocation` logging (provider, model, latency, success, fallback)
- [ ] `SIMULATE_OPENAI_FAILURE` env var for demo
- [ ] Prompt design: include payment context, failure details, customer history, segment

### Milestone 12: AI Diagnosis + Strategy Engine
- [ ] Diagnosis service: AI-powered root cause analysis
- [ ] Abandoned checkout detection: poll `GET /v1/orders` where `status=created` & `attempts=0` & `created_at > 15m` (log as inferred condition)
- [ ] Strategy Engine:
  1. Retrieve historical strategy performance for this segment
  2. Get AI recommendation
  3. Calculate Wilson score interval lower bound (95% confidence) for candidate strategies
  4. Compare AI recommendation against sample-size protected observed data
  5. Apply fallback hierarchy if sample size < 10 attempts: broader segment → baseline → human review
  6. Present competing strategies with evidence source, sample size, and confidence level
  7. Select best strategy based on sample-protected evidence + AI
- [ ] `strategy_evidence` field in decision: what data backed the recommendation
- [ ] `competing_strategies` field: alternatives considered with lower bound scores and confidence levels

### Milestone 13: Strategy Optimizer
- [ ] Strategy performance retrieval per segment with data source categorization (OBSERVED / SIMULATED / INSUFFICIENT)
- [ ] Evidence-based recommendation: prefer observed data (with sample size protection) over AI opinion
- [ ] Confidence levels: INSUFFICIENT (<10 attempts), LOW (10–30), MEDIUM (31–100), HIGH (>100)
- [ ] Strategy comparison output for UI displaying observed rate, lower bound, sample size, and evidence source

### Milestone 14: Action Executor
- [ ] Executor service with action routing
- [ ] `PAYMENT_LINK` action:
  - REAL mode: create via Razorpay API (up to 5–10 showcase links)
  - SIMULATED mode: create local record with SIM label
  - Mode selection based on `MAX_REAL_PAYMENT_LINKS` config
- [ ] `ESCALATION` action: create escalation record
- [ ] `NO_ACTION` action: log with reason
- [ ] `REMINDER` action: simulated notification
- [ ] `DELAYED_RETRY` action: schedule for later (simulated in demo)
- [ ] `HUMAN_REVIEW` action: flag for review
- [ ] Every action records `execution_mode` (REAL_TEST_MODE / SIMULATED)
- [ ] Every action records `notification_mode` (SIMULATED / RAZORPAY_TEST)

### Milestone 15: Verification + Outcome Attribution
- [ ] Explicit Evidence Categorization:
  - Payment Link creation is an action, NOT recovery
  - Razorpay Test Mode API/webhook confirmed payment = `VERIFIED`
  - Synthetic experiment / batch conversion result = `SIMULATED`
  - Strategy engine / policy simulator estimates = `PROJECTED`
  - Historical prior batch run results = `OBSERVED`
- [ ] Verification service:
  - REAL actions: fetch payment link status via Razorpay API (VERIFIED)
  - SIMULATED actions: apply segment-specific conversion rates (SIMULATED)
- [ ] Outcome attribution service:
  1. Determine outcome (RECOVERED / NOT_RECOVERED)
  2. Create `StrategyOutcome` record with explicit `outcome_source` (VERIFIED / SIMULATED / PROJECTED)
  3. Update `RecoveryStrategy` metrics (attempt_count, success_count, recovery_rate) as OBSERVED data for future runs
  4. Transition recovery case to terminal state
- [ ] Simulated conversion rates by failure category:
  - Authentication failures: ~45% recovery
  - Gateway errors: ~65% recovery
  - Insufficient funds: ~15% recovery
  - Checkout abandonment: ~30% recovery
  - Repeated failures: ~10% recovery
  - Business errors: ~5% recovery (mostly config fixes, not customer recovery)

### Milestone 16: Policy Simulator
- [ ] Simulator service (`backend/services/policy_simulator.py`)
- [ ] Read-only: NEVER writes to Razorpay or mutates real state
- [ ] Two policy configurations:
  - Baseline: retry once + generic reminder for all failures
  - RecoverAI: segment-aware strategy selection with evidence-based optimization
- [ ] Run both against same transaction batch
- [ ] Compare: revenue at risk, eligible, projected recovered, actions, blocks, escalations, contacts
- [ ] All results labeled `PROJECTED`
- [ ] Store in `PolicySimulation` model

### Milestone 17: Orchestrator (Main Agent Loop)
- [ ] Orchestrator ties all services together:
  1. Load transactions (from seed or API)
  2. Create recovery cases
  3. For each: detect → segment → eligibility → diagnose → strategy → policy → execute → verify → attribute
  4. Handle errors at each step without crashing the batch
  5. Compute batch metrics
  6. Return batch summary
- [ ] Batch run tracking (`BatchRun` model)
- [ ] Idempotency: re-running skips terminal cases
- [ ] Bounded concurrency (correctness first)
- [ ] Progress reporting

### Milestone 18: Metrics Service
- [ ] Compute from batch run:
  - total_transaction_count, total_transaction_value
  - total_revenue_at_risk, eligible_transaction_count, eligible_revenue
  - ai_decision_count, policy_approved_count, policy_blocked_count, escalation_count
  - actions_attempted (real + simulated breakdown)
  - verified_recovered, simulated_recovered, projected_recovery
  - incremental_recovery (RecoverAI vs baseline)
  - unrecovered_amount with breakdown by reason
  - recovery_rate, action_success_rate
  - duplicate_actions_prevented
  - ai_failure_rate, provider_fallback_rate, razorpay_api_failure_rate
- [ ] Strategy performance table per segment
- [ ] Failure analysis breakdown (why not recovered)

### Milestone 19: Audit Trail
- [ ] AuditEvent creation at every material step
- [ ] Event types: DETECTED, SEGMENTED, ELIGIBILITY_CHECKED, AI_DIAGNOSIS, STRATEGY_EVALUATED, STRATEGY_SELECTED, POLICY_EVALUATED, ACTION_EXECUTED, VERIFICATION_CHECKED, OUTCOME_ATTRIBUTED, RECOVERY_RESULT, ERROR, FALLBACK_USED, WEBHOOK_RECEIVED
- [ ] Actor tracking: system, ai:openai, ai:gemini, ai:deterministic, policy, razorpay, simulator
- [ ] Correlation IDs (recovery_case_id, batch_run_id)

### Milestone 20: API Routes
- [ ] Health check: `GET /api/health` (Razorpay, OpenAI, Gemini, DB status)
- [ ] Dashboard: `GET /api/dashboard/summary`, `GET /api/dashboard/failure-breakdown`
- [ ] Transactions: `GET /api/transactions`, `GET /api/transactions/{id}`
- [ ] Recovery: `POST /api/recovery/seed`, `POST /api/recovery/run`, `GET /api/recovery/cases`, `GET /api/recovery/cases/{id}`
- [ ] Segments: `GET /api/segments`, `GET /api/segments/{id}`
- [ ] Strategies: `GET /api/strategies`, `GET /api/strategies/segment/{id}`, `GET /api/strategies/compare`
- [ ] Simulator: `POST /api/simulator/run`, `GET /api/simulator/results`, `GET /api/simulator/compare`
- [ ] Audit: `GET /api/audit/events`, `GET /api/audit/events/{recovery_case_id}`
- [ ] Batch: `GET /api/batch/runs`, `GET /api/batch/runs/{id}`
- [ ] Webhooks: `POST /api/webhooks/razorpay`
- [ ] CORS middleware
- [ ] Error handling middleware

### Milestone 21: Frontend Dashboard
- [ ] HTML structure with semantic markup
- [ ] CSS: dark theme, fintech-style, clean card layouts
- [ ] Page 1 — Overview: KPI cards (Revenue At Risk, Recovered, Rate, Incremental), pipeline breakdown
- [ ] Page 2 — Recovery Opportunities: recoverable transactions by segment
- [ ] Page 3 — Segments: segment cards with failure distribution + recoverability
- [ ] Page 4 — Strategy Performance (HERO): strategy comparison table per segment with evidence
- [ ] Page 5 — Policy Simulator: baseline vs RecoverAI side-by-side comparison
- [ ] Page 6 — Recovery Queue: transactions pending action
- [ ] Page 7 — Transaction Detail: full reasoning chain (diagnosis → evidence → policy → action → outcome)
- [ ] Page 8 — Audit Trail: timeline view with filtering
- [ ] Page 9 — Batch Evaluation: batch run metrics
- [ ] Page 10 — System Health: service connectivity indicators
- [ ] Controls: Seed Data, Run Recovery, Run Simulator
- [ ] Responsive design

### Milestone 22: Testing
- [ ] Unit tests: eligibility, policy engine, state machine, metrics, AI schema validation, segmentation
- [ ] Integration tests: Razorpay client, payment link creation, webhook validation
- [ ] AI tests: valid response, malformed response, timeout, fallback chain, deterministic fallback
- [ ] Strategy tests: performance tracking, outcome attribution, confidence levels
- [ ] Simulator tests: read-only verification, projected metric calculation
- [ ] Batch tests: 500+ processing, mixed scenarios, metric integrity

### Milestone 23: Demo Hardening
- [ ] End-to-end dry run with 500+ records
- [ ] Verify REAL vs SIMULATED vs PROJECTED labels are correct everywhere
- [ ] Verify strategy performance numbers make statistical sense
- [ ] Verify policy simulator shows credible incremental recovery
- [ ] Fix edge cases
- [ ] Clean console output
- [ ] Create DEMO.md with 5-minute script

### Milestone 24: Documentation + Deployment
- [ ] README.md (problem, solution, architecture, setup, run, demo, limitations)
- [ ] ARCHITECTURE.md (finalize)
- [ ] DECISIONS.md (finalize)
- [ ] COMPETITIVE-DIFFERENTIATION.md (finalize)
- [ ] EVALUATION.md (batch evaluation methodology)
- [ ] API.md (endpoint reference)
- [ ] DEMO.md (5-minute demo script)
- [ ] Final git commit with meaningful history

---

## Environment Variables

```env
# Razorpay (Test Mode)
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash

# Application
DATABASE_URL=sqlite:///./recoverai.db
MAX_RECOVERY_ATTEMPTS=2
MAX_CONTACTS_PER_DAY=3
COOLDOWN_MINUTES=60
CONTACT_START_HOUR=9
CONTACT_END_HOUR=21
ESCALATION_THRESHOLD_PAISE=1000000
MAX_TRANSACTION_AGE_HOURS=72
MAX_REAL_PAYMENT_LINKS=10
SEED_RECORD_COUNT=500
MIN_STRATEGY_SAMPLE_SIZE=10

# Development
SIMULATE_OPENAI_FAILURE=false
DEBUG=true
```

---

## Dependencies

```
fastapi>=0.141.0
uvicorn>=0.52.0
sqlalchemy>=2.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
razorpay>=1.4.0
openai>=1.0.0
google-genai>=1.0.0
httpx>=0.28.0
tenacity>=8.0.0
python-dotenv>=1.0.0
```

---

## Risk Register

| Risk | Impact | Mitigation |
|:---|:---|:---|
| 30 Payment Link cap in Test Mode | Cannot create 500+ real links | Hybrid model: 5-10 real, rest simulated |
| OpenAI rate limit during demo | AI diagnosis fails mid-batch | Gemini fallback + deterministic fallback |
| Razorpay API downtime | External calls fail | Graceful error handling, simulated mode |
| LLM produces invalid output | Schema validation fails | Pydantic validation + reject + fallback |
| SQLite concurrent write issues | Data corruption | Single-threaded batch processing |
| Python 3.14 compatibility | Package issues | Test early, pin versions |
| Insufficient sample size per segment | Strategy performance stats unreliable | Flag low-confidence recommendations, fall back to AI |
| Policy simulator shows unrealistic results | Credibility loss | Use conservative conversion rate estimates, label PROJECTED |
| Seed data distribution doesn't match real patterns | Demo feels synthetic | Research real payment failure distributions, use realistic proportions |
