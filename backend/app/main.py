"""FastAPI application entry point for InsuraScan."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router as v1_router
from app.api.websocket import init_ws, ws_router
from app.config import settings
from app.services.blob_storage import blob_storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# Legacy MVP services — lazy-loaded to avoid crashing if GPU deps are missing
triposr_service = None
damage_service = None
job_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global triposr_service, damage_service, job_manager

    logger.info("Starting up — initializing services …")

    # Initialize blob storage (Azure or local fallback)
    blob_storage.init()

    # Load legacy MVP services (TripoSR + single-image damage assessment)
    # These require GPU/ML deps that may not be installed; skip gracefully.
    # Skip if already initialized (e.g., by test fixtures).
    if triposr_service is None:
        try:
            from app.services.triposr import TripoSRService
            from app.services.damage import DamageAssessmentService
            from app.services.job_manager import JobManager
            from app.api.routes import init_routes, router as legacy_router

            triposr_service = TripoSRService()
            damage_service = DamageAssessmentService()
            job_manager = JobManager(triposr_service, damage_service)

            try:
                triposr_service.load(
                    model_id=settings.triposr_model_id,
                    device=settings.triposr_device,
                    chunk_size=settings.triposr_chunk_size,
                )
            except Exception as exc:
                logger.warning("TripoSR not available: %s", exc)

            damage_service.load()
            job_manager.set_loop(asyncio.get_event_loop())

            init_routes(job_manager)
            init_ws(job_manager)

            # Mount legacy routes only if services loaded
            app.include_router(legacy_router)
        except Exception as exc:
            logger.warning("Legacy MVP services not available (GPU deps missing): %s", exc)

    # Always set the event loop on the job manager (even if pre-initialized by tests)
    if job_manager is not None:
        job_manager.set_loop(asyncio.get_event_loop())

    logger.info("Ready to accept requests")
    yield

    logger.info("Shutting down …")


app = FastAPI(
    title="InsuraScan API",
    description=(
        "AR/XR Vehicle Damage Assessment Platform — upload videos, "
        "generate 3D Gaussian Splats, and get AI-powered damage estimates."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket routes (V1 + legacy)
app.include_router(ws_router)

# New v1 API routes (video-based pipeline)
app.include_router(v1_router)
