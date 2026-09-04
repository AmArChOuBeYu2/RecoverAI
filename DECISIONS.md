# DECISIONS.md — RecoverAI Technical Decision Log

## Razorpay Capability Verification

Every capability relevant to the recovery agent, verified against official Razorpay documentation.

Classification:
- **REAL**: Confirmed in official docs, works in Test Mode
- **SIMULATED**: Local mock required because Test Mode doesn't execute it
- **PROJECTED**: Statistical/model-based expected outcome, not observed
- **UNAVAILABLE**: Not supported by Razorpay

---

### A. Payments API

| Capability | Endpoint / Mechanism | Test Mode? | Our Usage | Limitations | Classification |
|:---|:---|:---|:---|:---|:---|
| Fetch payment by ID | `GET /v1/payments/:id` | Yes | Fetch failure details for diagnosis | — | **REAL** |
| Fetch all payments | `GET /v1/payments` | Yes | Batch fetch with time range | Max 100 per request, no server-side status filter | **REAL** |
| Payment error fields | `error_code`, `error_description`, `error_source`, `error_step`, `error_reason` | Yes | AI diagnosis + segmentation input | Only populated on failed payments | **REAL** |
| Filter by status via API | Not supported | N/A | Must filter client-side after fetch | No `status` query param | **SIMULATED** |
| Fetch payments for order | `GET /v1/orders/:id/payments` | Yes | See all attempts for an order | — | **REAL** |

### B. Orders API

| Capability | Endpoint / Mechanism | Test Mode? | Our Usage | Limitations | Classification |
|:---|:---|:---|:---|:---|:---|
| Create order | `POST /v1/orders` | Yes | Create test orders for demo | — | **REAL** |
| Fetch order | `GET /v1/orders/:id` | Yes | Check order state | — | **REAL** |
| Detect abandoned orders | `status=created, attempts=0` | Yes | Identify checkout abandonment | Must poll or use time-based query | **REAL** |
| Order status lifecycle | `created → attempted → paid` | Yes | State tracking | — | **REAL** |

### C. Payment Links API

| Capability | Endpoint / Mechanism | Test Mode? | Our Usage | Limitations | Classification |
|:---|:---|:---|:---|:---|:---|
| Create payment link | `POST /v1/payment_links` | Yes | Recovery action: send customer a link | **30 link cap in Test Mode** | **REAL** |
| Fetch payment link | `GET /v1/payment_links/:id` | Yes | Verify link status | — | **REAL** |
| Cancel payment link | `POST /v1/payment_links/:id/cancel` | Yes | Cancel expired recovery links | Only on `created`/`partially_paid` | **REAL** |
| SMS/email notification | `notify.sms`, `notify.email` params | Accepted but not sent | Log as simulated notification | **No real SMS/email in Test Mode** | **SIMULATED** |
| Reminder delivery | `reminder_enable` param | Accepted but not sent | Log as simulated | Not transmitted in Test Mode | **SIMULATED** |
| Link expiration | `expire_by` Unix timestamp | Yes | Auto-expire recovery links | Max 6 months from creation | **REAL** |
| Reference ID tracking | `reference_id` field | Yes | Map to original order/recovery case | Max 40 chars | **REAL** |
| Notes metadata | `notes` field | Yes | Attach recovery context | Max 15 pairs, 256 chars/value | **REAL** |
| Programmatic payment | No API endpoint exists | N/A | Cannot mark link as paid via API | Must use checkout UI + mock bank | **UNAVAILABLE** |

### D. Webhooks

