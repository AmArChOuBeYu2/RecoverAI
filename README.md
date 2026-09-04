# RecoverAI — AI Revenue Recovery Agent

RecoverAI is an AI-powered revenue recovery optimization and execution system built for the Razorpay AI Buildathon (Track 03 — AI Revenue Recovery).

## Architecture & Principles
- **Core Question**: *"Which recovery intervention is most likely to recover this revenue, for this type of customer/payment, under these constraints, and what evidence do we have that this strategy actually works?"*
- **Core Principle**: *AI Recommends, Code Authorizes.*
- **Four Explicit Data Evidence Categories**:
  - `OBSERVED`: Recorded outcome from prior runs or historical datasets.
  - `VERIFIED`: Confirmed by Razorpay Test Mode via API/webhook.
  - `SIMULATED`: Synthetic conversion outcomes generated locally.
  - `PROJECTED`: Estimate or model output from simulator or optimizer.

## Project Structure
```
.
├── ARCHITECTURE.md                  # Complete engineering architecture
├── COMPETITIVE-DIFFERENTIATION.md   # Feature & architectural comparison vs Reven
├── DECISIONS.md                     # Technical decision log (DEC-001 to DEC-020)
├── IMPLEMENTATION_PLAN.md           # 24 implementation milestones
├── pyproject.toml                   # Python build & test configuration
├── requirements.txt                 # Pinned dependencies
├── .env.example                     # Environment variables template
├── backend/                         # FastAPI backend service
│   ├── __init__.py
│   └── main.py                      # Application entry point & health check
└── tests/                           # Pytest test suite
    └── test_env.py                  # Environment & health check tests
```

## Quick Start & Environment Setup

### 1. Prerequisites
- Python 3.14 (or Python 3.10+)

### 2. Setup Virtual Environment
```bash
python -m venv .venv
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your API keys in `.env`:
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`

*Note: Never commit `.env` to source control.*

### 5. Run Verification Tests
```bash
pytest
```

### 6. Run Health Server
```bash
uvicorn backend.main:app --reload
```
Access health status at `http://localhost:8000/api/health`.
