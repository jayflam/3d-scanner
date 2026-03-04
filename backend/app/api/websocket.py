"""WebSocket endpoints for real-time job progress updates.

Two WebSocket endpoints:
  /ws/v1/assessments/{id}/status  — V1: Redis pub/sub from Celery tasks
  /ws/{job_id}                    — Legacy MVP: in-memory job manager

NOTE: V1 route MUST be registered before the wildcard /ws/{job_id} route,
otherwise the wildcard captures /ws/v1/... requests first.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.models.schemas import ProgressUpdate
from app.services.job_manager import JobManager

logger = logging.getLogger(__name__)
ws_router = APIRouter()

_job_manager: JobManager | None = None


def init_ws(job_manager: JobManager) -> None:
    global _job_manager
    _job_manager = job_manager


def _mgr() -> JobManager:
    assert _job_manager is not None
    return _job_manager


# ---------------------------------------------------------------------------
# V1 WebSocket — Redis pub/sub for Celery pipeline progress
# NOTE: Must be registered BEFORE the wildcard /ws/{job_id} route below.
# ---------------------------------------------------------------------------


@ws_router.websocket("/ws/v1/assessments/{assessment_id}/status")
async def assessment_progress_ws(websocket: WebSocket, assessment_id: str):
    """Stream real-time pipeline progress for an assessment via Redis pub/sub.

    Messages are JSON objects published by Celery tasks to the channel
    ``insurascan:progress:{assessment_id}``.
    """
    await websocket.accept()
    logger.info("WebSocket connected for assessment %s", assessment_id)

    channel_name = f"insurascan:progress:{assessment_id}"
    done = asyncio.Event()

    async def _redis_listener() -> None:
        """Subscribe to Redis channel and forward messages to WebSocket."""
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(settings.redis_url)
            pubsub = r.pubsub()
            await pubsub.subscribe(channel_name)

            async for message in pubsub.listen():
                if done.is_set():
                    break
                if message["type"] != "message":
                    continue

                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()

                try:
                    await websocket.send_text(data)

                    # Check if pipeline is done
                    parsed = json.loads(data)
                    stage = parsed.get("stage", "")
                    pct = parsed.get("progress_pct", 0)
                    if stage == "report_generation" and pct >= 100:
                        done.set()
                except Exception:
                    done.set()
                    break

            await pubsub.unsubscribe(channel_name)
            await r.aclose()
        except Exception:
            logger.exception("Redis listener error for %s", assessment_id)
            done.set()

    # Start Redis listener as background task
    listener_task = asyncio.create_task(_redis_listener())

    try:
        # Keep connection alive: read client pings / wait for done
        while not done.is_set():
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                break
    finally:
        done.set()
        listener_task.cancel()
        try:
            await listener_task
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("WebSocket disconnected for assessment %s", assessment_id)


# ---------------------------------------------------------------------------
# Legacy MVP WebSocket (in-memory job manager)
# ---------------------------------------------------------------------------


@ws_router.websocket("/ws/{job_id}")
async def job_progress_ws(websocket: WebSocket, job_id: str):
    mgr = _mgr()
    job = mgr.get(job_id)
    if job is None:
        await websocket.close(code=4004, reason="Job not found")
        return

    await websocket.accept()

    done = asyncio.Event()

    async def _on_update(update: ProgressUpdate) -> None:
        try:
            await websocket.send_text(update.model_dump_json())
            if update.status in ("complete", "failed"):
                done.set()
        except Exception:
            done.set()

    mgr.subscribe(job_id, _on_update)
    try:
        # Send current state immediately so the client doesn't miss anything
        current = ProgressUpdate(
            job_id=job.id,
            status=job.status,
            progress_pct=job.progress_pct,
            message=job.message,
        )
        await websocket.send_text(current.model_dump_json())

        if job.status in ("complete", "failed"):
            return

        # Keep connection alive until job finishes or client disconnects
        while not done.is_set():
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                break

    finally:
        mgr.unsubscribe(job_id, _on_update)
        try:
            await websocket.close()
        except Exception:
            pass