| Capability | Endpoint / Mechanism | Test Mode? | Our Usage | Limitations | Classification |
|:---|:---|:---|:---|:---|:---|
| `payment.failed` event | Webhook subscription | Yes | Trigger recovery on failure | Requires public URL (ngrok) | **REAL** |
| `payment.captured` event | Webhook subscription | Yes | Verify successful payment | — | **REAL** |
| `payment_link.paid` event | Webhook subscription | Yes | Verify recovery success | — | **REAL** |
| `payment_link.expired` event | Webhook subscription | Yes | Handle expired recovery links | — | **REAL** |
| `order.paid` event | Webhook subscription | Yes | Order-level completion | — | **REAL** |
| Signature verification | HMAC-SHA256, `X-Razorpay-Signature` | Yes | Validate webhook authenticity | Must use raw request body | **REAL** |
| Delivery to localhost | Direct localhost URL | No | Rejected by Razorpay Dashboard | Must use ngrok or similar tunnel | **UNAVAILABLE** |
| Delivery retries | Exponential backoff, 24h window | Yes | Automatic retry on failure | Auto-disabled after 24h failures | **REAL** |

### E. Test Mode Behavior

| Capability | Behavior | Classification |
|:---|:---|:---|
| Test API keys | `rzp_test_` prefix, full API access | **REAL** |
| Simulating card failure | Mock bank page: Success/Failure buttons | **REAL** |
| Simulating UPI failure | `failure@razorpay` VPA | **REAL** |
| Test card numbers | Visa: `4111111111111111`, MC: `5104015555555558` | **REAL** |
| OTP simulation | `1234`/`123456` = success, other = failure | **REAL** |
| API rate limits | ~100 req/min (same as live) | **REAL** |
| Payment Link cap | **30 links per Test Mode account** | **REAL** |

---

## Architectural Decisions

### DEC-001: Hybrid Batch Model

**Decision:** Use a hybrid approach for the 500+ transaction batch.

**Rationale:** Razorpay Test Mode caps Payment Link creation at 30 links. We cannot create 500+ real links.

**Approach:**
- Process all 500+ transactions through the full pipeline (detect → segment → diagnose → strategize → policy → act → verify → attribute)
- For **5–10 showcase transactions**: execute REAL Razorpay API calls (create actual payment links in Test Mode)
- For **remaining transactions**: execute SIMULATED actions with clear labeling
- UI and audit trail distinguish `TEST_MODE_VERIFIED`, `SIMULATED`, and `PROJECTED` at every point

---

### DEC-002: Synthetic Data Strategy

**Decision:** Generate synthetic failed payment data locally rather than creating real failures via Razorpay.

**Rationale:** Razorpay Test Mode cannot programmatically create failed payments. Failures require browser interaction with the mock bank page. Generating 500+ real failures manually is impractical.

**Approach:**
- Generate payment objects that exactly mirror Razorpay's payment schema
- Include all 5 error fields
- Cover diverse failure categories with realistic distributions
- Mark all synthetic data as `source: SYNTHETIC` in the database
- Include sufficient volume per segment for statistically meaningful strategy performance metrics

---

### DEC-003: LLM Provider Architecture

**Decision:** Build a provider abstraction with OpenAI primary, Gemini fallback, deterministic safe fallback.

**Rationale:** Financial operations cannot fail silently because an AI provider is down.

**Chain:** OpenAI → Gemini → Deterministic rule-based fallback

---

### DEC-004: AI Recommends, Code Authorizes

**Decision:** LLM output is always a recommendation. The PolicyEngine makes the final authorization decision using deterministic rules.

**Rationale:** LLMs can hallucinate, produce inconsistent outputs, or be manipulated. Financial actions require deterministic safety guarantees.

**Implementation:**
- AI produces `RecoveryDiagnosis` (structured, Pydantic-validated)
- Strategy Engine compares AI recommendation against observed performance data
- PolicyEngine evaluates against deterministic rules
- Executor only acts on `APPROVE`
- No code path from AI → Razorpay API without passing through PolicyEngine

---

### DEC-005: Recovery State Machine

**Decision:** Use an explicit finite state machine with SEGMENTED state for recovery cases.

