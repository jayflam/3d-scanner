"""SQLAlchemy ORM model for vehicle damage assessments."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class AssessmentStatus(str, enum.Enum):
    CREATED = "created"
    UPLOADING = "uploading"
    EXTRACTING_FRAMES = "extracting_frames"
    SPLATTING = "splatting"
    ANALYZING = "analyzing"
    COMPLETE = "complete"
    FAILED = "failed"


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    claim_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    vin: Mapped[str] = mapped_column(String(17), default="")
    vehicle_year: Mapped[int] = mapped_column(Integer, nullable=False)
    vehicle_make: Mapped[str] = mapped_column(String(50), nullable=False)
    vehicle_model: Mapped[str] = mapped_column(String(50), nullable=False)

    status: Mapped[AssessmentStatus] = mapped_column(
        Enum(AssessmentStatus, name="assessment_status"),
        default=AssessmentStatus.CREATED,
        nullable=False,
    )

    exterior_video_blob_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    interior_video_blob_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    exterior_splat_blob_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    interior_splat_blob_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    exterior_frame_count: Mapped[int] = mapped_column(Integer, default=0)
    interior_frame_count: Mapped[int] = mapped_column(Integer, default=0)

    total_estimate_low: Mapped[float | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    total_estimate_high: Mapped[float | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    gps_latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    gps_longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    damage_items: Mapped[list["DamageItem"]] = relationship(
        "DamageItem", back_populates="assessment", cascade="all, delete-orphan"
    )
    processing_jobs: Mapped[list["ProcessingJob"]] = relationship(
        "ProcessingJob", back_populates="assessment", cascade="all, delete-orphan"
    )


# Import at bottom to avoid circular imports
from app.models.damage_item import DamageItem  # noqa: E402
from app.models.processing_job import ProcessingJob  # noqa: E402
