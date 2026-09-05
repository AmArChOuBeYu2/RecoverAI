import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.database.session import init_db
from backend.api.routes.health import router as health_router
from backend.api.routes.webhooks import router as webhooks_router
from backend.api.routes.intelligence import router as intelligence_router
from backend.api.routes.segments import router as segments_router
from backend.api.routes.recovery import router as recovery_router
from backend.api.routes.strategies import router as strategies_router
from backend.api.routes.simulator import router as simulator_router
from backend.api.routes.dashboard import router as dashboard_router
from backend.api.routes.transactions import router as transactions_router
from backend.api.routes.audit import router as audit_router
from backend.api.routes.batch import router as batch_router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database on startup: {e}")
    yield

app = FastAPI(
    title="NIVARAN",
    description="Revenue recovery, resolved intelligently.",
    version="0.1.0",
    lifespan=lifespan,
)

allowed_origins = [
    "https://frontend-eta-blush-g7x2xt69ry.vercel.app",
    "https://frontend-9nysw3zte-amars-projects-20e00d38.vercel.app",
    "https://project-7-razor-pay.vercel.app",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]

env_origins = os.environ.get("ALLOWED_ORIGINS")
if env_origins:
    for o in env_origins.split(","):
        o_clean = o.strip()
        if o_clean and o_clean not in allowed_origins:
            allowed_origins.append(o_clean)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handling Middleware
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected internal error occurred. Please contact system administrator.",
            "path": request.url.path,
        },
    )

# Include All API Routers
app.include_router(health_router)
app.include_router(webhooks_router)
app.include_router(intelligence_router)
app.include_router(dashboard_router)
app.include_router(transactions_router)
app.include_router(segments_router)
app.include_router(recovery_router)
app.include_router(strategies_router)
app.include_router(simulator_router)
app.include_router(audit_router)
app.include_router(batch_router)

