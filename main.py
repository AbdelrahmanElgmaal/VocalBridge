"""
Vocal Bridge AI Dubbing Service — FastAPI Entry Point
=====================================================

This is the main entry point for the AI microservice.
Start it with:

    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

The .NET backend communicates with this service via three endpoints:

    POST  /api/dubbing/start        → Queue a dubbing job
    GET   /api/dubbing/status/{id}  → Poll real-time progress
    POST  /api/dubbing/cancel/{id}  → Abort a running job

A health check is available at:

    GET   /health                   → {"status": "healthy", ...}
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import router as dubbing_router
from api.job_manager import job_manager
from utils.logger import pipeline_logger as logger

# ── Track service uptime ──
_started_at: datetime = datetime.now(timezone.utc)


# ── Lifespan handler (startup / shutdown) ─────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on service start and shutdown."""
    global _started_at
    _started_at = datetime.now(timezone.utc)
    logger.info("🚀 Vocal Bridge AI Service — ONLINE")
    logger.info("   Endpoints:")
    logger.info("     POST  /api/dubbing/start")
    logger.info("     GET   /api/dubbing/status/{job_id}")
    logger.info("     POST  /api/dubbing/cancel/{job_id}")
    logger.info("     GET   /health")
    yield
    logger.info("🛑 Vocal Bridge AI Service — SHUTTING DOWN")


# ── FastAPI Application ──────────────────────────────────────

app = FastAPI(
    title="Vocal Bridge AI Dubbing Service",
    description=(
        "Microservice that exposes the Vocal Bridge AI video dubbing "
        "pipeline as a REST API.  Designed for integration with an "
        "external .NET backend."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ── CORS — Allow the .NET backend to call this service ────────
# In production, replace ["*"] with the actual .NET backend origin.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Mount the dubbing router ─────────────────────────────────

app.include_router(dubbing_router)


# ── Health Check ─────────────────────────────────────────────

@app.get(
    "/health",
    tags=["System"],
    summary="Service health check",
    description="Returns service status, version, and active job count.",
)
async def health_check():
    """
    .NET backend can ping this to verify the AI service is reachable.

    Example cURL:
        curl http://localhost:8000/health
    """
    uptime = (datetime.now(timezone.utc) - _started_at).total_seconds()
    return {
        "status": "healthy",
        "service": "vocal-bridge-ai",
        "version": "1.0.0",
        "active_jobs": job_manager.active_count,
        "uptime_seconds": round(uptime, 1),
    }
