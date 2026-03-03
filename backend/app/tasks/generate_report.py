"""Celery task: generate JSON and PDF damage reports.

Fetches all damage items from DB, generates structured JSON report
and styled PDF, uploads both to Blob Storage.
"""

from __future__ import annotations

import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import redis

from app.config import settings
from app.services.blob_storage import blob_storage
from app.services.damage_analyzer import DamageItem, DamageReport, Severity, VehicleZone
from app.services.report_generator import ReportGeneratorService
from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)


def _publish_progress(assessment_id: str, stage: str, pct: int, message: str) -> None:
    """Publish progress update to Redis pub/sub channel."""
    try:
        r = redis.Redis.from_url(settings.redis_url)
        r.publish(
            f"insurascan:progress:{assessment_id}",
            json.dumps({
                "assessment_id": assessment_id,
                "stage": stage,
                "progress_pct": pct,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
        )
    except Exception:
        logger.debug("Failed to publish progress", exc_info=True)


def _get_assessment_with_damages(assessment_id: str) -> dict:
    """Fetch assessment info and all damage items from DB."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.models.assessment import Assessment
    from app.models.damage_item import DamageItem as DamageItemModel

    db_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
        "postgresql+psycopg2", "postgresql"
    )
    engine = create_engine(db_url)
    with Session(engine) as session:
        assessment = session.execute(
            select(Assessment).where(Assessment.id == assessment_id)
        ).scalar_one()

        damage_items = session.execute(
            select(DamageItemModel).where(
                DamageItemModel.assessment_id == assessment_id
            )
        ).scalars().all()

        return {
            "assessment_id": str(assessment.id),
            "claim_number": assessment.claim_number,
            "agent_id": assessment.agent_id,
            "vehicle_year": assessment.vehicle_year,
            "vehicle_make": assessment.vehicle_make,
            "vehicle_model": assessment.vehicle_model,
            "vin": assessment.vin,
            "total_estimate_low": float(assessment.total_estimate_low or 0),
            "total_estimate_high": float(assessment.total_estimate_high or 0),
            "damage_items": [
                {
                    "damage_id": d.damage_id,
                    "location": d.location,
                    "vehicle_zone": d.vehicle_zone.value,
                    "damage_type": d.damage_type,
                    "severity": d.severity.value,
                    "description": d.description,
                    "affected_parts": d.affected_parts or [],
                    "repair_method": d.repair_method,
                    "estimated_cost_low": float(d.estimated_cost_low),
                    "estimated_cost_high": float(d.estimated_cost_high),
                    "confidence_score": float(d.confidence_score),
                    "reference_frames": d.reference_frame_paths or [],
                }
                for d in damage_items
            ],
        }


def _update_db(assessment_id: str, **kwargs) -> None:
    """Synchronous DB update for Celery workers."""
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import Session

    from app.models.assessment import Assessment

    db_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
        "postgresql+psycopg2", "postgresql"
    )
    engine = create_engine(db_url)
    with Session(engine) as session:
        session.execute(
            update(Assessment).where(Assessment.id == assessment_id).values(**kwargs)
        )
        session.commit()


def _create_processing_job(
    assessment_id: str, stage: str, celery_task_id: str
) -> str:
    """Create a ProcessingJob record and return its ID."""
    import uuid

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models.processing_job import JobStatus, ProcessingJob, ProcessingStage

    db_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
        "postgresql+psycopg2", "postgresql"
    )
    engine = create_engine(db_url)
    with Session(engine) as session:
        job = ProcessingJob(
            id=uuid.uuid4(),
            assessment_id=assessment_id,
            stage=ProcessingStage(stage),
            status=JobStatus.RUNNING,
            celery_task_id=celery_task_id,
            started_at=datetime.now(timezone.utc),
        )
        session.add(job)
        session.commit()
        return str(job.id)


def _complete_processing_job(job_id: str, error: str | None = None) -> None:
    """Mark a ProcessingJob as complete or failed."""
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import Session

    from app.models.processing_job import JobStatus, ProcessingJob

    db_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
        "postgresql+psycopg2", "postgresql"
    )
    engine = create_engine(db_url)
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        values = {
            "status": JobStatus.FAILED if error else JobStatus.COMPLETE,
            "completed_at": now,
            "error_message": error,
        }
        session.execute(
            update(ProcessingJob).where(ProcessingJob.id == job_id).values(**values)
        )
        session.commit()


@celery.task(bind=True, name="app.tasks.generate_report.generate_report_task")
def generate_report_task(
    self,
    assessment_id: str,
) -> dict:
    """Fetch damage items from DB -> generate JSON + PDF -> upload to Blob.

    Args:
        assessment_id: UUID of the assessment.

    Returns:
        Dict with report blob paths.
    """
    job_id = _create_processing_job(
        assessment_id, "report_generation", self.request.id or ""
    )

    try:
        _publish_progress(
            assessment_id, "report_generation", 10,
            "Generating damage report...",
        )

        # 1. Fetch assessment data and damage items
        data = _get_assessment_with_damages(assessment_id)

        # 2. Build DamageReport from DB records
        damage_items = [
            DamageItem(
                damage_id=d["damage_id"],
                location=d["location"],
                vehicle_zone=VehicleZone(d["vehicle_zone"]),
                damage_type=d["damage_type"],
                severity=Severity(d["severity"]),
                description=d["description"],
                affected_parts=d["affected_parts"],
                repair_method=d["repair_method"],
                estimated_cost_low=d["estimated_cost_low"],
                estimated_cost_high=d["estimated_cost_high"],
                confidence_score=d["confidence_score"],
                reference_frames=d["reference_frames"],
            )
            for d in data["damage_items"]
        ]

        total_low = sum(d.estimated_cost_low for d in damage_items)
        total_high = sum(d.estimated_cost_high for d in damage_items)

        damage_report = DamageReport(
            damages=damage_items,
            total_damage_count=len(damage_items),
            total_estimate_low=total_low,
            total_estimate_high=total_high,
            recommendation=(
                "Total loss evaluation recommended" if total_high > 15000
                else "Significant repair required" if total_high > 5000
                else "Repair -- estimate below total loss threshold"
            ),
        )

        generator = ReportGeneratorService()

        # 3. Generate JSON report
        _publish_progress(
            assessment_id, "report_generation", 40,
            "Building JSON report...",
        )

        json_report = generator.generate_json_report(
            damage_report=damage_report,
            assessment_id=data["assessment_id"],
            claim_number=data["claim_number"],
            vehicle_year=data["vehicle_year"],
            vehicle_make=data["vehicle_make"],
            vehicle_model=data["vehicle_model"],
            vin=data["vin"],
            agent_id=data["agent_id"],
        )

        json_bytes = json.dumps(json_report, indent=2).encode()
        json_blob_path = blob_storage.upload_report(
            assessment_id, json_bytes, fmt="json"
        )

        # 4. Generate PDF report
        _publish_progress(
            assessment_id, "report_generation", 70,
            "Rendering PDF report...",
        )

        with tempfile.TemporaryDirectory(prefix="insurascan_report_") as tmpdir:
            pdf_path = Path(tmpdir) / "report.pdf"
            generator.generate_pdf_report(
                damage_report=damage_report,
                output_path=pdf_path,
                assessment_id=data["assessment_id"],
                claim_number=data["claim_number"],
                vehicle_year=data["vehicle_year"],
                vehicle_make=data["vehicle_make"],
                vehicle_model=data["vehicle_model"],
                vin=data["vin"],
                agent_id=data["agent_id"],
            )
            pdf_bytes = pdf_path.read_bytes()

        pdf_blob_path = blob_storage.upload_report(
            assessment_id, pdf_bytes, fmt="pdf"
        )

        # 5. Update assessment as complete
        _update_db(
            assessment_id,
            status="complete",
            completed_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        _publish_progress(
            assessment_id, "report_generation", 100,
            "Report generation complete!",
        )

        _complete_processing_job(job_id)

        return {
            "assessment_id": assessment_id,
            "json_blob_path": json_blob_path,
            "pdf_blob_path": pdf_blob_path,
        }

    except Exception as exc:
        logger.exception("Report generation failed for %s", assessment_id)
        _complete_processing_job(job_id, error=str(exc))
        _update_db(
            assessment_id,
            status="failed",
            error_message=f"Report generation failed: {exc}",
            updated_at=datetime.now(timezone.utc),
        )
        raise
