"""Enhanced zone-based AI damage analysis using Azure OpenAI GPT-4o.

Organizes extracted frames by estimated vehicle zone, batches them
(4-8 per API call), and uses the enhanced prompt from the project plan
to produce structured damage assessments with confidence scores.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class VehicleZone(str, Enum):
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


class Severity(str, Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


class DamageItem(BaseModel):
    damage_id: str = Field(description="Human-readable ID like DMG-001")
    location: str = Field(description="Specific panel/area of vehicle")
    vehicle_zone: VehicleZone
    damage_type: str = Field(description="E.g. dent, scratch, crack, shatter")
    severity: Severity
    description: str = Field(description="Detailed AI-generated description")
    affected_parts: list[str] = Field(default_factory=list)
    repair_method: str = ""
    estimated_cost_low: float = 0.0
    estimated_cost_high: float = 0.0
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.5)
    reference_frames: list[str] = Field(default_factory=list)


class DamageReport(BaseModel):
    damages: list[DamageItem] = Field(default_factory=list)
    total_damage_count: int = 0
    total_estimate_low: float = 0.0
    total_estimate_high: float = 0.0
    recommendation: str = ""
    pre_existing_damage_flags: list[str] = Field(default_factory=list)
    narrative: str = ""


# ---------------------------------------------------------------------------
# Zone assignment heuristic
# ---------------------------------------------------------------------------

# Approximate zone assignment by frame position in sequence.
# For a walkaround video, frames are roughly ordered:
# front -> right side -> rear -> left side
EXTERIOR_ZONE_MAP: list[tuple[float, float, VehicleZone]] = [
    (0.00, 0.10, VehicleZone.FRONT_CENTER),
    (0.10, 0.20, VehicleZone.FRONT_RIGHT),
    (0.20, 0.35, VehicleZone.SIDE_RIGHT),
    (0.35, 0.45, VehicleZone.REAR_RIGHT),
    (0.45, 0.55, VehicleZone.REAR_CENTER),
    (0.55, 0.65, VehicleZone.REAR_LEFT),
    (0.65, 0.80, VehicleZone.SIDE_LEFT),
    (0.80, 0.90, VehicleZone.FRONT_LEFT),
    (0.90, 1.00, VehicleZone.FRONT_CENTER),
]

INTERIOR_ZONE_MAP: list[tuple[float, float, VehicleZone]] = [
    (0.00, 0.50, VehicleZone.INTERIOR_FRONT),
    (0.50, 1.00, VehicleZone.INTERIOR_REAR),
]


def assign_zone(
    frame_index: int,
    total_frames: int,
    is_interior: bool = False,
) -> VehicleZone:
    """Estimate vehicle zone from frame position in the video sequence."""
    if total_frames == 0:
        return VehicleZone.FRONT_CENTER
    ratio = frame_index / total_frames
    zone_map = INTERIOR_ZONE_MAP if is_interior else EXTERIOR_ZONE_MAP
    for lo, hi, zone in zone_map:
        if lo <= ratio < hi:
            return zone
    return zone_map[-1][2]


def group_frames_by_zone(
    frames: list[Path],
    is_interior: bool = False,
) -> dict[VehicleZone, list[Path]]:
    """Group a sorted list of frames into vehicle zones."""
    zones: dict[VehicleZone, list[Path]] = {}
    total = len(frames)
    for i, frame in enumerate(frames):
        zone = assign_zone(i, total, is_interior)
        zones.setdefault(zone, []).append(frame)
    return zones


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """\
You are an expert automotive damage assessor with 20 years of experience \
in vehicle collision repair estimation. You are analyzing images of a \
damaged vehicle captured by an insurance field agent.

Vehicle Information:
- Year: {vehicle_year}
- Make: {vehicle_make}
- Model: {vehicle_model}
- VIN: {vin}

Analyze the provided images and identify ALL visible damage. For each \
damage instance, provide:

1. Location -- specific panel/area of vehicle
2. Vehicle Zone -- categorize into: front_left, front_right, front_center, \
   rear_left, rear_right, rear_center, side_left, side_right, roof, \
   interior_front, interior_rear