**States:** `DETECTED → ANALYZED → SEGMENTED → ELIGIBLE/INELIGIBLE → STRATEGIES_EVALUATED → POLICY_APPROVED/POLICY_BLOCKED/ESCALATED → ACTION_ATTEMPTED → AWAITING_VERIFICATION → RECOVERED/UNRECOVERED/ESCALATED`

**Rules:**
- Terminal states (`RECOVERED`, `INELIGIBLE`, `ESCALATED`) allow no further transitions
- `POLICY_BLOCKED` cannot transition to `ACTION_ATTEMPTED`
- Duplicate batch runs skip transactions already in terminal states

---

### DEC-006: Notification Handling

**Decision:** Build a notification adapter interface with a simulated implementation.

**Rationale:** Razorpay does not deliver real SMS/email in Test Mode. We must not claim "SMS sent" when it wasn't.

---

### DEC-007: Database Choice

**Decision:** SQLite with SQLAlchemy ORM, repository pattern abstraction.

**Rationale:** Zero-dependency local database for buildathon demo. Repository abstraction enables PostgreSQL migration.

---

### DEC-008: No Virtual Environment

**Decision:** Use global Python 3.14.3 installation.

**Rationale:** User has a global Python setup. Install missing packages (`razorpay`, `openai`, `python-dotenv`) globally.

---

### DEC-009: Webhook Strategy for Demo

**Decision:** Implement webhook endpoints but do not require ngrok for the core demo flow.

**Rationale:** Requiring ngrok adds setup friction for judges. The primary demo uses the batch processing flow. Webhook endpoints exist for production use.

---

### DEC-010: Honest Metrics

**Decision:** Never count "payment link created" as "revenue recovered."

**Implementation:**
- `recovered_amount` includes ONLY verified outcomes
- `simulated_recovered` is clearly separated
- `projected_recovery` is labeled as PROJECTED
- All three are displayed distinctly in the UI

---

### DEC-011: Portfolio-Level Strategy Intelligence (NEW)

**Decision:** Track strategy performance per segment using observed outcomes, not just AI opinions.

**Rationale:** This is RecoverAI's core differentiator vs case-level recovery systems. A strategy recommendation backed by "44.2% success rate over 120 observed attempts" is more credible than "AI recommends this with 0.91 confidence."

**Approach:**
- `recovery_strategies` table tracks attempt_count, success_count, recovery_rate per (segment, strategy) pair
- Strategy Engine retrieves historical performance before making recommendations
- AI recommendation is one input; observed data is the primary input when sample size is sufficient
- Every recommendation exposes supporting evidence, sample size, and confidence level

---

### DEC-012: Payment Segmentation Model (NEW)

**Decision:** Segment transactions deterministically based on observable payment attributes.

**Segmentation dimensions:**
- `failure_category`: AUTHENTICATION_FAILURE, BANK_TIMEOUT, NETWORK_FAILURE, INSUFFICIENT_FUNDS, CHECKOUT_ABANDONMENT, REPEATED_FAILURE, UNKNOWN
- `payment_method`: card, upi, netbanking, wallet
- `amount_range`: LOW (<₹500), MID (₹500–₹5,000), HIGH (₹5,000–₹50,000), PREMIUM (>₹50,000)
- `customer_type`: NEW (first transaction), RETURNING (prior success), FATIGUED (3+ recent failures)

**Rationale:** Segmentation is deterministic (not AI-driven) because it defines the population for strategy performance tracking. AI-driven segmentation would make performance metrics unreproducible.

---

### DEC-013: Read-Only Policy Simulator (NEW)

**Decision:** Build a simulator that compares two policy configurations against the same dataset without mutating any data.

**Rationale:** Demonstrates incremental recovery value of RecoverAI's strategy-aware approach vs a naive baseline. Judges can see the projected improvement.

**Constraints:**
- Read-only: never writes to Razorpay
- All results labeled `PROJECTED`
- Never claims projected outcomes as verified recovery
- Runs against the same transaction batch used for actual recovery

