"""Tests for the enhanced damage analyzer service."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.damage_analyzer import (
    DamageAnalyzerService,
    DamageItem,
    DamageReport,
    Severity,
    VehicleZone,
    _parse_json_response,
    assign_zone,
    group_frames_by_zone,
)


class TestAssignZone:
    def test_first_frame_is_front_center(self):
        assert assign_zone(0, 100) == VehicleZone.FRONT_CENTER

    def test_quarter_is_side_right(self):
        assert assign_zone(25, 100) == VehicleZone.SIDE_RIGHT

    def test_half_is_rear_center(self):
        assert assign_zone(50, 100) == VehicleZone.REAR_CENTER

    def test_three_quarter_is_side_left(self):
        assert assign_zone(75, 100) == VehicleZone.SIDE_LEFT

    def test_last_frame_is_front_center(self):
        assert assign_zone(95, 100) == VehicleZone.FRONT_CENTER

    def test_interior_first_half(self):
        assert assign_zone(10, 100, is_interior=True) == VehicleZone.INTERIOR_FRONT

    def test_interior_second_half(self):
        assert assign_zone(75, 100, is_interior=True) == VehicleZone.INTERIOR_REAR

    def test_zero_total_returns_default(self):
        assert assign_zone(0, 0) == VehicleZone.FRONT_CENTER


class TestGroupFramesByZone:
    def test_groups_exterior_frames(self, tmp_path: Path):
        frames = [tmp_path / f"frame_{i:04d}.jpg" for i in range(20)]
        zones = group_frames_by_zone(frames)

        # Should have multiple zones populated
        assert len(zones) > 1
        # Total frames across zones should equal input
        total = sum(len(v) for v in zones.values())
        assert total == 20

    def test_groups_interior_frames(self, tmp_path: Path):
        frames = [tmp_path / f"frame_{i:04d}.jpg" for i in range(10)]
        zones = group_frames_by_zone(frames, is_interior=True)

        # Interior should only have INTERIOR_FRONT and INTERIOR_REAR
        for zone in zones:
            assert zone in (VehicleZone.INTERIOR_FRONT, VehicleZone.INTERIOR_REAR)


class TestParseJsonResponse:
    def test_parses_clean_json(self):
        raw = '{"damages": [], "narrative": "test"}'
        result = _parse_json_response(raw)
        assert result == {"damages": [], "narrative": "test"}

    def test_strips_markdown_fences(self):
        raw = '```json\n{"damages": []}\n```'
        result = _parse_json_response(raw)
        assert result == {"damages": []}

    def test_strips_plain_fences(self):
        raw = '```\n{"damages": []}\n```'
        result = _parse_json_response(raw)
        assert result == {"damages": []}

    def test_invalid_json_returns_none(self):
        assert _parse_json_response("not json at all") is None


class TestDamageItem:
    def test_valid_damage_item(self):
        item = DamageItem(
            damage_id="DMG-001",
            location="Front bumper",
            vehicle_zone=VehicleZone.FRONT_CENTER,
            damage_type="Dent",
            severity=Severity.MODERATE,
            description="8-inch dent on front bumper",
            affected_parts=["Front bumper cover"],
            repair_method="Replace",
            estimated_cost_low=800,
            estimated_cost_high=1200,
            confidence_score=0.85,
            reference_frames=["frame_0001.jpg"],
        )
        assert item.damage_id == "DMG-001"
        assert item.confidence_score == 0.85

    def test_confidence_score_bounds(self):
        with pytest.raises(Exception):
            DamageItem(
                damage_id="DMG-001",
                location="test",
                vehicle_zone=VehicleZone.FRONT_CENTER,
                damage_type="test",
                severity=Severity.MINOR,
                description="test",
                confidence_score=1.5,  # out of bounds
            )


class TestDamageAnalyzerService:
    def test_placeholder_when_no_client(self):
        """Should return placeholder when Azure OpenAI is not configured."""
        import asyncio

        service = DamageAnalyzerService()
        # Don't call load() -- client stays None
        report = asyncio.get_event_loop().run_until_complete(
            service.analyze(frames=[])
        )
        assert isinstance(report, DamageReport)
        assert report.total_damage_count == 2
        assert report.damages[0].damage_id == "DMG-001"

    @pytest.mark.asyncio
    async def test_analyze_calls_gpt4o(self, tmp_path: Path):
        """When client is available, should call GPT-4o for each zone batch."""
        service = DamageAnalyzerService(max_frames_per_batch=4)

        # Create mock client
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"damages": [{"damage_id": "DMG-001", "location": "Front bumper", "vehicle_zone": "front_center", "damage_type": "Dent", "severity": "moderate", "description": "Test damage", "affected_parts": ["Bumper"], "repair_method": "Replace", "estimated_cost_low": 500, "estimated_cost_high": 800, "confidence_score": 0.9, "reference_frames": ["frame_0001.jpg"]}], "pre_existing_damage_flags": [], "narrative": "Test narrative"}'
                )
            )
        ]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        # Create test frame files
        frames = []
        for i in range(5):
            f = tmp_path / f"frame_{i:04d}.jpg"
            f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # minimal JPEG header
            frames.append(f)

        report = await service.analyze(
            frames=frames,
            vehicle_year=2022,
            vehicle_make="Toyota",
            vehicle_model="Camry",
        )

        assert isinstance(report, DamageReport)
        assert mock_client.chat.completions.create.called
        # Should have at least one damage item from our mock
        assert report.total_damage_count >= 1

    def test_sample_frames_under_limit(self):
        service = DamageAnalyzerService(max_frames_per_batch=6)
        frames = [Path(f"frame_{i}.jpg") for i in range(4)]
        sampled = service._sample_frames(frames, 6)
        assert sampled == frames

    def test_sample_frames_over_limit(self):
        service = DamageAnalyzerService(max_frames_per_batch=6)
        frames = [Path(f"frame_{i}.jpg") for i in range(20)]
        sampled = service._sample_frames(frames, 6)
        assert len(sampled) == 6
        # Should be evenly distributed
        assert sampled[0] == frames[0]
        assert sampled[-1] == frames[16]  # int(5 * 20/6) = 16
