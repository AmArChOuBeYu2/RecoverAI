"""
RecoverAI FastAPI Main Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="RecoverAI",
    description="AI-Powered Revenue Recovery Optimization & Execution System",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "RecoverAI",
        "version": "0.1.0",
        "evidence_categories": ["OBSERVED", "VERIFIED", "SIMULATED", "PROJECTED"]
    }
