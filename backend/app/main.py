"""FastAPI application entry point for the Car Insurance Quote service."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import init_routes, router
from app.api.websocket import init_ws, ws_router
from app.config import settings
from app.services.damage import DamageAssessmentService
from app.services.job_manager import JobManager
from app.services.triposr import TripoSRService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

triposr_service = TripoSRService()
damage_service = DamageAssessmentService()
job_manager = JobManager(triposr_service, damage_service)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — loading models …")

    triposr_service.load(
        model_id=settings.triposr_model_id,
        device=settings.triposr_device,
        chunk_size=settings.triposr_chunk_size,
    )
    damage_service.load()

    job_manager.set_loop(asyncio.get_event_loop())

    init_routes(job_manager)
    init_ws(job_manager)

    logger.info("Ready to accept requests")
    yield

    logger.info("Shutting down …")


app = FastAPI(
    title="Car Damage Quote API",
    description=(
        "Upload a photo of your damaged car to receive an instant 3D model "
        "and insurance quote."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(ws_router)
