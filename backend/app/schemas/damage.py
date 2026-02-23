"""Pydantic v2 schemas for damage item responses."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DamageItemResponse(BaseModel):
    id: UUID
    assessment_id: UUID
    damage_id: str
    location: str
    vehicle_zone: str
    damage_type: str
    severity: str
    description: str
    affected_parts: list[str]
    repair_method: str
    estimated_cost_low: float
    estimated_cost_high: float
    confidence_score: float
    reference_frame_paths: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class DamageListResponse(BaseModel):
    items: list[DamageItemResponse]
    total: int
