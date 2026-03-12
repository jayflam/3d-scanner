"""Celery task: AI damage analysis.

Downloads sampled frames from Blob Storage, batches them by vehicle zone,
sends to GPT-4o for analysis, stores DamageItem records, and updates totals.
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import redis

from app.config import settings
from app.services.blob_storage import blob_storage
from app.services.damage_analyzer import DamageAnalyzerService
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


def _get_assessment_info(assessment_id: str) -> dict:
    """Fetch vehicle info from DB for the prompt."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.models.assessment import Assessment

    db_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
        "postgresql+psycopg2", "postgresql"
    )
    engine = create_engine(db_url)
    with Session(engine) as session:
        result = session.execute(
            select(Assessment).where(Assessment.id == assessment_id)
        )
        assessment = result.scalar_one()
        return {
            "vehicle_year": assessment.vehicle_year,
            "vehicle_make": assessment.vehicle_make,
            "vehicle_model": assessment.vehicle_model,
            "vin": assessment.vin,
            "exterior_frame_count": assessment.exterior_frame_count,
            "interior_frame_count": assessment.interior_frame_count,
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


def _store_damage_items(assessment_id: str, damages: list) -> None:
    """Store parsed DamageItem records in DB."""
    import uuid

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models.damage_item import DamageItem as DamageItemModel
    from app.models.damage_item import DamageSeverity, VehicleZone

    db_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
        "postgresql+psycopg2", "postgresql"
    )
    engine = create_engine(db_url)
    with Session(engine) as session:
        for d in damages:
            item = DamageItemModel(
                id=uuid.uuid4(),
                assessment_id=assessment_id,
                damage_id=d.damage_id,
                location=d.location,
                vehicle_zone=VehicleZone(d.vehicle_zone.value),
                damage_type=d.damage_type,
                severity=DamageSeverity(d.severity.value),
                description=d.description,
                affected_parts=d.affected_parts,
                repair_method=d.repair_method,
                estimated_cost_low=d.estimated_cost_low,
                estimated_cost_high=d.estimated_cost_high,
                confidence_score=d.confidence_score,
                reference_frame_paths=d.reference_frames,
            )
            session.add(item)
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


def _download_frames(
    assessment_id: str,
    video_type: str,
    frame_count: int,
    output_dir: Path,
    sample_every: int = 1,
) -> list[Path]:
    """Download frames from blob, optionally sampling every Nth frame."""
    frames = []
    for i in range(1, frame_count + 1):
        if sample_every > 1 and (i - 1) % sample_every != 0:
            continue
        blob_path = f"frames/{assessment_id}/{video_type}/frame_{i:04d}.jpg"
        try:
            data = blob_storage.download_blob(blob_path)
            local_path = output_dir / f"frame_{i:04d}.jpg"
            local_path.write_bytes(data)
            frames.append(local_path)
        except FileNotFoundError:
            continue
    return frames


@celery.task(bind=True, name="app.tasks.analyze_damage.analyze_damage_task")
def analyze_damage_task(
    self,
    assessment_id: str,
) -> dict:
    """Download sampled frames -> batch by zone -> GPT-4o -> store damage items.

    Args:
        assessment_id: UUID of the assessment.

    Returns:
        Dict with total_damage_count and cost estimates.
    """
    job_id = _create_processing_job(
        assessment_id, "analysis", self.request.id or ""
    )

    try:
        _publish_progress(
            assessment_id, "analysis", 5,
            "Starting AI damage analysis...",
        )

        _update_db(
            assessment_id,
            status="analyzing",
            updated_at=datetime.now(timezone.utc),
        )

        # Get vehicle info for the prompt
        info = _get_assessment_info(assessment_id)

        with tempfile.TemporaryDirectory(prefix="insurascan_analyze_") as tmpdir:
            tmpdir = Path(tmpdir)

            # 1. Download exterior frames (sample every 3rd for efficiency)
            _publish_progress(
                assessment_id, "analysis", 10,
                "Downloading frames for analysis...",
            )

            (tmpdir / "exterior").mkdir(parents=True, exist_ok=True)
            exterior_frames = _download_frames(
                assessment_id, "exterior",
                info["exterior_frame_count"],
                tmpdir / "exterior",
                sample_every=3,
            )

            (tmpdir / "interior").mkdir(parents=True, exist_ok=True)
            interior_frames = _download_frames(
                assessment_id, "interior",
                info["interior_frame_count"],
                tmpdir / "interior",
                sample_every=3,
            )

            # 2. Run analyzer (async service called from sync context)
            _publish_progress(
                assessment_id, "analysis", 25,
                "Analyzing exterior damage with AI...",
            )

            analyzer = DamageAnalyzerService()
            analyzer.load()

            # Run async analyzer in sync context
            loop = asyncio.new_event_loop()
            try:
                exterior_report = loop.run_until_complete(
                    analyzer.analyze(
                        frames=exterior_frames,
                        vehicle_year=info["vehicle_year"],
                        vehicle_make=info["vehicle_make"],
                        vehicle_model=info["vehicle_model"],
                        vin=info["vin"],
                        is_interior=False,
                    )
                )

                _publish_progress(
                    assessment_id, "analysis", 60,
                    "Analyzing interior damage with AI...",
                )

                interior_report = loop.run_until_complete(
                    analyzer.analyze(
                        frames=interior_frames,
                        vehicle_year=info["vehicle_year"],
                        vehicle_make=info["vehicle_make"],
                        vehicle_model=info["vehicle_model"],
                        vin=info["vin"],
                        is_interior=True,
                    )
                )
            finally:
                loop.close()

            # 3. Resolve reference frames to blob paths before merging
            for d in exterior_report.damages:
                d.reference_frames = [
                    f"frames/{assessment_id}/exterior/{name}"
                    for name in d.reference_frames
                ]
            for d in interior_report.damages:
                d.reference_frames = [
                    f"frames/{assessment_id}/interior/{name}"
                    for name in d.reference_frames
                ]

            _publish_progress(
                assessment_id, "analysis", 85,
                "Storing damage items...",
            )

            all_damages = exterior_report.damages + interior_report.damages
            total_low = sum(d.estimated_cost_low for d in all_damages)
            total_high = sum(d.estimated_cost_high for d in all_damages)

            # 4. Store in DB
            if all_damages:
                _store_damage_items(assessment_id, all_damages)

            _update_db(
                assessment_id,
                total_estimate_low=total_low,
                total_estimate_high=total_high,
                updated_at=datetime.now(timezone.utc),
            )

            _publish_progress(
                assessment_id, "analysis", 100,
                f"Analysis complete: {len(all_damages)} damage items found.",
            )

            _complete_processing_job(job_id)

            return {
                "assessment_id": assessment_id,
                "total_damage_count": len(all_damages),
                "total_estimate_low": total_low,
                "total_estimate_high": total_high,
            }

    except Exception as exc:
        logger.exception("Damage analysis failed for %s", assessment_id)
        _complete_processing_job(job_id, error=str(exc))
        _update_db(
            assessment_id,
            status="failed",
            error_message=f"Damage analysis failed: {exc}",
            updated_at=datetime.now(timezone.utc),
        )
        raise
