# Synthetic Dataset & Evaluation Framework (Milestone 7)

## Executive Summary
This document defines the methodology, architecture, data distributions, anti-leakage safeguards, and validation rules for the RecoverAI Synthetic Merchant-Payment Evaluation Dataset (`v1.0`).

The synthetic dataset provides 1,000 realistic, reproducible failed/abandoned transaction records spanning 400 customer profiles. It serves as the authoritative foundation for RecoverAI's segmentation, strategy-performance analysis, optimizer evaluation, policy simulation, and outcome attribution.

---

## Key Principles & Anti-Leakage Safeguards

1. **Strict Data Separation**:
   - `data/observed/`: Historical outcomes and payment records accessible to the optimizer.
   - `data/holdout/`: 20% temporal holdout set (latest chronological payments) reserved strictly for evaluation.
   - `data/simulation_truth/`: Latent ground-truth probabilities and true optimal strategies. **ISOLATED** from application APIs and never loaded during strategy optimization.
   - `data/metadata/`: Dataset versioning, seed, record counts, and split definitions.

2. **Zero Optimizer Privilege**:
   - The optimizer receives only `OBSERVED` outcomes from historical merchant policy executions.
   - Ground-truth latent probabilities and outcome generation parameters are completely hidden.

3. **Deterministic Reproducibility**:
   - Default random seed: `20260904`.
   - Running the generator twice with the same seed yields 100% byte-for-byte identical output.

4. **Monetary Integrity**:
   - All amounts are strictly positive integer `paise` (e.g., ₹10,000.00 = `1000000` paise). Floating-point money is prohibited.

---

## Dataset Architecture & Schema

### 1. Data Directory Structure
```
data/
├── metadata/
│   └── dataset_metadata.json   # Reproducibility metadata, seed, versions, split stats
├── observed/
│   ├── customers.json          # 400 customer profiles with consistent payment history
│   ├── transactions.json       # 800 historical/train payment failures
│   ├── outcomes.json           # 800 observed recovery strategy outcomes
│   └── segments.json           # Segment definitions
├── holdout/
│   ├── transactions.json       # 200 holdout/test payment failures (chronologically latest)
│   └── outcomes.json           # 200 holdout observed outcomes
└── simulation_truth/
    └── ground_truth.json       # Latent probabilities, best strategies, and influencing factors
```

---

## Data Distributions

### 1. Failure Category Proportions
- `AUTHENTICATION_FAILURE`: 35%
- `BANK_TIMEOUT`: 25%
- `CHECKOUT_ABANDONMENT`: 15%
- `INSUFFICIENT_FUNDS`: 10%
- `REPEATED_FAILURE`: 8%
- `NETWORK_FAILURE`: 5%
- `UNKNOWN`: 2%

### 2. Payment Method Proportions
- `card`: 40%
- `upi`: 35%
- `netbanking`: 15%
- `wallet`: 10%

### 3. Customer Type Proportions
- `NEW`: 40% (Account age 1–30 days, 0–2 prior transactions)
- `RETURNING`: 45% (Account age 31–365 days, 3–25 prior transactions, strong recovery history)
- `FATIGUED`: 15% (High prior failures, high 24h contact count, -18% recovery probability penalty)

### 4. Amount Distribution (Heavy-Tailed Log-Normal)
- **LOW** (< ₹500): 25%
- **MID** (₹500 – ₹5,000): 50%
- **HIGH** (₹5,000 – ₹50,000): 18%
- **PREMIUM** (> ₹50,000): 7%

#### Exact Boundary Edge Cases Included:
- `49999` paise (₹499.99 - LOW/MID boundary)
- `50000` paise (₹500.00 - Exact boundary)
- `999999` paise (₹9,999.99 - High value boundary)
- `1000000` paise (₹10,000.00 - High value threshold)
- `1000001` paise (₹10,000.01 - Above high value threshold)
- `4999999` paise (₹49,999.99 - Below max auto action limit)
- `5000000` paise (₹50,000.00 - Exact max auto action threshold)
- `5000001` paise (₹50,000.01 - Above max auto action threshold)

---

## Segment Generation & Sample-Size Tiers

Segments are derived deterministically:
`segment_name = failure_category_lower + "_" + payment_method + "_" + amount_range_lower`

The dataset exercises all 4 sample-size protection tiers:
1. **INSUFFICIENT** (< 10 records): Long-tail segment combinations.
2. **LOW** (10 – 30 records): Moderate frequency failure patterns.
3. **MEDIUM** (31 – 100 records): Common failure patterns.
4. **HIGH** (> 100 records): Dominant failure clusters (e.g., `authentication_failure_card_mid`).

---

## Ground Truth & Strategy Outcome Model

### Latent Ground Truth (`SIMULATION_GROUND_TRUTH`)
For each transaction, true latent probabilities $P(\text{recovery} \mid \text{transaction}, \text{strategy})$ are calculated from:
- Failure category base performance
- Customer type & fatigue modifiers
- High-value transaction penalties
- Gaussian stochastic noise $N(0, 0.04)$

### Case G Small-Sample Trap Scenario
An explicit trap scenario is included in the synthetic dataset:
- **Strategy A** (`METHOD_SWITCH`): 1 attempt / 1 recovery (100% naive rate, sample size = 1, Wilson lower bound ≈ 0.025).
- **Strategy B** (`PAYMENT_LINK`): 40 recoveries / 150 attempts (26.7% recovery rate, sample size = 150, Wilson lower bound ≈ 0.20).

This guarantees that the future Strategy Engine cannot blindly select Strategy A and must utilize Wilson score lower-bound confidence intervals.

---

## Validation & Verification

Generation executes strict validation (`backend/seed/validation.py`):
1. **Enum Correctness**: All string fields match project domain enums.
2. **Amount Invariants**: `recovered_amount_paise <= amount_paise` and `amount_paise > 0`.
3. **Customer History Invariants**: `successful + failed <= total`, `recovered <= failed`.
4. **Temporal Ordering**: `created_at <= failed_at`, and `max(train.created_at) <= min(holdout.created_at)`.
5. **Anti-Leakage**: Zero ground-truth fields present in `OBSERVED` outcomes.

---

## Reproducibility Commands

To regenerate the synthetic dataset deterministically:
```bash
python -m backend.seed.generator
```

To run the automated test suite (83 passed tests):
```bash
.venv\Scripts\pytest.exe
```

---

## Disclaimer
This dataset is synthetically generated for testing, simulation, and algorithm evaluation in a merchant payment environment. It does not represent real customer PII or actual merchant transaction records.
