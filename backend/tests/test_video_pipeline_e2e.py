"""End-to-end tests exposing three bugs in the video upload → pipeline flow.

Bug 1: triposr.py missing `import rembg` → NameError at runtime
Bug 2: videos.py pipeline double-trigger on dual-video upload
Bug 3: analyze_damage_task creates subdirectory AFTER _download_frames writes into it
"""

from __future__ import annotations

import io
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub heavy ML / GPU imports before any app imports
# ---------------------------------------------------------------------------
for _mod in (
    "torch", "trimesh", "xatlas", "cv2",
    "tsr", "tsr.system", "tsr.bake_texture",
    "rembg", "rembg.sessions",
    "celery", "redis", "ffmpeg",
    "azure", "azure.storage", "azure.storage.blob",
):
    sys.modules.setdefault(_mod, MagicMock())

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, StaticPool
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.assessment import Assessment, AssessmentStatus

# ---------------------------------------------------------------------------
# Test database (in-memory SQLite, JSONB → JSON)
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

for _table in Base.metadata.tables.values():
    for _col in _table.columns:
        if isinstance(_col.type, JSONB):
            _col.type = JSON()

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

# ---------------------------------------------------------------------------
# App with overrides
# ---------------------------------------------------------------------------
from app.api.deps import get_blob_storage, get_db
from app.api.v1.router import api_router
from app.services.blob_storage import BlobStorageService
from fastapi import FastAPI


async def _override_get_db():
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


_mock_blob = MagicMock(spec=BlobStorageService)
_mock_blob.is_azure = False
_mock_blob.get_blob_url.return_value = "/blob/test/path"
_mock_blob.upload_video.side_effect = lambda aid, vt, _f: f"videos/{aid}/{vt}.mp4"


def _override_get_blob():
    return _mock_blob


