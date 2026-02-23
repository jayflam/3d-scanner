"""Tests for the report generation service."""

from pathlib import Path

import pytest

from app.services.damage_analyzer import (
    DamageItem,
    DamageReport,
    Severity,
    VehicleZone,
)
from app.services.report_generator import ReportGeneratorService


@pytest.fixture
def sample_report() -> DamageReport:
    return DamageReport(
        damages=[
            DamageItem(
                damage_id="DMG-001",
                location="Front bumper, driver side",
                vehicle_zone=VehicleZone.FRONT_LEFT,
                damage_type="Dent with paint transfer",
                severity=Severity.MODERATE,
                description="8-inch dent on front bumper cover with white paint transfer.",
                affected_parts=["Front bumper cover", "Bumper reinforcement bar"],
                repair_method="Replace bumper cover + repaint",
                estimated_cost_low=800,
                estimated_cost_high=1200,
                confidence_score=0.85,
                reference_frames=["frame_0042.jpg", "frame_0043.jpg"],
            ),
            DamageItem(
                damage_id="DMG-002",
                location="Left headlight",
                vehicle_zone=VehicleZone.FRONT_LEFT,
                damage_type="Crack",
                severity=Severity.SEVERE,
                description="Cracked headlight lens, needs replacement.",
                affected_parts=["Headlight assembly"],
                repair_method="Replace",
                estimated_cost_low=400,
                estimated_cost_high=900,
                confidence_score=0.90,
                reference_frames=["frame_0044.jpg"],
            ),
        ],
        total_damage_count=2,
        total_estimate_low=1200,
        total_estimate_high=2100,
        recommendation="Repair -- estimate below total loss threshold",
        pre_existing_damage_flags=["Minor scratch on rear bumper appears weathered"],
        narrative="Vehicle sustained moderate frontal damage consistent with a low-speed collision.",
    )


@pytest.fixture
def generator():
    return ReportGeneratorService()


class TestGenerateJsonReport:
    def test_json_report_structure(
        self,
        generator: ReportGeneratorService,
        sample_report: DamageReport,
    ):
        result = generator.generate_json_report(
            damage_report=sample_report,
            assessment_id="test-uuid",
            claim_number="CLM-2026-001",
            vehicle_year=2022,
            vehicle_make="Toyota",
            vehicle_model="Camry",
            vin="4T1BF1FK5CU512345",
            agent_id="agent_jsmith",
        )

        assert result["assessment_id"] == "test-uuid"
        assert result["claim_number"] == "CLM-2026-001"
        assert result["vehicle"]["year"] == 2022
        assert result["vehicle"]["make"] == "Toyota"
        assert len(result["damages"]) == 2
        assert result["summary"]["total_damage_count"] == 2
        assert result["summary"]["total_estimate_low"] == 1200
        assert result["summary"]["total_estimate_high"] == 2100
        assert "generated_at" in result

    def test_empty_report(self, generator: ReportGeneratorService):
        empty = DamageReport()
        result = generator.generate_json_report(empty)
        assert result["damages"] == []
        assert result["summary"]["total_damage_count"] == 0


class TestRenderHtml:
    def test_html_contains_vehicle_info(
        self,
        generator: ReportGeneratorService,
        sample_report: DamageReport,
    ):
        html = generator._render_html(
            damage_report=sample_report,
            assessment_id="test-uuid",
            claim_number="CLM-2026-001",
            vehicle_year=2022,
            vehicle_make="Toyota",
            vehicle_model="Camry",
            vin="4T1BF1FK5CU512345",
            agent_id="agent_jsmith",
        )

        assert "Toyota" in html
        assert "Camry" in html
        assert "2022" in html
        assert "CLM-2026-001" in html
        assert "4T1BF1FK5CU512345" in html

    def test_html_contains_damage_items(
        self,
        generator: ReportGeneratorService,
        sample_report: DamageReport,
    ):
        html = generator._render_html(
            damage_report=sample_report,
            assessment_id="",
            claim_number="",
            vehicle_year=0,
            vehicle_make="",
            vehicle_model="",
            vin="",
            agent_id="",
        )

        assert "DMG-001" in html
        assert "DMG-002" in html
        assert "Front bumper, driver side" in html
        assert "Dent with paint transfer" in html
        assert "badge-moderate" in html
        assert "badge-severe" in html

    def test_html_contains_pre_existing_flags(
        self,
        generator: ReportGeneratorService,
        sample_report: DamageReport,
    ):
        html = generator._render_html(
            damage_report=sample_report,
            assessment_id="",
            claim_number="",
            vehicle_year=0,
            vehicle_make="",
            vehicle_model="",
            vin="",
            agent_id="",
        )

        assert "Pre-Existing Damage Flags" in html
        assert "rear bumper appears weathered" in html

    def test_html_no_pre_existing_when_empty(
        self,
        generator: ReportGeneratorService,
    ):
        report = DamageReport(
            damages=[],
            total_damage_count=0,
            total_estimate_low=0,
            total_estimate_high=0,
            pre_existing_damage_flags=[],
        )
        html = generator._render_html(
            damage_report=report,
            assessment_id="",
            claim_number="",
            vehicle_year=0,
            vehicle_make="",
            vehicle_model="",
            vin="",
            agent_id="",
        )

        assert "Pre-Existing Damage Flags" not in html