3. Damage Type -- dent, scratch, crack, shatter, deformation, paint damage, \
   missing part, etc.
4. Severity -- minor, moderate, or severe
5. Description -- detailed description of the damage
6. Affected Parts -- list of OEM parts affected
7. Repair Method -- recommended repair approach (PDR, repaint, replace, etc.)
8. Cost Estimate -- low and high range in USD based on current labor and \
   parts pricing for this vehicle
9. Confidence Score -- your confidence in this assessment (0.0 to 1.0)
10. Reference -- which image(s) show this damage

Also flag any damage that appears to be pre-existing (weathered, oxidized, \
inconsistent with reported incident).

Respond ONLY with valid JSON matching this schema (no markdown fences):
{{
  "damages": [
    {{
      "damage_id": "DMG-001",
      "location": "string",
      "vehicle_zone": "string",
      "damage_type": "string",
      "severity": "minor|moderate|severe",
      "description": "string",
      "affected_parts": ["string"],
      "repair_method": "string",
      "estimated_cost_low": number,
      "estimated_cost_high": number,
      "confidence_score": number,
      "reference_frames": ["string"]
    }}
  ],
  "pre_existing_damage_flags": ["string"],
  "narrative": "string"
}}
"""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DamageAnalyzerService:
    """Enhanced zone-based damage analysis using GPT-4o multimodal."""

    def __init__(self, max_frames_per_batch: int = 6) -> None:
        self._client = None
        self._max_frames_per_batch = max_frames_per_batch

    def load(self) -> None:
        """Initialize the Azure OpenAI client."""
        if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
            logger.warning(
                "Azure OpenAI credentials not configured -- "
                "damage analysis will return placeholders."
            )
            return
        from openai import AsyncAzureOpenAI

        self._client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        logger.info(
            "DamageAnalyzer ready (deployment=%s)",
            settings.azure_openai_deployment,
        )

    async def analyze(
        self,
        frames: list[Path],
        vehicle_year: int = 0,
        vehicle_make: str = "Unknown",
        vehicle_model: str = "Unknown",
        vin: str = "",
        is_interior: bool = False,
    ) -> DamageReport:
        """Run full zone-based damage analysis on a set of frames.

        Args:
            frames: Sorted list of frame image paths.
            vehicle_year: Vehicle model year.
            vehicle_make: Vehicle manufacturer.
            vehicle_model: Vehicle model name.
            vin: Vehicle Identification Number.
            is_interior: Whether these are interior frames.

        Returns:
            Aggregated DamageReport with all detected damage items.
        """
        if self._client is None:
            return _placeholder_report()

        # Group frames by zone
        zones = group_frames_by_zone(frames, is_interior)

        all_damages: list[DamageItem] = []
        all_pre_existing: list[str] = []
        all_narratives: list[str] = []
        damage_counter = 0

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            vehicle_year=vehicle_year,
            vehicle_make=vehicle_make,
            vehicle_model=vehicle_model,
            vin=vin or "N/A",
        )

        for zone, zone_frames in zones.items():
            # Sample frames if zone has too many
            sampled = self._sample_frames(zone_frames, self._max_frames_per_batch)

            logger.info(
                "Analyzing zone %s: %d frames (sampled from %d)",
                zone.value,
                len(sampled),
                len(zone_frames),
            )

            result = await self._analyze_batch(
                system_prompt=system_prompt,
                frames=sampled,
                zone_hint=zone,
                damage_id_start=damage_counter,
            )

            if result:
                all_damages.extend(result.get("damages", []))
                all_pre_existing.extend(result.get("pre_existing_damage_flags", []))
                if result.get("narrative"):
                    all_narratives.append(result["narrative"])
                damage_counter += len(result.get("damages", []))

        # Build aggregated report
        parsed_damages = []
        for d in all_damages:
            try:
                parsed_damages.append(DamageItem(**d) if isinstance(d, dict) else d)
            except Exception:
                logger.warning("Skipping invalid damage item: %s", d)

        total_low = sum(d.estimated_cost_low for d in parsed_damages)
        total_high = sum(d.estimated_cost_high for d in parsed_damages)

        recommendation = "No damage detected"
        if parsed_damages:
            if total_high > 15000:
                recommendation = "Total loss evaluation recommended"
            elif total_high > 5000:
                recommendation = "Significant repair required -- consider total loss threshold"
            else:
                recommendation = "Repair -- estimate below total loss threshold"

        return DamageReport(
            damages=parsed_damages,
            total_damage_count=len(parsed_damages),
            total_estimate_low=total_low,
            total_estimate_high=total_high,
            recommendation=recommendation,
            pre_existing_damage_flags=all_pre_existing,
            narrative=" ".join(all_narratives) if all_narratives else "",
        )

    async def _analyze_batch(
        self,
        system_prompt: str,
        frames: list[Path],
        zone_hint: VehicleZone,
        damage_id_start: int,
    ) -> dict[str, Any] | None:
        """Send a batch of frames to GPT-4o for analysis."""
        # Build content array with images
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"These {len(frames)} images show the {zone_hint.value} zone "
                    f"of the vehicle. Identify all visible damage. "
                    f"Start damage IDs from DMG-{damage_id_start + 1:03d}."
                ),
            },
        ]

        for frame_path in frames:
            b64 = _encode_frame(frame_path)
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64}",
                        "detail": "high",
                    },
                }
            )

        try:
            response = await self._client.chat.completions.create(
                model=settings.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content},
                ],
                max_tokens=4096,
                temperature=0.2,
            )

            raw = response.choices[0].message.content or ""
            return _parse_json_response(raw)

        except Exception:
            logger.exception("GPT-4o analysis failed for zone %s", zone_hint.value)
            return None

    @staticmethod
    def _sample_frames(frames: list[Path], max_count: int) -> list[Path]:
        """Evenly sample frames down to max_count."""
        if len(frames) <= max_count:
            return frames
        step = len(frames) / max_count
        return [frames[int(i * step)] for i in range(max_count)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _encode_frame(frame_path: Path) -> str:
    """Read and base64-encode a JPEG frame."""
    return base64.b64encode(frame_path.read_bytes()).decode()


def _parse_json_response(raw: str) -> dict[str, Any] | None:
    """Extract JSON from GPT response, handling markdown fences."""
    raw = raw.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse GPT-4o JSON response: %s", raw[:500])
        return None


def _placeholder_report() -> DamageReport:
    """Return a placeholder report when Azure OpenAI is not configured."""
    return DamageReport(
        damages=[
            DamageItem(
                damage_id="DMG-001",
                location="Front bumper, driver side",
                vehicle_zone=VehicleZone.FRONT_LEFT,
                damage_type="Dent with paint transfer",
                severity=Severity.MODERATE,
                description=(
                    "Placeholder -- configure AZURE_OPENAI_* env vars for real analysis. "
                    "Approximately 8-inch dent on front bumper cover."
                ),
                affected_parts=["Front bumper cover", "Bumper reinforcement bar (inspect)"],
                repair_method="Replace bumper cover + repaint",
                estimated_cost_low=800.0,
                estimated_cost_high=1200.0,
                confidence_score=0.85,
                reference_frames=[],
            ),
            DamageItem(
                damage_id="DMG-002",
                location="Left headlight assembly",
                vehicle_zone=VehicleZone.FRONT_LEFT,
                damage_type="Crack",
                severity=Severity.MODERATE,
                description="Placeholder -- cracked headlight lens.",
                affected_parts=["Headlight assembly"],
                repair_method="Replace headlight assembly",
                estimated_cost_low=400.0,
                estimated_cost_high=900.0,
                confidence_score=0.80,
                reference_frames=[],
            ),
        ],
        total_damage_count=2,
        total_estimate_low=1200.0,
        total_estimate_high=2100.0,
        recommendation="Repair -- estimate below total loss threshold",
        pre_existing_damage_flags=[],
        narrative="Placeholder assessment. Set Azure OpenAI credentials for real results.",
    )
