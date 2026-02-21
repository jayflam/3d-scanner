"""In-memory async job manager.

Tracks upload-to-result lifecycle and broadcasts progress over WebSocket.
Suitable for a hackathon demo; swap for a real queue (Azure Queue / Service Bus)
in production.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine

from PIL import Image

from app.config import settings
from app.models.schemas import (
    DamageAssessment,
    JobStatus,
    ProgressUpdate,
)
from app.services.damage import DamageAssessmentService
from app.services.triposr import TripoSRService

logger = logging.getLogger(__name__)


class Job:
    __slots__ = (
        "id",
        "status",
        "created_at",
        "progress_pct",
        "message",
        "image_path",
        "glb_path",
        "assessment",
        "error",
    )

    def __init__(self, job_id: str, image_path: Path) -> None:
        self.id = job_id
        self.status = JobStatus.PENDING
        self.created_at = datetime.now(timezone.utc)
        self.progress_pct = 0
        self.message = "Queued"
        self.image_path = image_path
        self.glb_path: Path | None = None
        self.assessment: DamageAssessment | None = None
        self.error: str | None = None


ProgressCallback = Callable[[ProgressUpdate], Coroutine[Any, Any, None]]


class JobManager:
    def __init__(
        self,
        triposr: TripoSRService,
        damage: DamageAssessmentService,
    ) -> None:
        self._triposr = triposr
        self._damage = damage
        self._jobs: dict[str, Job] = {}
        self._subscribers: dict[str, list[ProgressCallback]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    # -- job CRUD -----------------------------------------------------------

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def create_job(self, image_path: Path) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job = Job(job_id, image_path)
        self._jobs[job_id] = job
        return job

    # -- subscriptions for WebSocket ----------------------------------------

    def subscribe(self, job_id: str, callback: ProgressCallback) -> None:
        self._subscribers.setdefault(job_id, []).append(callback)

    def unsubscribe(self, job_id: str, callback: ProgressCallback) -> None:
        cbs = self._subscribers.get(job_id, [])
        if callback in cbs:
            cbs.remove(callback)

    async def _notify(self, job: Job) -> None:
        update = ProgressUpdate(
            job_id=job.id,
            status=job.status,
            progress_pct=job.progress_pct,
            message=job.message,
        )
        for cb in list(self._subscribers.get(job.id, [])):
            try:
                await cb(update)
            except Exception:
                logger.debug("Subscriber callback failed", exc_info=True)

    # -- processing pipeline ------------------------------------------------

    def enqueue(self, job: Job) -> None:
        """Schedule the processing pipeline in the background."""
        loop = self._loop or asyncio.get_event_loop()
        loop.create_task(self._process(job))

    async def _process(self, job: Job) -> None:
        try:
            await self._set(job, JobStatus.PREPROCESSING, 10, "Preprocessing image…")
            image = Image.open(job.image_path).convert("RGBA")

            # Run 3D generation and damage assessment concurrently.
            # TripoSR is CPU/GPU-bound so we offload it to a thread.
            await self._set(job, JobStatus.GENERATING_3D, 20, "Generating 3D model…")

            output_stem = settings.output_dir / job.id / "model"
            output_stem.parent.mkdir(parents=True, exist_ok=True)

            loop = asyncio.get_event_loop()

            gen_task = loop.run_in_executor(
                None,
                lambda: self._triposr.generate_glb(
                    image,
                    output_stem,
                    mc_resolution=settings.triposr_mc_resolution,
                    texture_resolution=settings.triposr_texture_resolution,
                    foreground_ratio=settings.triposr_foreground_ratio,
                ),
            )

            await self._set(job, JobStatus.ASSESSING_DAMAGE, 40, "Assessing damage…")
            assess_task = self._damage.assess(image)

            glb_path, assessment = await asyncio.gather(gen_task, assess_task)

            job.glb_path = glb_path
            job.assessment = assessment

            await self._set(job, JobStatus.COMPLETE, 100, "Done")

        except Exception as exc:
            logger.error("Job %s failed: %s", job.id, exc, exc_info=True)
            job.error = traceback.format_exc()
            await self._set(job, JobStatus.FAILED, job.progress_pct, str(exc))

    async def _set(
        self, job: Job, status: JobStatus, pct: int, msg: str
    ) -> None:
        job.status = status
        job.progress_pct = pct
        job.message = msg
        await self._notify(job)
