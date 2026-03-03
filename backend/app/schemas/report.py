"""Pydantic v2 schemas for damage report responses."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.damage import DamageItemResponse


class ReportSummary(BaseModel):
    total_damage_count: int
    total_estimate_low: float
    total_estimate_high: float
    recommendation: str
    narrative: str


class VehicleInfo(BaseModel):
    year: int
    make: str
    model: str
    vin: str


class ReportResponse(BaseModel):
    assessment_id: UUID
    vehicle: VehicleInfo
    damages: list[DamageItemResponse]
    summary: ReportSummary
    generated_at: datetime

    model_config = {"from_attributes": True}
