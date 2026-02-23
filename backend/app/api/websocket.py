"""WebSocket endpoint for real-time job progress updates."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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
