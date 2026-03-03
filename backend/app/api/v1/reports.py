"""Damage report API v1 endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_blob_storage, get_db
from app.models.assessment import Assessment
from app.models.damage_item import DamageItem
from app.schemas.damage import DamageItemResponse, DamageListResponse
from app.schemas.report import ReportResponse, ReportSummary, VehicleInfo
from app.services.blob_storage import BlobStorageService

router = APIRouter(prefix="/assessments/{assessment_id}", tags=["reports"])


@router.get("/report", response_model=ReportResponse)
async def get_report(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Assessment)
        .options(selectinload(Assessment.damage_items))
        .where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    damages = [
        DamageItemResponse(
            id=d.id,
            assessment_id=d.assessment_id,
            damage_id=d.damage_id,
            location=d.location,
            vehicle_zone=d.vehicle_zone.value,
            damage_type=d.damage_type,
            severity=d.severity.value,
            description=d.description,
            affected_parts=d.affected_parts or [],
            repair_method=d.repair_method,
            estimated_cost_low=float(d.estimated_cost_low),
            estimated_cost_high=float(d.estimated_cost_high),
            confidence_score=float(d.confidence_score),
            reference_frame_paths=d.reference_frame_paths or [],
            created_at=d.created_at,
        )
        for d in assessment.damage_items
    ]

    total_low = sum(d.estimated_cost_low for d in damages)
    total_high = sum(d.estimated_cost_high for d in damages)

    return ReportResponse(
        assessment_id=assessment.id,
        vehicle=VehicleInfo(
            year=assessment.vehicle_year,
            make=assessment.vehicle_make,
            model=assessment.vehicle_model,
            vin=assessment.vin,
        ),
        damages=damages,
        summary=ReportSummary(
            total_damage_count=len(damages),
            total_estimate_low=total_low,
            total_estimate_high=total_high,
            recommendation="Repair" if total_high < 10000 else "Total loss evaluation recommended",
            narrative=f"Vehicle sustained {len(damages)} damage instance(s) with estimated repair costs of ${total_low:,.2f} - ${total_high:,.2f}.",
        ),
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/report/pdf")
async def get_report_pdf(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    blob: BlobStorageService = Depends(get_blob_storage),
):
    # Try to fetch pre-generated PDF from blob storage
    blob_path = f"reports/{assessment_id}/report.pdf"
    try:
        pdf_bytes = blob.download_blob(blob_path)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="report_{assessment_id}.pdf"'
            },
        )
    except FileNotFoundError:
        raise HTTPException(404, "PDF report not generated yet")


@router.get("/damages", response_model=DamageListResponse)
async def list_damages(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Assessment not found")

    result = await db.execute(
        select(DamageItem).where(DamageItem.assessment_id == assessment_id)
    )
    items = result.scalars().all()

    return DamageListResponse(
        items=[
            DamageItemResponse(
                id=d.id,
                assessment_id=d.assessment_id,
                damage_id=d.damage_id,
                location=d.location,
                vehicle_zone=d.vehicle_zone.value,
                damage_type=d.damage_type,
                severity=d.severity.value,
                description=d.description,
                affected_parts=d.affected_parts or [],
                repair_method=d.repair_method,
                estimated_cost_low=float(d.estimated_cost_low),
                estimated_cost_high=float(d.estimated_cost_high),
                confidence_score=float(d.confidence_score),
                reference_frame_paths=d.reference_frame_paths or [],
                created_at=d.created_at,
            )
            for d in items
        ],
        total=len(items),
    )


@router.get("/frames")
async def list_frames(
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

    frames = {
        "exterior": {
            "count": assessment.exterior_frame_count,
            "blob_prefix": f"frames/{assessment_id}/exterior/",
        },
        "interior": {
            "count": assessment.interior_frame_count,
            "blob_prefix": f"frames/{assessment_id}/interior/",
        },
    }

    return {
        "assessment_id": str(assessment_id),
        "frames": frames,
    }