test_app = FastAPI()
test_app.include_router(api_router)
test_app.dependency_overrides[get_db] = _override_get_db
test_app.dependency_overrides[get_blob_storage] = _override_get_blob


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def _setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def assessment_id(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/assessments", json={
        "claim_number": "CLM-E2E-001",
        "agent_id": "agent-99",
        "vehicle_year": 2020,
        "vehicle_make": "Toyota",
        "vehicle_model": "Camry",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


# ===========================================================================
# Bug 1 – triposr.py must import rembg at module level
# ===========================================================================

class TestTripoSRRembgImport:
    def test_remove_background_calls_rembg_not_nameerror(self):
        """_remove_background must call rembg.remove without NameError."""
        import app.services.triposr as triposr_mod

        fake_image = MagicMock()
        fake_image.mode = "RGB"
        fake_session = MagicMock()

        mock_rembg = sys.modules["rembg"]
        mock_rembg.remove.return_value = MagicMock(
            mode="RGBA",
            getextrema=lambda: [(0, 255)] * 4,
        )

        try:
            triposr_mod._remove_background(fake_image, fake_session)
        except NameError as exc:
            pytest.fail(
                f"Bug 1: NameError in _remove_background — rembg not imported: {exc}"
            )

        mock_rembg.remove.assert_called_once_with(fake_image, session=fake_session)

    def test_load_calls_rembg_new_session_not_nameerror(self):
        """TripoSRService.load() must call rembg.new_session() without NameError."""
        import app.services.triposr as triposr_mod

        mock_rembg = sys.modules["rembg"]
        mock_rembg.new_session.return_value = MagicMock()

        mock_tsr = sys.modules["tsr"]
        mock_tsr.system.TSR.from_pretrained.return_value = MagicMock()
        sys.modules["torch"].cuda.is_available.return_value = False

        svc = triposr_mod.TripoSRService()
        try:
            svc.load(device="cpu")
        except NameError as exc:
            pytest.fail(
                f"Bug 1: NameError in TripoSRService.load — rembg not imported: {exc}"
            )

        mock_rembg.new_session.assert_called_once()


# ===========================================================================
# Bug 2 – pipeline must NOT start twice when two videos are uploaded
# ===========================================================================

class TestPipelineTrigger:
    @pytest.mark.asyncio
    async def test_first_of_two_videos_does_not_start_pipeline(
        self, client: AsyncClient, assessment_id: str
    ):
        """Uploading only the first video (exterior) must NOT start pipeline yet —
        the pipeline should wait until both are present."""
        # start_pipeline is imported locally inside the handler, so patch at source
        with patch("app.tasks.pipeline.start_pipeline", return_value="task-1") as mock_pl:
            resp = await client.post(
                f"/api/v1/assessments/{assessment_id}/videos/exterior",
                files={"file": ("ext.mp4", io.BytesIO(b"fake"), "video/mp4")},
            )
        assert resp.status_code == 200
        mock_pl.assert_not_called()

    @pytest.mark.asyncio
    async def test_two_video_uploads_start_pipeline_exactly_once(
        self, client: AsyncClient, assessment_id: str
    ):
        """Bug 2: uploading both exterior and interior must call start_pipeline
        exactly once (when the second video arrives), not once per upload."""
        call_count = 0

        def _counting(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return f"task-{call_count}"

        with patch("app.tasks.pipeline.start_pipeline", side_effect=_counting):
            r1 = await client.post(
                f"/api/v1/assessments/{assessment_id}/videos/exterior",
                files={"file": ("ext.mp4", io.BytesIO(b"fake"), "video/mp4")},
            )
            assert r1.status_code == 200

            r2 = await client.post(
                f"/api/v1/assessments/{assessment_id}/videos/interior",
                files={"file": ("int.mp4", io.BytesIO(b"fake"), "video/mp4")},
            )
            assert r2.status_code == 200

        assert call_count == 1, (
            f"Bug 2: start_pipeline was called {call_count} times — "
            "must be called exactly once (when both videos are ready)."
        )

    @pytest.mark.asyncio
    async def test_pipeline_called_with_both_flags_when_both_uploaded(
        self, client: AsyncClient, assessment_id: str
    ):
        """When both videos are present, pipeline is invoked with
        has_exterior=True AND has_interior=True."""
        captured = []

        def _capture(*args, **kwargs):
            captured.append(kwargs)
            return "task-x"

        with patch("app.tasks.pipeline.start_pipeline", side_effect=_capture):
            await client.post(
                f"/api/v1/assessments/{assessment_id}/videos/exterior",
                files={"file": ("ext.mp4", io.BytesIO(b"fake"), "video/mp4")},
            )
            await client.post(
                f"/api/v1/assessments/{assessment_id}/videos/interior",
                files={"file": ("int.mp4", io.BytesIO(b"fake"), "video/mp4")},
            )

        assert len(captured) == 1
        assert captured[0].get("has_exterior") is True
        assert captured[0].get("has_interior") is True


# ===========================================================================
# Bug 3 – analyze_damage_task: frame dirs must exist BEFORE _download_frames
# ===========================================================================

class TestAnalyzeDamageTaskMkdir:
    @patch("app.tasks.analyze_damage._complete_processing_job")
    @patch("app.tasks.analyze_damage._create_processing_job", return_value="job-xyz")
    @patch("app.tasks.analyze_damage._store_damage_items")
    @patch("app.tasks.analyze_damage._update_db")
    @patch("app.tasks.analyze_damage._publish_progress")
    @patch("app.tasks.analyze_damage._get_assessment_info")
    @patch("app.tasks.analyze_damage.blob_storage")
    @patch("app.tasks.analyze_damage.DamageAnalyzerService")
    def test_exterior_frames_are_actually_written(
        self,
        MockAnalyzer,
        mock_blob,
        mock_info,
        mock_progress,
        mock_update_db,
        mock_store,
        mock_create_job,
        mock_complete_job,
    ):
        """Bug 3: with exterior_frame_count=3 and sample_every=3, at least one
        frame must be written to disk. If the directory is created after
        _download_frames, write_bytes silently swallows a FileNotFoundError
        and no frames are written — analysis runs on empty input."""
        from app.tasks.analyze_damage import analyze_damage_task, _download_frames
        from app.services.damage_analyzer import DamageReport

        mock_info.return_value = {
            "vehicle_year": 2020, "vehicle_make": "Toyota",
            "vehicle_model": "Camry", "vin": "",
            "exterior_frame_count": 3, "interior_frame_count": 0,
        }
        # Return fake JPEG bytes for every frame download
        mock_blob.download_blob.return_value = b"\xff\xd8\xff" + b"\x00" * 100

        # Track what frames the analyzer actually receives
        received_frames: list = []

        async def _capture_analyze(frames, **kwargs):
            received_frames.extend(frames)
            return DamageReport()

        mock_analyzer_instance = MagicMock()
        mock_analyzer_instance.analyze = _capture_analyze
        MockAnalyzer.return_value = mock_analyzer_instance

        analyze_damage_task.request.id = "task-bug3-ext"
        analyze_damage_task("assessment-bug3-ext")

        # With frame_count=3, sample_every=3: frame 1 should be written.
        # If Bug 3 is present, received_frames would be empty (silently dropped).
        assert len(received_frames) >= 1, (
            "Bug 3: zero frames reached the analyzer — the exterior frame directory "
            "was not created before _download_frames, so write_bytes silently failed."
        )

    @patch("app.tasks.analyze_damage._complete_processing_job")
    @patch("app.tasks.analyze_damage._create_processing_job", return_value="job-xyz2")
    @patch("app.tasks.analyze_damage._store_damage_items")
    @patch("app.tasks.analyze_damage._update_db")
    @patch("app.tasks.analyze_damage._publish_progress")
    @patch("app.tasks.analyze_damage._get_assessment_info")
    @patch("app.tasks.analyze_damage.blob_storage")
    @patch("app.tasks.analyze_damage.DamageAnalyzerService")
    def test_interior_frames_are_actually_written(
        self,
        MockAnalyzer,
        mock_blob,
        mock_info,
        mock_progress,
        mock_update_db,
        mock_store,
        mock_create_job,
        mock_complete_job,
    ):
        """Bug 3 (interior): same check for interior frames."""
        from app.tasks.analyze_damage import analyze_damage_task
        from app.services.damage_analyzer import DamageReport

        mock_info.return_value = {
            "vehicle_year": 2021, "vehicle_make": "Honda",
            "vehicle_model": "Civic", "vin": "VIN123",
            "exterior_frame_count": 0, "interior_frame_count": 6,
        }
        mock_blob.download_blob.return_value = b"\xff\xd8\xff" + b"\x00" * 100

        received_interior: list = []

        async def _capture_analyze(frames, is_interior=False, **kwargs):
            if is_interior:
                received_interior.extend(frames)
            return DamageReport()

        mock_analyzer_instance = MagicMock()
        mock_analyzer_instance.analyze = _capture_analyze
        MockAnalyzer.return_value = mock_analyzer_instance

        analyze_damage_task.request.id = "task-bug3-int"
        analyze_damage_task("assessment-bug3-int")

        assert len(received_interior) >= 1, (
            "Bug 3: zero interior frames reached the analyzer — the interior frame "
            "directory was not created before _download_frames."
        )