---

### DEC-014: Closed-Loop Outcome Attribution (NEW)

**Decision:** When a recovery action produces an outcome, attribute it back to the specific (strategy, segment) combination and update performance metrics.

**Rationale:** This closes the feedback loop. Without attribution, the system cannot learn. With it, strategy recommendations improve as more data accumulates.

**Flow:**
1. Action executed → outcome verified → strategy_outcome record created
2. Corresponding `recovery_strategies` record updated (attempt_count++, success_count++ if recovered)
3. `recovery_rate` recomputed
4. Next recommendation for same segment uses updated data

---

### DEC-015: Evidence-Based Over AI-Only Recommendations (NEW)

**Decision:** When sufficient historical evidence exists (≥10 observed attempts), prefer observed strategy performance over AI recommendation.

**Rationale:**
- AI confidence (e.g. "0.91 recoverability") is a model estimate with no ground truth
- Observed recovery rate (e.g. "44.2% from 120 attempts") is empirical evidence
- Evidence-based recommendations are more defensible in a financial context

**When evidence is insufficient:** Fall back to AI recommendation but flag `confidence_level: LOW` and `evidence: INSUFFICIENT_SAMPLE`.

---

### DEC-016: Batch Scale 500+ Records (NEW)

**Decision:** Generate 500+ synthetic records instead of 50+.

**Rationale:**
- 50 records is enough for a basic demo but insufficient for meaningful per-segment strategy statistics
- 500+ records across ~20 segments provides enough data for credible strategy performance tracking
- Demonstrates portfolio-level thinking, which is the core differentiator

---

### DEC-017: Four Explicit Data Evidence Categories

**Decision:** Do not use vague "REAL" or single-level metrics. Use four explicit data evidence categories across all calculations, metrics, and strategy performance reports:

- **OBSERVED**: An actual recorded outcome from an available dataset or prior batch run.
- **VERIFIED**: An outcome explicitly confirmed by Razorpay Test Mode through authoritative API/webhook evidence (`payment.captured` or `payment_link.paid`).
- **SIMULATED**: A synthetic experiment or batch result generated locally (e.g. mock conversion outcomes).
- **PROJECTED**: An estimate or model output derived from observed evidence or simulation (e.g. policy simulator estimates).

**Usage Rules:**
1. Never mix these categories in the same metric without clearly indicating the source.
2. Creating a Payment Link is an action, NOT recovery.
3. Only a payment explicitly confirmed by Razorpay API/webhook is VERIFIED recovery.
4. Synthetic conversion results are SIMULATED recovery.
5. Strategy engine estimates based on observed or simulated rates are PROJECTED recovery.

---

### DEC-018: Product Naming

**Decision:** Name the product "RecoverAI" to reflect the AI-powered optimization focus.

**Rationale:** "AI Payment Recovery Agent" is generic. "RecoverAI" communicates the product identity and positions it as an intelligent system, not just a recovery tool.

---

### DEC-019: Abandoned Checkout Detection Mechanism

**Decision:** Treat checkout abandonment as an **inferred condition**, not a native Razorpay event.

**Rationale:** Standard Razorpay Checkout does NOT fire an `order.abandoned` event (that exists only in Razorpay Magic Checkout for e-commerce). 

**Implementation Mechanism:**
- Periodically poll `GET /v1/orders` where `status = created` AND `attempts = 0`.
- Filter for orders where `created_at` is older than threshold (e.g. >15 minutes).
- Mark as `CHECKOUT_ABANDONMENT` candidate.
- Explicitly log in audit trail that abandonment is an inferred state, not an authoritative webhook event, acknowledging that customer intent drop-off is inferred (could be closed tab, network drop, or changed mind).

---

### DEC-020: Small-Sample Statistical Protection for Strategy Engine

