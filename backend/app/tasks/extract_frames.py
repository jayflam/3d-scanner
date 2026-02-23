"""Celery task: extract frames from uploaded video.

Downloads the video from Blob Storage, runs FFmpeg extraction with
quality filtering, uploads passing frames back to Blob, and updates
the assessment record.
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
from app.services.frame_extractor import FrameExtractorService
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
    """Synchronous DB update for use in Celery workers."""
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import Session

    from app.models.assessment import Assessment

    # Convert async URL to sync
    db_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
        "postgresql+psycopg2", "postgresql"
    )
    engine = create_engine(db_url)
    with Session(engine) as session:
        session.execute(
            update(Assessment)
            .where(Assessment.id == assessment_id)
            .values(**kwargs)
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


@celery.task(bind=True, name="app.tasks.extract_frames.extract_frames_task")
def extract_frames_task(
    self,
    assessment_id: str,
    video_type: str,
) -> dict:
    """Download video from Blob -> extract frames -> upload frames -> update DB.

    Args:
        assessment_id: UUID of the assessment.
        video_type: "exterior" or "interior".

    Returns:
        Dict with frame_count and frame paths in Blob.
    """
    job_id = _create_processing_job(
        assessment_id, "frame_extraction", self.request.id or ""
    )

    try:
        _publish_progress(
            assessment_id, "frame_extraction", 5,
            f"Starting frame extraction for {video_type} video...",
        )

        # Update assessment status
        _update_db(
            assessment_id,
            status="extracting_frames",
            updated_at=datetime.now(timezone.utc),
        )

        # 1. Download video from blob to temp dir
        blob_path = f"videos/{assessment_id}/{video_type}.mp4"
        with tempfile.TemporaryDirectory(prefix="insurascan_frames_") as tmpdir:
            tmpdir = Path(tmpdir)
            video_path = tmpdir / f"{video_type}.mp4"

            _publish_progress(
                assessment_id, "frame_extraction", 10,
                "Downloading video from storage...",
            )

            video_data = blob_storage.download_blob(blob_path)
            video_path.write_bytes(video_data)

            # 2. Extract frames with FFmpeg
            _publish_progress(
                assessment_id, "frame_extraction", 20,
                "Extracting frames with FFmpeg...",
            )

            extractor = FrameExtractorService()
            frames_dir = tmpdir / "frames"
            passing_frames = extractor.extract_frames(
                video_path=video_path,
                output_dir=frames_dir,
                fps=2,
            )

            _publish_progress(
                assessment_id, "frame_extraction", 60,
                f"Extracted {len(passing_frames)} quality frames. Uploading...",
            )

            # 3. Upload passing frames to blob
            uploaded_paths = []
            for i, frame_path in enumerate(passing_frames):
                frame_bytes = frame_path.read_bytes()
                blob_frame_path = blob_storage.upload_frame(
                    assessment_id, video_type, i + 1, frame_bytes
                )
                uploaded_paths.append(blob_frame_path)

                if i % 10 == 0:
                    pct = 60 + int(30 * i / max(len(passing_frames), 1))
                    _publish_progress(
                        assessment_id, "frame_extraction", pct,
                        f"Uploading frame {i + 1}/{len(passing_frames)}...",
                    )

            # 4. Update assessment DB record
            frame_count_field = f"{video_type}_frame_count"
            _update_db(
                assessment_id,
                **{frame_count_field: len(passing_frames)},
                updated_at=datetime.now(timezone.utc),
            )

            _publish_progress(
                assessment_id, "frame_extraction", 100,
                f"Frame extraction complete: {len(passing_frames)} frames.",
            )

            _complete_processing_job(job_id)

            return {
                "assessment_id": assessment_id,
                "video_type": video_type,
                "frame_count": len(passing_frames),
                "frame_paths": uploaded_paths,
            }

    except Exception as exc:
        logger.exception(
            "Frame extraction failed for %s/%s", assessment_id, video_type
        )
        _complete_processing_job(job_id, error=str(exc))
        _update_db(
            assessment_id,
            status="failed",
            error_message=f"Frame extraction failed: {exc}",
            updated_at=datetime.now(timezone.utc),
        )
        raise
