"""Video upload API v1 endpoints."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
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

    # Validate content type
    if file.content_type and not file.content_type.startswith("video/"):
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

    # TODO: Trigger Celery frame extraction task here once pipeline teammate implements it
    # from app.tasks.extract_frames import extract_frames_task
    # extract_frames_task.delay(str(assessment_id), video_type)

    return {
        "assessment_id": str(assessment_id),
        "video_type": video_type,
        "blob_path": blob_path,
        "status": "uploaded",
        "message": f"{video_type} video uploaded successfully",
    }


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
