from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PREPROCESSING = "preprocessing"
    GENERATING_3D = "generating_3d"
    ASSESSING_DAMAGE = "assessing_damage"
    COMPLETE = "complete"
    FAILED = "failed"


class DamagePart(BaseModel):
    part_name: str = Field(description="e.g. front bumper, hood, left fender")
    severity: str = Field(description="minor, moderate, or severe")
    repair_type: str = Field(description="e.g. repair, replace, repaint")
    cost_low: float = Field(description="Low end of estimated repair cost in USD")
    cost_high: float = Field(description="High end of estimated repair cost in USD")
    description: str = Field(description="Brief description of the damage")


class DamageAssessment(BaseModel):
    vehicle_description: str = Field(description="Make/model/color if identifiable")
    overall_severity: str = Field(description="minor, moderate, or severe")
    total_cost_low: float
    total_cost_high: float
    parts: List[DamagePart]
    summary: str = Field(description="Human-readable summary of assessment")


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    progress_pct: int = Field(ge=0, le=100)
    message: str = ""


class JobResult(BaseModel):
    job_id: str
    status: JobStatus
    model_url: str = Field(description="URL to download the GLB 3D model")
    assessment: Optional[DamageAssessment] = None


class UploadResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class ProgressUpdate(BaseModel):
    job_id: str
    status: JobStatus
    progress_pct: int
    message: str
