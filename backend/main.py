"""
RecoverAI FastAPI Main Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes.health import router as health_router
from backend.api.routes.webhooks import router as webhooks_router
from backend.api.routes.intelligence import router as intelligence_router
from backend.api.routes.segments import router as segments_router
from backend.api.routes.recovery import router as recovery_router
from backend.api.routes.strategies import router as strategies_router
from backend.api.routes.simulator import router as simulator_router

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

app.include_router(health_router)
app.include_router(webhooks_router)
app.include_router(intelligence_router)
app.include_router(segments_router)
app.include_router(recovery_router)
app.include_router(strategies_router)
app.include_router(simulator_router)
