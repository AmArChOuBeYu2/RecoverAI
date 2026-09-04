"""
Health Check API Route Handler
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "RecoverAI",
        "version": "0.1.0",
        "evidence_categories": ["OBSERVED", "VERIFIED", "SIMULATED", "PROJECTED"],
    }
