"""Car damage assessment service using Azure OpenAI GPT-4o with vision."""

from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any

from openai import AsyncAzureOpenAI
from PIL import Image

from app.config import settings
from app.models.schemas import DamageAssessment, DamagePart

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert auto-insurance damage assessor. You will be shown a photograph
of a damaged vehicle. Analyze the image and produce a structured damage report.

Rules:
- Identify every visibly damaged part (e.g. front bumper, hood, left fender,
  headlight, windshield, door panel, trunk lid, etc.).
- For each part state the severity (minor / moderate / severe), recommended
  repair type (repair, replace, repaint), and an estimated repair cost range
  in USD.
- Provide an overall severity rating and total estimated cost range.
- If you can identify the vehicle make, model, color, or year, include it.
- Be concise but thorough.

Respond ONLY with valid JSON matching this schema (no markdown fences):
{
  "vehicle_description": "string",
  "overall_severity": "minor | moderate | severe",
  "total_cost_low": number,
  "total_cost_high": number,
  "parts": [
    {
      "part_name": "string",
      "severity": "minor | moderate | severe",
      "repair_type": "repair | replace | repaint",
      "cost_low": number,
      "cost_high": number,
      "description": "string"
    }
  ],
  "summary": "string"
}
"""


class DamageAssessmentService:
    """Calls Azure OpenAI GPT-4o with vision to assess car damage."""

    def __init__(self) -> None:
        self._client: AsyncAzureOpenAI | None = None

    def load(self) -> None:
        if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
            logger.warning(
                "Azure OpenAI credentials not configured – "
                "damage assessment will return a placeholder."
            )
            return
        self._client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        logger.info("Azure OpenAI client ready (deployment=%s)", settings.azure_openai_deployment)

    async def assess(self, image: Image.Image) -> DamageAssessment:
        if self._client is None:
            return _placeholder_assessment()

        b64 = _image_to_base64(image)

        response = await self._client.chat.completions.create(
            model=settings.azure_openai_deployment,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Assess the damage visible in this car photo and "
                                "return the JSON report."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            max_tokens=2048,
            temperature=0.2,
        )

        raw = response.choices[0].message.content or ""
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        data: dict[str, Any] = json.loads(raw)
        return DamageAssessment(
            vehicle_description=data.get("vehicle_description", "Unknown vehicle"),
            overall_severity=data.get("overall_severity", "moderate"),
            total_cost_low=data.get("total_cost_low", 0),
            total_cost_high=data.get("total_cost_high", 0),
            parts=[DamagePart(**p) for p in data.get("parts", [])],
            summary=data.get("summary", ""),
        )


def _image_to_base64(image: Image.Image) -> str:
    buf = io.BytesIO()
    rgb = image.convert("RGB")
    rgb.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode()


def _placeholder_assessment() -> DamageAssessment:
    """Return a realistic placeholder when Azure OpenAI is not configured."""
    return DamageAssessment(
        vehicle_description="Unknown vehicle (Azure OpenAI not configured)",
        overall_severity="moderate",
        total_cost_low=1500.0,
        total_cost_high=4500.0,
        parts=[
            DamagePart(
                part_name="Front Bumper",
                severity="moderate",
                repair_type="replace",
                cost_low=800.0,
                cost_high=2000.0,
                description="Placeholder – configure AZURE_OPENAI_* env vars for real assessment",
            ),
            DamagePart(
                part_name="Hood",
                severity="minor",
                repair_type="repaint",
                cost_low=400.0,
                cost_high=1200.0,
                description="Placeholder – configure AZURE_OPENAI_* env vars for real assessment",
            ),
            DamagePart(
                part_name="Left Headlight",
                severity="moderate",
                repair_type="replace",
                cost_low=300.0,
                cost_high=1300.0,
                description="Placeholder – configure AZURE_OPENAI_* env vars for real assessment",
            ),
        ],
        summary="Placeholder assessment. Set Azure OpenAI credentials for real results.",
    )
