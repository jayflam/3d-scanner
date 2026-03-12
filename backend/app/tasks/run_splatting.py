"""Celery task: COLMAP SfM + Gaussian Splatting.

Downloads extracted frames from Blob Storage, runs COLMAP to get camera poses,
trains a Gaussian Splatting model, exports .ply, and uploads to Blob.
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
from app.services.colmap_service import COLMAPService
from app.services.gaussian_splat import GaussianSplatService
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


@celery.task(bind=True, name="app.tasks.run_splatting.run_splatting_task")
def run_splatting_task(
    self,
    assessment_id: str,
    video_type: str,
) -> dict:
    """Download frames -> COLMAP SfM -> Gaussian Splatting -> upload .ply.

    Args:
        assessment_id: UUID of the assessment.
        video_type: "exterior" or "interior".

    Returns:
        Dict with splat_blob_path.
    """
    job_id = _create_processing_job(
        assessment_id, "splatting", self.request.id or ""
    )

    try:
        _publish_progress(
            assessment_id, "splatting", 5,
            f"Starting 3D reconstruction for {video_type}...",
        )

        _update_db(
            assessment_id,
            status="splatting",
            updated_at=datetime.now(timezone.utc),
        )

        with tempfile.TemporaryDirectory(prefix="insurascan_splat_") as tmpdir:
            tmpdir = Path(tmpdir)
            frames_dir = tmpdir / "frames"
            frames_dir.mkdir()

            # 1. Download frames from blob
            _publish_progress(
                assessment_id, "splatting", 10,
                "Downloading extracted frames...",
            )

            # List frames from blob (we know the naming convention)
            frame_idx = 1
            while True:
                blob_path = f"frames/{assessment_id}/{video_type}/frame_{frame_idx:04d}.jpg"
                try:
                    data = blob_storage.download_blob(blob_path)
                    (frames_dir / f"frame_{frame_idx:04d}.jpg").write_bytes(data)
                    frame_idx += 1
                except FileNotFoundError:
                    break

            frame_count = frame_idx - 1
            if frame_count == 0:
                raise RuntimeError("No frames found in blob storage")

            logger.info("Downloaded %d frames for splatting", frame_count)

            # 2. Run COLMAP SfM
            _publish_progress(
                assessment_id, "splatting", 20,
                "Running COLMAP Structure-from-Motion...",
            )

            colmap = COLMAPService()
            colmap_output = tmpdir / "colmap"
            model_dir = colmap.run_sfm(frames_dir, colmap_output)

            _publish_progress(
                assessment_id, "splatting", 45,
                "COLMAP complete. Starting Gaussian Splatting training...",
            )

            # 3. Prepare data directory for nerfstudio
            gs = GaussianSplatService()
            ns_data = tmpdir / "ns_data"
            gs.prepare_data_dir(frames_dir, model_dir, ns_data)

            # 4. Train Gaussian Splatting
            gs_output = tmpdir / "gs_output"
            trained_dir = gs.train(ns_data, gs_output, iterations=7000)

            _publish_progress(
                assessment_id, "splatting", 85,
                "Training complete. Exporting PLY...",
            )

            # 5. Export .ply
            ply_path = tmpdir / f"{video_type}.ply"
            exported = gs.export_ply(trained_dir, ply_path)

            # 6. Upload .ply to blob
            _publish_progress(
                assessment_id, "splatting", 95,
                "Uploading 3D splat to storage...",
            )

            splat_blob_path = blob_storage.upload_splat(
                assessment_id, video_type, exported
            )

            # 7. Optionally export GLB for AR/web viewers
            model_blob_path: str | None = None
            try:
                _publish_progress(
                    assessment_id,
                    "splatting",
                    97,
                    "Generating web AR model (GLB)...",
                )
                try:
                    import trimesh  # type: ignore[import]
                except ImportError:
                    trimesh = None  # type: ignore[assignment]

                if trimesh is not None:
                    glb_path = tmpdir / f"{video_type}.glb"
                    mesh = trimesh.load(exported, process=False)  # type: ignore[call-arg]
                    mesh.export(glb_path)  # type: ignore[call-arg]
                    model_blob_path = blob_storage.upload_model(
                        assessment_id, video_type, glb_path
                    )
            except Exception:
                logger.debug(
                    "Failed to generate GLB model for %s/%s (non-fatal)",
                    assessment_id,
                    video_type,
                    exc_info=True,
                )

            # 8. Update DB
            splat_field = f"{video_type}_splat_blob_path"
            model_field = f"{video_type}_model_blob_path"
            update_values = {
                splat_field: splat_blob_path,
                "updated_at": datetime.now(timezone.utc),
            }
            if model_blob_path is not None:
                update_values[model_field] = model_blob_path

            _update_db(
                assessment_id,
                **update_values,
            )

            _publish_progress(
                assessment_id, "splatting", 100,
                f"3D reconstruction complete for {video_type}.",
            )

            _complete_processing_job(job_id)

            return {
                "assessment_id": assessment_id,
                "video_type": video_type,
                "splat_blob_path": splat_blob_path,
                "model_blob_path": model_blob_path,
            }

    except Exception as exc:
        logger.warning(
            "Splatting failed for %s/%s (non-fatal, pipeline continues): %s",
            assessment_id, video_type, exc,
        )
        _complete_processing_job(job_id, error=str(exc))
        # Do NOT mark the assessment as failed or re-raise — splatting is optional.
        # Damage analysis and report generation can still complete without the splat.
        return {
            "assessment_id": assessment_id,
            "video_type": video_type,
            "splat_blob_path": None,
            "error": str(exc),
        }
