"""API v1 router — aggregates all v1 sub-routers."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1 import assessments, reports, splats, videos
from app.config import settings

logger = logging.getLogger(__name__)

api_router = APIRouter(prefix="/api/v1")

# Include sub-routers
api_router.include_router(assessments.router)
api_router.include_router(videos.router)
api_router.include_router(splats.router)
api_router.include_router(reports.router)


# ── Health / System endpoints ─────────────────────────────────────────


@api_router.get("/health", tags=["system"])
async def health_check(db: AsyncSession = Depends(get_db)):
    checks = {"api": "ok"}

    # Check DB
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    # Check Redis (use async client to avoid blocking event loop)
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}


@api_router.get("/health/gpu", tags=["system"])
async def gpu_status():
    try:
        import torch

        if torch.cuda.is_available():
            return {
                "gpu_available": True,
                "device_count": torch.cuda.device_count(),
                "device_name": torch.cuda.get_device_name(0),
            }
        return {"gpu_available": False, "reason": "CUDA not available"}
    except ImportError:
        return {"gpu_available": False, "reason": "torch not installed"}


@api_router.get("/config", tags=["system"])
async def app_config():
    return {
        "max_upload_size_mb": settings.max_upload_size_mb,
        "allowed_video_extensions": list(settings.allowed_video_extensions),
        "allowed_image_extensions": list(settings.allowed_extensions),
        "blob_storage": "azure" if settings.azure_blob_connection_string else "local",
    }