**Decision:** Implement Wilson score interval lower bound ranking to protect the strategy optimizer against small-sample noise.

**Rationale:** Naive conversion rates produce misleading rankings (e.g. 2/3 = 66.7% ranking higher than 53/120 = 44.2%). In financial recovery optimization, ranking by sample lower bound prevents over-allocating to untested strategies.

**Rules:**
1. Strategy engine ranks strategies by Wilson score interval lower bound ($95\%$ confidence).
2. Sample Size Thresholds:
   - `< 10 attempts` (`INSUFFICIENT`): Do not rely on observed rate alone.
   - `10–30 attempts` (`LOW`): Use lower-bound estimate; flag uncertainty.
   - `31–100 attempts` (`MEDIUM`): Weight observed rate alongside AI recommendation.
   - `> 100 attempts` (`HIGH`): Observed rate takes primary precedence.
3. Fallback Hierarchy when sample size is insufficient:
   - Level 1: Broader segment statistics (e.g., all `AUTH_FAILURE` regardless of amount)
   - Level 2: Deterministic baseline strategy (`PAYMENT_LINK` for auth, `RETRY` for network)
   - Level 3: Escalation to human review
4. UI Requirement: Expose evidence category, sample size, and confidence level alongside every strategy recommendation.

---

### DEC-021: Deterministic Policy Engine & Action Authorization Boundary

**Decision:** Enforce absolute separation between AI recommendation and recovery action execution. AI recommends; Policy decides; Executor acts.

**Rationale:** Financial recovery systems cannot delegate financial execution authority directly to LLM prompts. A deterministic policy layer guarantees safety, auditability, and compliance regardless of AI model hallucinations or confidence scores.

**Key Architecture Rules:**
1. **Zero LLM Authority**: Policy decisions are 100% code-driven and deterministic.
2. **Explicit 14-Rule Precedence**: Rule evaluation follows a strict precedence hierarchy (Terminal State -> Already Recovered -> Trust Gate -> Unsupported Strategy -> Max Automated Amount -> High Value -> Low Confidence -> Max Retries -> Max Contacts 24h -> Cooldown -> Contact Hours -> Active Link -> Strategy Constraints -> Approval).
3. **Structured Decisions**: Evaluates to `APPROVE`, `DENY`, or `ESCALATE` with granular explanations for dashboard rendering.
4. **Action Authorization Guard**: `ActionAuthorizationService` prevents financial action execution unless decision is `APPROVE` and `can_execute_action is True`. `DENY` and `ESCALATE` strictly block execution.
5. **Policy Versioning**: Every decision is stamped with `policy_version = "v1.0"` for simulator compatibility.

---

### DEC-022: Canonical 4-Dimensional Segment Identity

**Decision:** Define canonical segment identity as a 4-dimensional key: `failure_category × payment_method × amount_range × customer_type`.

**Key Format:**
`segment_name = failure_category_lower + "_" + payment_method + "_" + amount_range_lower + "_" + customer_type_lower`

**Rationale:**
1. Customer behavioral archetypes (`NEW`, `RETURNING`, `FATIGUED`) significantly alter recovery probability, contact sensitivity, and policy boundaries. For example, `FATIGUED` customers exhibit lower recovery rates under repetitive contact and trigger policy cooldown blocks, whereas `RETURNING` customers show higher responsiveness to direct Payment Links.
2. Incorporating `customer_type` directly into the canonical segment key allows the strategy engine to track separate historical outcome distributions (attempt count, success count, recovery rate) per customer archetype (e.g., `auth_failure_card_mid_returning` vs `auth_failure_card_mid_fatigued`).
3. For sparse combinations with sample sizes < 10 (`INSUFFICIENT` tier), the system relies on Wilson score lower bounds and falls back to 3D/2D aggregate levels (`failure_category × payment_method × amount_range` or broader failure category baselines), preserving statistical protection without losing archetype granularity.



