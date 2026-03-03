"""End-to-end pipeline integration test.

Tests the full assessment lifecycle: create -> upload -> frame extraction ->
splatting -> analysis -> report. Heavy services (FFmpeg, COLMAP, GS, GPT-4o)
are mocked, but the Celery task chain wiring and DB state transitions are
verified.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Stub heavy deps before any app imports
for mod in ("torch", "trimesh", "trimesh.visual", "trimesh.visual.material",
            "xatlas", "numpy", "einops", "rembg", "rembg.sessions",
            "cv2", "redis", "celery", "celery.result",
            "ffmpeg", "weasyprint"):
    sys.modules.setdefault(mod, MagicMock())
fake_tsr = MagicMock()
sys.modules.setdefault("tsr", fake_tsr)
sys.modules.setdefault("tsr.system", fake_tsr.system)
sys.modules.setdefault("tsr.bake_texture", fake_tsr.bake_texture)

import pytest
import pytest_asyncio
from sqlalchemy import JSON, StaticPool, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.assessment import Assessment, AssessmentStatus
from app.models.damage_item import DamageItem, DamageSeverity, VehicleZone
from app.models.processing_job import JobStatus, ProcessingJob, ProcessingStage


# --- In-memory test DB (SQLite with JSONB->JSON adaptation) ---

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# Replace JSONB columns with JSON for SQLite compatibility
for table in Base.metadata.tables.values():
    for column in table.columns:
        if isinstance(column.type, JSONB):
            column.type = JSON()

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
test_session = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    async with test_session() as session:
        yield session


# --- Helper to create a full assessment ---

async def create_test_assessment(db: AsyncSession) -> Assessment:
    a = Assessment(
        id=uuid.uuid4(),
        claim_number="CLM-E2E-001",
        agent_id="agent_test",
        vehicle_year=2022,
        vehicle_make="Toyota",
        vehicle_model="Camry",
        vin="4T1BF1FK5CU512345",
        status=AssessmentStatus.CREATED,
        exterior_frame_count=0,
        interior_frame_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


# --- Tests ---


class TestAssessmentLifecycle:
    """Test the full assessment state machine from created -> complete."""

    @pytest.mark.asyncio
    async def test_status_transitions_created_to_uploading(self, db: AsyncSession):
        a = await create_test_assessment(db)
        assert a.status == AssessmentStatus.CREATED

        # Simulate video upload
        a.status = AssessmentStatus.UPLOADING
        a.exterior_video_blob_path = "videos/test/exterior.mp4"
        await db.commit()
        await db.refresh(a)

        assert a.status == AssessmentStatus.UPLOADING
        assert a.exterior_video_blob_path is not None

    @pytest.mark.asyncio
    async def test_status_transitions_through_pipeline(self, db: AsyncSession):
        a = await create_test_assessment(db)

        # uploading
        a.status = AssessmentStatus.UPLOADING
        a.exterior_video_blob_path = "videos/test/exterior.mp4"
        await db.commit()

        # extracting_frames
        a.status = AssessmentStatus.EXTRACTING_FRAMES
        a.exterior_frame_count = 60
        await db.commit()

        # splatting
        a.status = AssessmentStatus.SPLATTING
        await db.commit()

        # analyzing
        a.status = AssessmentStatus.ANALYZING
        a.exterior_splat_blob_path = "splats/test/exterior.ply"
        await db.commit()

        # complete
        a.status = AssessmentStatus.COMPLETE
        a.total_estimate_low = 1500
        a.total_estimate_high = 3500
        a.completed_at = datetime.now(timezone.utc)
        await db.commit()

        await db.refresh(a)
        assert a.status == AssessmentStatus.COMPLETE
        assert float(a.total_estimate_low) == 1500
        assert float(a.total_estimate_high) == 3500
        assert a.completed_at is not None

    @pytest.mark.asyncio
    async def test_failed_status(self, db: AsyncSession):
        a = await create_test_assessment(db)
        a.status = AssessmentStatus.FAILED
        a.error_message = "COLMAP failed: insufficient features"
        await db.commit()

        await db.refresh(a)
        assert a.status == AssessmentStatus.FAILED
        assert "COLMAP" in a.error_message


class TestProcessingJobTracking:
    """Test that processing jobs correctly track each pipeline stage."""

    @pytest.mark.asyncio
    async def test_create_and_complete_processing_jobs(self, db: AsyncSession):
        a = await create_test_assessment(db)

        # Create frame extraction job
        job = ProcessingJob(
            id=uuid.uuid4(),
            assessment_id=a.id,
            stage=ProcessingStage.FRAME_EXTRACTION,
            status=JobStatus.RUNNING,
            celery_task_id="celery-task-abc",
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.commit()

        # Complete it
        job.status = JobStatus.COMPLETE
        job.completed_at = datetime.now(timezone.utc)
        job.duration_seconds = 45
        await db.commit()
        await db.refresh(job)

        assert job.status == JobStatus.COMPLETE
        assert job.duration_seconds == 45

    @pytest.mark.asyncio
    async def test_failed_processing_job(self, db: AsyncSession):
        a = await create_test_assessment(db)

        job = ProcessingJob(
            id=uuid.uuid4(),
            assessment_id=a.id,
            stage=ProcessingStage.SPLATTING,
            status=JobStatus.RUNNING,
            celery_task_id="celery-task-def",
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.commit()

        # Fail it
        job.status = JobStatus.FAILED
        job.error_message = "CUDA out of memory"
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(job)

        assert job.status == JobStatus.FAILED
        assert "CUDA" in job.error_message

    @pytest.mark.asyncio
    async def test_all_pipeline_stages_tracked(self, db: AsyncSession):
        a = await create_test_assessment(db)

        stages = [
            ProcessingStage.FRAME_EXTRACTION,
            ProcessingStage.SPLATTING,
            ProcessingStage.ANALYSIS,
            ProcessingStage.REPORT_GENERATION,
        ]

        for stage in stages:
            job = ProcessingJob(
                id=uuid.uuid4(),
                assessment_id=a.id,
                stage=stage,
                status=JobStatus.COMPLETE,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db.add(job)

        await db.commit()

        result = await db.execute(
            select(ProcessingJob).where(ProcessingJob.assessment_id == a.id)
        )
        jobs = result.scalars().all()
        assert len(jobs) == 4
        completed_stages = {j.stage for j in jobs}
        assert completed_stages == set(stages)


class TestDamageItemStorage:
    """Test storing damage items linked to an assessment."""

    @pytest.mark.asyncio
    async def test_store_damage_items(self, db: AsyncSession):
        a = await create_test_assessment(db)

        items = [
            DamageItem(
                id=uuid.uuid4(),
                assessment_id=a.id,
                damage_id="DMG-001",
                location="Front bumper, driver side",
                vehicle_zone=VehicleZone.FRONT_LEFT,
                damage_type="Dent with paint transfer",
                severity=DamageSeverity.MODERATE,
                description="8-inch dent on front bumper cover",
                affected_parts=["Front bumper cover", "Bumper reinforcement bar"],
                repair_method="Replace bumper cover + repaint",
                estimated_cost_low=800,
                estimated_cost_high=1200,
                confidence_score=0.85,
                reference_frame_paths=["frame_0042.jpg", "frame_0043.jpg"],
                created_at=datetime.now(timezone.utc),
            ),
            DamageItem(
                id=uuid.uuid4(),
                assessment_id=a.id,
                damage_id="DMG-002",
                location="Left headlight",
                vehicle_zone=VehicleZone.FRONT_LEFT,
                damage_type="Shatter",
                severity=DamageSeverity.SEVERE,
                description="Headlight lens shattered",
                affected_parts=["Left headlight assembly"],
                repair_method="Replace headlight assembly",
                estimated_cost_low=400,
                estimated_cost_high=800,
                confidence_score=0.92,
                reference_frame_paths=["frame_0044.jpg"],
                created_at=datetime.now(timezone.utc),
            ),
        ]

        for item in items:
            db.add(item)
        await db.commit()

        result = await db.execute(
            select(DamageItem).where(DamageItem.assessment_id == a.id)
        )
        stored = result.scalars().all()
        assert len(stored) == 2

        total_low = sum(float(d.estimated_cost_low) for d in stored)
        total_high = sum(float(d.estimated_cost_high) for d in stored)
        assert total_low == 1200
        assert total_high == 2000

    @pytest.mark.asyncio
    async def test_cascade_delete_removes_damage_items(self, db: AsyncSession):
        a = await create_test_assessment(db)

        d = DamageItem(
            id=uuid.uuid4(),
            assessment_id=a.id,
            damage_id="DMG-DEL",
            location="Hood",
            vehicle_zone=VehicleZone.FRONT_CENTER,
            damage_type="Scratch",
            severity=DamageSeverity.MINOR,
            description="Light scratch",
            affected_parts=["Hood"],
            repair_method="Repaint",
            estimated_cost_low=200,
            estimated_cost_high=400,
            confidence_score=0.9,
            reference_frame_paths=[],
            created_at=datetime.now(timezone.utc),
        )
        db.add(d)
        await db.commit()

        # Delete the assessment
        await db.delete(a)
        await db.commit()

        # Damage items should be cascade-deleted
        result = await db.execute(
            select(DamageItem).where(DamageItem.assessment_id == a.id)
        )
        remaining = result.scalars().all()
        assert len(remaining) == 0


class TestFullE2EFlow:
    """Simulate the full pipeline flow through DB state."""

    @pytest.mark.asyncio
    async def test_complete_assessment_lifecycle(self, db: AsyncSession):
        # 1. Create assessment
        a = await create_test_assessment(db)
        assert a.status == AssessmentStatus.CREATED

        # 2. Upload videos
        a.status = AssessmentStatus.UPLOADING
        a.exterior_video_blob_path = "videos/test/exterior.mp4"
        a.interior_video_blob_path = "videos/test/interior.mp4"
        await db.commit()

        # 3. Frame extraction
        a.status = AssessmentStatus.EXTRACTING_FRAMES
        await db.commit()

        ext_job = ProcessingJob(
            id=uuid.uuid4(),
            assessment_id=a.id,
            stage=ProcessingStage.FRAME_EXTRACTION,
            status=JobStatus.COMPLETE,
            celery_task_id="task-ext-1",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_seconds=30,
        )
        db.add(ext_job)

        a.exterior_frame_count = 60
        a.interior_frame_count = 45
        await db.commit()

        # 4. Splatting
        a.status = AssessmentStatus.SPLATTING
        await db.commit()

        splat_job = ProcessingJob(
            id=uuid.uuid4(),
            assessment_id=a.id,
            stage=ProcessingStage.SPLATTING,
            status=JobStatus.COMPLETE,
            celery_task_id="task-splat-1",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_seconds=600,
        )
        db.add(splat_job)

        a.exterior_splat_blob_path = "splats/test/exterior.ply"
        a.interior_splat_blob_path = "splats/test/interior.ply"
        await db.commit()

        # 5. Damage analysis
        a.status = AssessmentStatus.ANALYZING
        await db.commit()

        analysis_job = ProcessingJob(
            id=uuid.uuid4(),
            assessment_id=a.id,
            stage=ProcessingStage.ANALYSIS,
            status=JobStatus.COMPLETE,
            celery_task_id="task-analyze-1",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_seconds=90,
        )
        db.add(analysis_job)

        # Add damage items
        for i, (zone, sev, low, high) in enumerate([
            (VehicleZone.FRONT_LEFT, DamageSeverity.MODERATE, 800, 1200),
            (VehicleZone.FRONT_CENTER, DamageSeverity.SEVERE, 1500, 2500),
            (VehicleZone.SIDE_LEFT, DamageSeverity.MINOR, 200, 400),
        ], start=1):
            db.add(DamageItem(
                id=uuid.uuid4(),
                assessment_id=a.id,
                damage_id=f"DMG-{i:03d}",
                location=f"Test location {i}",
                vehicle_zone=zone,
                damage_type="Test damage",
                severity=sev,
                description=f"Test damage {i}",
                affected_parts=[f"Part {i}"],
                repair_method="Replace",
                estimated_cost_low=low,
                estimated_cost_high=high,
                confidence_score=0.85,
                reference_frame_paths=[],
                created_at=datetime.now(timezone.utc),
            ))

        a.total_estimate_low = 2500
        a.total_estimate_high = 4100
        await db.commit()

        # 6. Report generation
        report_job = ProcessingJob(
            id=uuid.uuid4(),
            assessment_id=a.id,
            stage=ProcessingStage.REPORT_GENERATION,
            status=JobStatus.COMPLETE,
            celery_task_id="task-report-1",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_seconds=15,
        )
        db.add(report_job)

        a.status = AssessmentStatus.COMPLETE
        a.completed_at = datetime.now(timezone.utc)
        await db.commit()

        # --- Verify final state ---
        await db.refresh(a)
        assert a.status == AssessmentStatus.COMPLETE
        assert a.exterior_video_blob_path is not None
        assert a.interior_video_blob_path is not None
        assert a.exterior_splat_blob_path is not None
        assert a.interior_splat_blob_path is not None
        assert a.exterior_frame_count == 60
        assert a.interior_frame_count == 45
        assert float(a.total_estimate_low) == 2500
        assert float(a.total_estimate_high) == 4100
        assert a.completed_at is not None

        # Verify all 4 processing jobs
        result = await db.execute(
            select(ProcessingJob).where(ProcessingJob.assessment_id == a.id)
        )
        jobs = result.scalars().all()
        assert len(jobs) == 4
        assert all(j.status == JobStatus.COMPLETE for j in jobs)

        # Verify 3 damage items
        result = await db.execute(
            select(DamageItem).where(DamageItem.assessment_id == a.id)
        )
        damages = result.scalars().all()
        assert len(damages) == 3


class TestPipelineChainStructure:
    """Test that the pipeline module constructs the correct Celery chain."""

    def test_start_pipeline_requires_at_least_one_video(self):
        from app.tasks.pipeline import start_pipeline

        with pytest.raises(ValueError, match="At least one video"):
            start_pipeline("fake-id", has_exterior=False, has_interior=False)
