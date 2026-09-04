"""
Health Check API Route Handler — RecoverAI Milestone 20
Provides comprehensive system health monitoring across Database, Razorpay integration,
and AI LLM provider SDK configurations.
"""

import os
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database.session import get_db

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    # Database check
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # Razorpay SDK / Test Mode check
    rzp_key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    rzp_key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    rzp_status = "configured" if (rzp_key_id and rzp_key_secret) else "unconfigured (test simulation mode active)"

    # AI LLM Provider check
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    llm_status = {
        "openai": "configured" if openai_key else "missing_key",
        "gemini": "configured" if gemini_key else "missing_key",
        "fallback": "deterministic_rules_active",
    }

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "service": "RecoverAI",
        "version": "0.1.0",
        "components": {
            "database": db_status,
            "razorpay": rzp_status,
            "llm_providers": llm_status,
        },
        "evidence_categories": ["OBSERVED", "VERIFIED", "SIMULATED", "PROJECTED"],
    }

