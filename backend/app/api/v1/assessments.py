"""Assessment CRUD API v1 endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_blob_storage, get_db
from app.models.assessment import Assessment, AssessmentStatus
from app.services.blob_storage import BlobStorageService
from app.schemas.assessment import (
    AssessmentCreateResponse,
    AssessmentListResponse,
    AssessmentResponse,
    CreateAssessment,
    PipelineStatus,
    VehicleInfo,
)

router = APIRouter(prefix="/assessments", tags=["assessments"])


def _build_pipeline_status(a: Assessment) -> PipelineStatus:
    """Derive pipeline status from assessment state."""
    status_map = {
        AssessmentStatus.CREATED: PipelineStatus(),
        AssessmentStatus.UPLOADING: PipelineStatus(exterior_video="in_progress"),
        AssessmentStatus.EXTRACTING_FRAMES: PipelineStatus(
            exterior_video="complete" if a.exterior_video_blob_path else "pending",
            interior_video="complete" if a.interior_video_blob_path else "pending",
            frame_extraction="in_progress",
        ),
        AssessmentStatus.SPLATTING: PipelineStatus(
            exterior_video="complete" if a.exterior_video_blob_path else "pending",
            interior_video="complete" if a.interior_video_blob_path else "pending",
            frame_extraction="complete",
            gaussian_splatting="in_progress",
        ),
        AssessmentStatus.ANALYZING: PipelineStatus(
            exterior_video="complete" if a.exterior_video_blob_path else "pending",
            interior_video="complete" if a.interior_video_blob_path else "pending",
            frame_extraction="complete",
            gaussian_splatting="complete" if a.exterior_splat_blob_path else "in_progress",
            damage_analysis="in_progress",
        ),
        AssessmentStatus.COMPLETE: PipelineStatus(
            exterior_video="complete",
            interior_video="complete" if a.interior_video_blob_path else "pending",
            frame_extraction="complete",
            gaussian_splatting="complete",
            damage_analysis="complete",
            report_generation="complete",
        ),
        AssessmentStatus.FAILED: PipelineStatus(
            exterior_video="complete" if a.exterior_video_blob_path else "failed",
            interior_video="complete" if a.interior_video_blob_path else "failed",
            frame_extraction="failed",
        ),
    }
    return status_map.get(a.status, PipelineStatus())


def _to_response(a: Assessment) -> AssessmentResponse:
    return AssessmentResponse(
        id=a.id,
        status=a.status.value,
        claim_number=a.claim_number,
        agent_id=a.agent_id,
        vin=a.vin,
        vehicle=VehicleInfo(year=a.vehicle_year, make=a.vehicle_make, model=a.vehicle_model),
        pipeline=_build_pipeline_status(a),
        frame_count={"exterior": a.exterior_frame_count, "interior": a.interior_frame_count},
        splat_ready={
            "exterior": a.exterior_splat_blob_path is not None,
            "interior": a.interior_splat_blob_path is not None,
        },
        model_ready={
            "exterior": a.exterior_model_blob_path is not None,
            "interior": a.interior_model_blob_path is not None,
        },
        total_estimate_low=float(a.total_estimate_low) if a.total_estimate_low else None,
        total_estimate_high=float(a.total_estimate_high) if a.total_estimate_high else None,
        error_message=a.error_message,
        created_at=a.created_at,
        updated_at=a.updated_at,
        completed_at=a.completed_at,
    )


@router.post("", response_model=AssessmentCreateResponse, status_code=201)
async def create_assessment(
    body: CreateAssessment,
    db: AsyncSession = Depends(get_db),
):
    assessment = Assessment(
        claim_number=body.claim_number,
        agent_id=body.agent_id,
        vehicle_year=body.vehicle_year,
        vehicle_make=body.vehicle_make,
        vehicle_model=body.vehicle_model,
        vin=body.vin,
        gps_latitude=body.gps_latitude,
        gps_longitude=body.gps_longitude,
        status=AssessmentStatus.CREATED,
    )
    db.add(assessment)
    await db.flush()

    return AssessmentCreateResponse(
        id=assessment.id,
        status=assessment.status.value,
        claim_number=assessment.claim_number,
        created_at=assessment.created_at,
        upload_urls={
            "exterior": f"/api/v1/assessments/{assessment.id}/videos/exterior",
            "interior": f"/api/v1/assessments/{assessment.id}/videos/interior",
        },
    )


@router.get("", response_model=AssessmentListResponse)
async def list_assessments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    claim_number: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Assessment)

    if status:
        try:
            status_enum = AssessmentStatus(status)
            query = query.where(Assessment.status == status_enum)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    if claim_number:
        query = query.where(Assessment.claim_number.ilike(f"%{claim_number}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    # Paginate
    query = query.order_by(Assessment.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    assessments = result.scalars().all()

    return AssessmentListResponse(
        items=[_to_response(a) for a in assessments],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    return _to_response(assessment)


@router.delete("/{assessment_id}", status_code=204)
async def delete_assessment(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    blob: BlobStorageService = Depends(get_blob_storage),
):
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Delete all blobs first (videos, frames, splats, report)
    try:
        blob.delete_assessment_blobs(str(assessment_id))
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to delete blobs for assessment %s", assessment_id, exc_info=True
        )

    # Cascade deletes damage_items and processing_jobs via ORM relationship
    await db.delete(assessment)
    await db.commit()
