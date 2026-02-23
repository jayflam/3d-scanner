"""Pipeline orchestration using Celery chord.

Orchestrates the full processing chain:
  1. Frame extraction (exterior + interior in parallel)
  2. After frames ready: splatting + damage analysis in parallel
  3. After both complete: report generation

Uses Celery chord to express the parallel-then-aggregate pattern.
"""

from __future__ import annotations

import logging

from celery import chain, chord, group

from app.tasks.analyze_damage import analyze_damage_task
from app.tasks.extract_frames import extract_frames_task
from app.tasks.generate_report import generate_report_task
from app.tasks.run_splatting import run_splatting_task

logger = logging.getLogger(__name__)


def start_pipeline(
    assessment_id: str,
    has_exterior: bool = True,
    has_interior: bool = True,
) -> str:
    """Start the full InsuraScan processing pipeline.

    Pipeline flow:
      extract_frames (exterior) ─┐
      extract_frames (interior) ─┤
                                 ├─> [after all frames extracted]
                                 │
      run_splatting (exterior) ──┐
      run_splatting (interior) ──┤
      analyze_damage ────────────┤
                                 ├─> generate_report
                                 └─>

    Args:
        assessment_id: UUID of the assessment to process.
        has_exterior: Whether an exterior video was uploaded.
        has_interior: Whether an interior video was uploaded.

    Returns:
        Celery task group ID for tracking.
    """
    # Phase 1: Frame extraction for all uploaded videos
    extraction_tasks = []
    if has_exterior:
        extraction_tasks.append(
            extract_frames_task.si(assessment_id, "exterior")
        )
    if has_interior:
        extraction_tasks.append(
            extract_frames_task.si(assessment_id, "interior")
        )

    if not extraction_tasks:
        raise ValueError("At least one video (exterior or interior) is required")

    # Phase 2: After frames are extracted, run splatting + analysis in parallel
    phase2_tasks = []
    if has_exterior:
        phase2_tasks.append(
            run_splatting_task.si(assessment_id, "exterior")
        )
    if has_interior:
        phase2_tasks.append(
            run_splatting_task.si(assessment_id, "interior")
        )
    # Damage analysis runs on all available frames
    phase2_tasks.append(
        analyze_damage_task.si(assessment_id)
    )

    # Phase 3: After splatting + analysis, generate the report
    report_task = generate_report_task.si(assessment_id)

    # Build the full pipeline:
    # chord(extraction_group) -> chord(phase2_group) -> report
    pipeline = chain(
        chord(group(extraction_tasks), _noop.si()),
        chord(group(phase2_tasks), _noop.si()),
        report_task,
    )

    result = pipeline.apply_async()
    logger.info(
        "Pipeline started for assessment %s (task_id=%s)",
        assessment_id,
        result.id,
    )
    return result.id


def start_single_video_pipeline(
    assessment_id: str,
    video_type: str,
) -> str:
    """Start pipeline for a single video (when processing one at a time).

    Simpler flow: extract -> (splat + analyze) -> report

    Args:
        assessment_id: UUID of the assessment.
        video_type: "exterior" or "interior".

    Returns:
        Celery task ID.
    """
    pipeline = chain(
        extract_frames_task.si(assessment_id, video_type),
        chord(
            group(
                run_splatting_task.si(assessment_id, video_type),
                analyze_damage_task.si(assessment_id),
            ),
            _noop.si(),
        ),
        generate_report_task.si(assessment_id),
    )

    result = pipeline.apply_async()
    logger.info(
        "Single-video pipeline started for %s/%s (task_id=%s)",
        assessment_id,
        video_type,
        result.id,
    )
    return result.id


from app.tasks.celery_app import celery  # noqa: E402


@celery.task(name="app.tasks.pipeline._noop")
def _noop(*args, **kwargs):
    """No-op callback for chord finalization.

    Celery chord requires a callback; this discards the group results
    and lets the chain continue.
    """
    return None
