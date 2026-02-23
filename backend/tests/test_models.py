"""Tests for SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock
import sys

# Stub heavy deps so models can be imported without a real DB
for mod in ("torch", "trimesh", "trimesh.visual", "trimesh.visual.material",
            "xatlas", "numpy", "einops", "rembg", "rembg.sessions"):
    sys.modules.setdefault(mod, MagicMock())
fake_tsr = MagicMock()
sys.modules.setdefault("tsr", fake_tsr)
sys.modules.setdefault("tsr.system", fake_tsr.system)
sys.modules.setdefault("tsr.bake_texture", fake_tsr.bake_texture)

from app.models.assessment import Assessment, AssessmentStatus
from app.models.damage_item import DamageItem, DamageSeverity, VehicleZone
from app.models.processing_job import ProcessingJob, ProcessingStage, JobStatus


class TestAssessmentModel:
    def test_create_assessment_with_fields(self):
        a = Assessment(
            claim_number="CLM-001",
            agent_id="agent_jsmith",
            vehicle_year=2022,
            vehicle_make="Toyota",
            vehicle_model="Camry",
            status=AssessmentStatus.CREATED,
        )
        assert a.claim_number == "CLM-001"
        assert a.agent_id == "agent_jsmith"
        assert a.vehicle_year == 2022
        assert a.vehicle_make == "Toyota"
        assert a.vehicle_model == "Camry"
        assert a.status == AssessmentStatus.CREATED

    def test_assessment_status_enum_values(self):
        assert AssessmentStatus.CREATED.value == "created"
        assert AssessmentStatus.UPLOADING.value == "uploading"
        assert AssessmentStatus.EXTRACTING_FRAMES.value == "extracting_frames"
        assert AssessmentStatus.SPLATTING.value == "splatting"
        assert AssessmentStatus.ANALYZING.value == "analyzing"
        assert AssessmentStatus.COMPLETE.value == "complete"
        assert AssessmentStatus.FAILED.value == "failed"

    def test_assessment_all_statuses_are_strings(self):
        for s in AssessmentStatus:
            assert isinstance(s.value, str)


class TestDamageItemModel:
    def test_create_damage_item(self):
        d = DamageItem(
            assessment_id=uuid.uuid4(),
            damage_id="DMG-001",
            location="Front bumper, driver side",
            vehicle_zone=VehicleZone.FRONT_LEFT,
            damage_type="Dent with paint transfer",
            severity=DamageSeverity.MODERATE,
            description="8-inch dent on front bumper cover",
            affected_parts=["Front bumper cover"],
            repair_method="Replace bumper cover + repaint",
            estimated_cost_low=800,
            estimated_cost_high=1200,
            confidence_score=0.85,
            reference_frame_paths=["frame_0042.jpg"],
        )
        assert d.damage_id == "DMG-001"
        assert d.severity == DamageSeverity.MODERATE
        assert d.vehicle_zone == VehicleZone.FRONT_LEFT

    def test_vehicle_zone_enum_values(self):
        zones = {z.value for z in VehicleZone}
        assert "front_left" in zones
        assert "rear_center" in zones
        assert "roof" in zones
        assert "interior_front" in zones
        assert len(zones) == 11

    def test_severity_enum_values(self):
        assert DamageSeverity.MINOR.value == "minor"
        assert DamageSeverity.MODERATE.value == "moderate"
        assert DamageSeverity.SEVERE.value == "severe"


class TestProcessingJobModel:
    def test_create_processing_job(self):
        j = ProcessingJob(
            assessment_id=uuid.uuid4(),
            stage=ProcessingStage.FRAME_EXTRACTION,
            status=JobStatus.QUEUED,
        )
        assert j.stage == ProcessingStage.FRAME_EXTRACTION
        assert j.status == JobStatus.QUEUED

    def test_processing_stage_enum(self):
        assert ProcessingStage.FRAME_EXTRACTION.value == "frame_extraction"
        assert ProcessingStage.SPLATTING.value == "splatting"
        assert ProcessingStage.ANALYSIS.value == "analysis"
        assert ProcessingStage.REPORT_GENERATION.value == "report_generation"

    def test_job_status_enum(self):
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETE.value == "complete"
        assert JobStatus.FAILED.value == "failed"
