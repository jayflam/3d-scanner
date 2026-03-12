"""3D model (GLB) API v1 endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_blob_storage, get_db
from app.models.assessment import Assessment
from app.services.blob_storage import BlobStorageService

router = APIRouter(prefix="/assessments/{assessment_id}/model", tags=["models"])

ALLOWED_MODEL_TYPES = {"exterior", "interior"}


@router.get("/{model_type}")
async def get_model(
    assessment_id: UUID,
    model_type: str,
    db: AsyncSession = Depends(get_db),
    blob: BlobStorageService = Depends(get_blob_storage),
):
    if model_type not in ALLOWED_MODEL_TYPES:
        raise HTTPException(400, f"model_type must be one of: {ALLOWED_MODEL_TYPES}")

    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    blob_path = (
        assessment.exterior_model_blob_path
        if model_type == "exterior"
        else assessment.interior_model_blob_path
    )

    if not blob_path:
        raise HTTPException(404, f"{model_type} model not ready yet")

    url = blob.get_blob_url(blob_path)

    return {
        "assessment_id": str(assessment_id),
        "model_type": model_type,
        "url": url,
        "blob_path": blob_path,
    }

