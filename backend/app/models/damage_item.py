"""SQLAlchemy ORM model for individual damage items."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class VehicleZone(str, enum.Enum):
    FRONT_LEFT = "front_left"
    FRONT_RIGHT = "front_right"
    FRONT_CENTER = "front_center"
    REAR_LEFT = "rear_left"
    REAR_RIGHT = "rear_right"
    REAR_CENTER = "rear_center"
    SIDE_LEFT = "side_left"
    SIDE_RIGHT = "side_right"
    ROOF = "roof"
    INTERIOR_FRONT = "interior_front"
    INTERIOR_REAR = "interior_rear"


class DamageSeverity(str, enum.Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


class DamageItem(Base):
    __tablename__ = "damage_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    damage_id: Mapped[str] = mapped_column(String(20), nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    vehicle_zone: Mapped[VehicleZone] = mapped_column(
        Enum(VehicleZone, name="vehicle_zone"), nullable=False
    )
    damage_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[DamageSeverity] = mapped_column(
        Enum(DamageSeverity, name="damage_severity"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_parts: Mapped[dict | list] = mapped_column(JSONB, default=list)
    repair_method: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_cost_low: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    estimated_cost_high: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    reference_frame_paths: Mapped[dict | list] = mapped_column(JSONB, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    assessment: Mapped["Assessment"] = relationship(
        "Assessment", back_populates="damage_items"
    )


from app.models.assessment import Assessment  # noqa: E402
