"""REST API routes for the car insurance quote service."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from app.config import settings
from app.models.schemas import (
    JobResponse,
    JobResult,
    JobStatus,
    UploadResponse,
)
from app.services.job_manager import JobManager

router = APIRouter(prefix="/api")

_job_manager: JobManager | None = None


def init_routes(job_manager: JobManager) -> None:
    global _job_manager
    _job_manager = job_manager


def _mgr() -> JobManager:
    assert _job_manager is not None, "JobManager not initialised"
    return _job_manager


# ── Upload ────────────────────────────────────────────────────────────────


@router.post("/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """Accept a car damage photo and start the processing pipeline."""
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(400, "File must be an image")

    ext = Path(file.filename or "upload.jpg").suffix.lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            400,
            f"Unsupported file type '{ext}'. Allowed: {settings.allowed_extensions}",
        )

    mgr = _mgr()
    job = mgr.create_job(image_path=Path("placeholder"))

    upload_dir = settings.upload_dir / job.id
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"input{ext}"

    with dest.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    job.image_path = dest
    mgr.enqueue(job)

    return UploadResponse(
        job_id=job.id,
        status=job.status,
        message="Image uploaded — processing started",
    )


# ── Job status ────────────────────────────────────────────────────────────


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    job = _mgr().get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return JobResponse(
        job_id=job.id,
        status=job.status,
        created_at=job.created_at,
        progress_pct=job.progress_pct,
        message=job.message,
    )


# ── Results ───────────────────────────────────────────────────────────────


@router.get("/jobs/{job_id}/result", response_model=JobResult)
async def get_job_result(job_id: str):
    job = _mgr().get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.status == JobStatus.FAILED:
        raise HTTPException(500, f"Job failed: {job.error}")
    if job.status != JobStatus.COMPLETE:
        raise HTTPException(409, f"Job not complete yet (status={job.status.value})")

    return JobResult(
        job_id=job.id,
        status=job.status,
        model_url=f"/api/jobs/{job_id}/model",
        assessment=job.assessment,
    )


@router.get("/jobs/{job_id}/model")
async def download_model(job_id: str):
    """Serve the generated GLB file."""
    job = _mgr().get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.glb_path is None or not job.glb_path.exists():
        raise HTTPException(409, "3D model not ready yet")
    return FileResponse(
        job.glb_path,
        media_type="model/gltf-binary",
        filename=f"{job_id}.glb",
    )


# ── Health ────────────────────────────────────────────────────────────────


@router.get("/health")
async def health():
    return {"status": "ok"}


# ── OpenAPI JSON (for frontend codegen) ───────────────────────────────────


@router.get("/openapi.json", include_in_schema=False)
async def openapi_json():
    """Convenience alias so the frontend team can fetch the schema at a
    predictable URL without knowing FastAPI internals."""
    from app.main import app as _app
    return _app.openapi()
