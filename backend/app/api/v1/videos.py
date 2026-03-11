"""Video upload API v1 endpoints."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_blob_storage, get_db
from app.models.assessment import Assessment, AssessmentStatus
from app.services.blob_storage import BlobStorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assessments/{assessment_id}/videos", tags=["videos"])

ALLOWED_VIDEO_TYPES = {"exterior", "interior"}
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB


@router.post("/{video_type}")
async def upload_video(
    assessment_id: UUID,
    video_type: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    blob: BlobStorageService = Depends(get_blob_storage),
):
    if video_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(400, f"video_type must be one of: {ALLOWED_VIDEO_TYPES}")

    # # Validate content type
    # if file.content_type and not file.content_type.startswith("video/"):
    #     raise HTTPException(400, "File must be a video")

    # Validate content type — allow video/* MIME types or known video extensions
    ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".3gp"}
    has_video_content_type = file.content_type and file.content_type.startswith("video/")
    has_video_extension = file.filename and Path(file.filename).suffix.lower() in ALLOWED_VIDEO_EXTENSIONS
    if not has_video_content_type and not has_video_extension:
        raise HTTPException(400, "File must be a video")

    # Look up assessment
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Update status
    assessment.status = AssessmentStatus.UPLOADING

    # Upload to blob storage
    blob_path = blob.upload_video(str(assessment_id), video_type, file.file)

    # Update assessment record
    if video_type == "exterior":
        assessment.exterior_video_blob_path = blob_path
    else:
        assessment.interior_video_blob_path = blob_path

    logger.info("Video uploaded: %s for assessment %s", video_type, assessment_id)

    has_exterior = assessment.exterior_video_blob_path is not None
    has_interior = assessment.interior_video_blob_path is not None

    # Start the pipeline as soon as the exterior video is uploaded.
    # Interior video is optional and will be used if present.
    should_start = has_exterior and video_type == "exterior"

    if should_start:
        from app.tasks.pipeline import start_pipeline  # noqa: PLC0415

        try:
            task_id = start_pipeline(
                str(assessment_id),
                has_exterior=has_exterior,
                has_interior=has_interior,
            )
            logger.info("Pipeline started for assessment %s (task_id=%s)", assessment_id, task_id)
        except Exception:
            logger.exception("Failed to start pipeline for assessment %s", assessment_id)

    return {
        "assessment_id": str(assessment_id),
        "video_type": video_type,
        "blob_path": blob_path,
        "status": "uploaded",
        "message": f"{video_type} video uploaded successfully",
    }


@router.get("/{video_type}/stream")
async def stream_video(
    assessment_id: UUID,
    video_type: str,
    db: AsyncSession = Depends(get_db),
    blob: BlobStorageService = Depends(get_blob_storage),
):
    if video_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(400, f"video_type must be one of: {ALLOWED_VIDEO_TYPES}")

    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    blob_path = (
        assessment.exterior_video_blob_path
        if video_type == "exterior"
        else assessment.interior_video_blob_path
    )
    if not blob_path:
        raise HTTPException(404, f"No {video_type} video uploaded yet")

    if blob.is_azure:
        redirect_url = blob.get_blob_url(blob_path)
        return RedirectResponse(url=redirect_url)

    local_path = blob.get_local_path(blob_path)
    if not local_path.exists():
        raise HTTPException(404, "Video file not found on disk")
    return FileResponse(str(local_path), media_type="video/mp4")


@router.get("/{video_type}/status")
async def get_video_status(
    assessment_id: UUID,
    video_type: str,
    db: AsyncSession = Depends(get_db),
):
    if video_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(400, f"video_type must be one of: {ALLOWED_VIDEO_TYPES}")

    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    blob_path = (
        assessment.exterior_video_blob_path
        if video_type == "exterior"
        else assessment.interior_video_blob_path
    )

    return {
        "assessment_id": str(assessment_id),
        "video_type": video_type,
        "uploaded": blob_path is not None,
        "blob_path": blob_path,
        "assessment_status": assessment.status.value,
    }
