"""Gaussian Splat API v1 endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_blob_storage, get_db
from app.models.assessment import Assessment
from app.services.blob_storage import BlobStorageService

router = APIRouter(prefix="/assessments/{assessment_id}/splat", tags=["splats"])

ALLOWED_SPLAT_TYPES = {"exterior", "interior"}


@router.get("/{splat_type}")
async def get_splat(
    assessment_id: UUID,
    splat_type: str,
    db: AsyncSession = Depends(get_db),
    blob: BlobStorageService = Depends(get_blob_storage),
):
    if splat_type not in ALLOWED_SPLAT_TYPES:
        raise HTTPException(400, f"splat_type must be one of: {ALLOWED_SPLAT_TYPES}")

    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    blob_path = (
        assessment.exterior_splat_blob_path
        if splat_type == "exterior"
        else assessment.interior_splat_blob_path
    )

    if not blob_path:
        raise HTTPException(404, f"{splat_type} splat not ready yet")

    url = blob.get_blob_url(blob_path)

    return {
        "assessment_id": str(assessment_id),
        "splat_type": splat_type,
        "url": url,
        "blob_path": blob_path,
    }
