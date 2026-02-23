"""Pydantic v2 schemas for Assessment API v1 endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateAssessment(BaseModel):
    claim_number: str = Field(..., max_length=50)
    agent_id: str = Field(..., max_length=100)
    vehicle_year: int
    vehicle_make: str = Field(..., max_length=50)
    vehicle_model: str = Field(..., max_length=50)
    vin: str = Field(default="", max_length=17)
    gps_latitude: float | None = None
    gps_longitude: float | None = None


class PipelineStatus(BaseModel):
    exterior_video: str = "pending"
    interior_video: str = "pending"
    frame_extraction: str = "pending"
    gaussian_splatting: str = "pending"
    damage_analysis: str = "pending"
    report_generation: str = "pending"


class VehicleInfo(BaseModel):
    year: int
    make: str
    model: str


class AssessmentResponse(BaseModel):
    id: UUID
    status: str
    claim_number: str
    agent_id: str
    vin: str
    vehicle: VehicleInfo
    pipeline: PipelineStatus
    frame_count: dict[str, int]
    splat_ready: dict[str, bool]
    total_estimate_low: float | None = None
    total_estimate_high: float | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class AssessmentCreateResponse(BaseModel):
    id: UUID
    status: str
    claim_number: str
    created_at: datetime
    upload_urls: dict[str, str]


class AssessmentListResponse(BaseModel):
    items: list[AssessmentResponse]
    total: int
    page: int
    page_size: int
