"""Tests for Pydantic v2 API schemas."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

# Stub heavy deps
for mod in ("torch", "trimesh", "trimesh.visual", "trimesh.visual.material",
            "xatlas", "numpy", "einops", "rembg", "rembg.sessions"):
    sys.modules.setdefault(mod, MagicMock())
fake_tsr = MagicMock()
sys.modules.setdefault("tsr", fake_tsr)
sys.modules.setdefault("tsr.system", fake_tsr.system)
sys.modules.setdefault("tsr.bake_texture", fake_tsr.bake_texture)

import pytest
from pydantic import ValidationError

from app.schemas.assessment import (
    AssessmentCreateResponse,
    AssessmentListResponse,
    AssessmentResponse,
    CreateAssessment,
    PipelineStatus,
    VehicleInfo,
)
from app.schemas.damage import DamageItemResponse, DamageListResponse
from app.schemas.report import ReportResponse, ReportSummary, VehicleInfo as ReportVehicleInfo


class TestCreateAssessment:
    def test_valid_creation(self):
        data = CreateAssessment(
            claim_number="CLM-2026-00142",
            agent_id="agent_jsmith",
            vehicle_year=2022,
            vehicle_make="Toyota",
            vehicle_model="Camry",
        )
        assert data.claim_number == "CLM-2026-00142"
        assert data.vin == ""
        assert data.gps_latitude is None

    def test_full_creation(self):
        data = CreateAssessment(
            claim_number="CLM-001",
            agent_id="agent_1",
            vehicle_year=2022,
            vehicle_make="Toyota",
            vehicle_model="Camry",
            vin="4T1BF1FK5CU512345",
            gps_latitude=33.749,
            gps_longitude=-84.388,
        )
        assert data.vin == "4T1BF1FK5CU512345"
        assert data.gps_latitude == 33.749

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            CreateAssessment(
                agent_id="agent_1",
                vehicle_year=2022,
                vehicle_make="Toyota",
                vehicle_model="Camry",
            )


class TestAssessmentResponse:
    def test_serialization(self):
        now = datetime.now(timezone.utc)
        resp = AssessmentResponse(
            id=uuid4(),
            status="created",
            claim_number="CLM-001",
            agent_id="agent_1",
            vin="",
            vehicle=VehicleInfo(year=2022, make="Toyota", model="Camry"),
            pipeline=PipelineStatus(),
            frame_count={"exterior": 0, "interior": 0},
            splat_ready={"exterior": False, "interior": False},
            created_at=now,
            updated_at=now,
        )
        data = resp.model_dump()
        assert data["status"] == "created"
        assert data["vehicle"]["year"] == 2022
        assert data["pipeline"]["exterior_video"] == "pending"


class TestDamageItemResponse:
    def test_serialization(self):
        now = datetime.now(timezone.utc)
        resp = DamageItemResponse(
            id=uuid4(),
            assessment_id=uuid4(),
            damage_id="DMG-001",
            location="Front bumper",
            vehicle_zone="front_left",
            damage_type="Dent",
            severity="moderate",
            description="8-inch dent",
            affected_parts=["Front bumper cover"],
            repair_method="Replace",
            estimated_cost_low=800.0,
            estimated_cost_high=1200.0,
            confidence_score=0.85,
            reference_frame_paths=["frame_0042.jpg"],
            created_at=now,
        )
        data = resp.model_dump()
        assert data["damage_id"] == "DMG-001"
        assert data["severity"] == "moderate"
        assert len(data["affected_parts"]) == 1


class TestReportResponse:
    def test_report_serialization(self):
        now = datetime.now(timezone.utc)
        resp = ReportResponse(
            assessment_id=uuid4(),
            vehicle=ReportVehicleInfo(year=2022, make="Toyota", model="Camry", vin=""),
            damages=[],
            summary=ReportSummary(
                total_damage_count=0,
                total_estimate_low=0,
                total_estimate_high=0,
                recommendation="No damage detected",
                narrative="Vehicle appears undamaged.",
            ),
            generated_at=now,
        )
        data = resp.model_dump()
        assert data["summary"]["total_damage_count"] == 0
