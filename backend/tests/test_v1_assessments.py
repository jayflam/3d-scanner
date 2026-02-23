"""Comprehensive API v1 endpoint tests using httpx AsyncClient with in-memory SQLite."""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

# Stub heavy deps before any app imports
for mod in ("torch", "trimesh", "trimesh.visual", "trimesh.visual.material",
            "xatlas", "numpy", "einops", "rembg", "rembg.sessions",
            "cv2", "redis", "celery", "ffmpeg"):
    sys.modules.setdefault(mod, MagicMock())
fake_tsr = MagicMock()
sys.modules.setdefault("tsr", fake_tsr)
sys.modules.setdefault("tsr.system", fake_tsr.system)
sys.modules.setdefault("tsr.bake_texture", fake_tsr.bake_texture)

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, StaticPool, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.assessment import Assessment, AssessmentStatus
from app.models.damage_item import DamageItem, DamageSeverity, VehicleZone
from app.models.processing_job import ProcessingJob

# --- Test database setup (SQLite with JSONB->JSON adaptation) ---

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
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db():
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# --- App setup ---

from app.api.deps import get_db, get_blob_storage
from app.services.blob_storage import BlobStorageService

# Create a mock blob service
mock_blob = MagicMock(spec=BlobStorageService)
mock_blob.is_azure = False
mock_blob.get_blob_url.return_value = "/blob/test/path"
mock_blob.upload_video.return_value = "videos/test/exterior.mp4"


def override_get_blob_storage():
    return mock_blob


# Build test app by importing after stubs
from app.api.v1.router import api_router
from fastapi import FastAPI

test_app = FastAPI()
test_app.include_router(api_router)
test_app.dependency_overrides[get_db] = override_get_db
test_app.dependency_overrides[get_blob_storage] = override_get_blob_storage


# --- Fixtures ---


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db_session():
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def sample_assessment(db_session: AsyncSession) -> Assessment:
    """Insert a sample assessment into the DB."""
    a = Assessment(
        id=uuid.uuid4(),
        claim_number="CLM-2026-00142",
        agent_id="agent_jsmith",
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
    db_session.add(a)
    await db_session.commit()
    await db_session.refresh(a)
    return a


# --- Tests: Create Assessment ---


class TestCreateAssessment:
    @pytest.mark.asyncio
    async def test_create_returns_201(self, client: AsyncClient):
        resp = await client.post("/api/v1/assessments", json={
            "claim_number": "CLM-001",
            "agent_id": "agent_1",
            "vehicle_year": 2022,
            "vehicle_make": "Toyota",
            "vehicle_model": "Camry",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "created"
        assert body["claim_number"] == "CLM-001"
        assert "id" in body
        assert "upload_urls" in body
        assert "exterior" in body["upload_urls"]
        assert "interior" in body["upload_urls"]

    @pytest.mark.asyncio
    async def test_create_with_optional_fields(self, client: AsyncClient):
        resp = await client.post("/api/v1/assessments", json={
            "claim_number": "CLM-002",
            "agent_id": "agent_2",
            "vehicle_year": 2023,
            "vehicle_make": "Honda",
            "vehicle_model": "Civic",
            "vin": "1HGBH41JXMN109186",
            "gps_latitude": 33.749,
            "gps_longitude": -84.388,
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_create_missing_required_field(self, client: AsyncClient):
        resp = await client.post("/api/v1/assessments", json={
            "agent_id": "agent_1",
            "vehicle_year": 2022,
        })
        assert resp.status_code == 422


# --- Tests: List Assessments ---


class TestListAssessments:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/api/v1/assessments")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["page"] == 1

    @pytest.mark.asyncio
    async def test_list_after_create(self, client: AsyncClient):
        # Create an assessment
        await client.post("/api/v1/assessments", json={
            "claim_number": "CLM-LIST-001",
            "agent_id": "agent_1",
            "vehicle_year": 2022,
            "vehicle_make": "Toyota",
            "vehicle_model": "Camry",
        })

        resp = await client.get("/api/v1/assessments")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["claim_number"] == "CLM-LIST-001"

    @pytest.mark.asyncio
    async def test_list_pagination(self, client: AsyncClient):
        # Create 3 assessments
        for i in range(3):
            await client.post("/api/v1/assessments", json={
                "claim_number": f"CLM-PAG-{i:03d}",
                "agent_id": "agent_1",
                "vehicle_year": 2022,
                "vehicle_make": "Toyota",
                "vehicle_model": "Camry",
            })

        resp = await client.get("/api/v1/assessments?page=1&page_size=2")
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 2
        assert body["page"] == 1

        resp2 = await client.get("/api/v1/assessments?page=2&page_size=2")
        body2 = resp2.json()
        assert len(body2["items"]) == 1

    @pytest.mark.asyncio
    async def test_list_filter_by_claim_number(self, client: AsyncClient):
        await client.post("/api/v1/assessments", json={
            "claim_number": "CLM-FIND-ME",
            "agent_id": "a1",
            "vehicle_year": 2022,
            "vehicle_make": "Toyota",
            "vehicle_model": "Camry",
        })
        await client.post("/api/v1/assessments", json={
            "claim_number": "CLM-OTHER",
            "agent_id": "a1",
            "vehicle_year": 2022,
            "vehicle_make": "Honda",
            "vehicle_model": "Civic",
        })

        resp = await client.get("/api/v1/assessments?claim_number=FIND")
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["claim_number"] == "CLM-FIND-ME"

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, client: AsyncClient):
        await client.post("/api/v1/assessments", json={
            "claim_number": "CLM-STATUS",
            "agent_id": "a1",
            "vehicle_year": 2022,
            "vehicle_make": "Toyota",
            "vehicle_model": "Camry",
        })

        resp = await client.get("/api/v1/assessments?status=created")
        body = resp.json()
        assert body["total"] == 1

        resp2 = await client.get("/api/v1/assessments?status=complete")
        body2 = resp2.json()
        assert body2["total"] == 0

    @pytest.mark.asyncio
    async def test_list_filter_invalid_status(self, client: AsyncClient):
        resp = await client.get("/api/v1/assessments?status=bogus")
        assert resp.status_code == 400


# --- Tests: Get Assessment Detail ---


class TestGetAssessment:
    @pytest.mark.asyncio
    async def test_get_existing(self, client: AsyncClient, sample_assessment: Assessment):
        resp = await client.get(f"/api/v1/assessments/{sample_assessment.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(sample_assessment.id)
        assert body["claim_number"] == "CLM-2026-00142"
        assert body["vehicle"]["year"] == 2022
        assert body["vehicle"]["make"] == "Toyota"
        assert body["pipeline"]["exterior_video"] == "pending"
        assert body["splat_ready"]["exterior"] is False

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/v1/assessments/{fake_id}")
        assert resp.status_code == 404


# --- Tests: Delete Assessment ---


class TestDeleteAssessment:
    @pytest.mark.asyncio
    async def test_delete_existing(self, client: AsyncClient, sample_assessment: Assessment):
        resp = await client.delete(f"/api/v1/assessments/{sample_assessment.id}")
        assert resp.status_code == 204

        # Verify it's gone
        resp2 = await client.get(f"/api/v1/assessments/{sample_assessment.id}")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client.delete(f"/api/v1/assessments/{fake_id}")
        assert resp.status_code == 404


# --- Tests: Assessment Response Shape ---


class TestAssessmentResponseShape:
    @pytest.mark.asyncio
    async def test_response_contains_all_expected_fields(self, client: AsyncClient):
        create_resp = await client.post("/api/v1/assessments", json={
            "claim_number": "CLM-SHAPE",
            "agent_id": "agent_1",
            "vehicle_year": 2022,
            "vehicle_make": "Ford",
            "vehicle_model": "F-150",
            "vin": "1FTEW1EP0MKE12345",
        })
        assessment_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/assessments/{assessment_id}")
        body = resp.json()

        # Required top-level fields
        assert "id" in body
        assert "status" in body
        assert "claim_number" in body
        assert "agent_id" in body
        assert "vin" in body
        assert "vehicle" in body
        assert "pipeline" in body
        assert "frame_count" in body
        assert "splat_ready" in body
        assert "created_at" in body
        assert "updated_at" in body

        # Vehicle subfields
        assert body["vehicle"]["year"] == 2022
        assert body["vehicle"]["make"] == "Ford"
        assert body["vehicle"]["model"] == "F-150"

        # Pipeline subfields
        pipeline = body["pipeline"]
        for key in ("exterior_video", "interior_video", "frame_extraction",
                     "gaussian_splatting", "damage_analysis", "report_generation"):
            assert key in pipeline

        # Frame count
        assert body["frame_count"]["exterior"] == 0
        assert body["frame_count"]["interior"] == 0

        # Splat ready
        assert body["splat_ready"]["exterior"] is False
        assert body["splat_ready"]["interior"] is False


# --- Tests: Health / System Endpoints ---


class TestSystemEndpoints:
    @pytest.mark.asyncio
    async def test_gpu_status(self, client: AsyncClient):
        resp = await client.get("/api/v1/health/gpu")
        assert resp.status_code == 200
        body = resp.json()
        assert "gpu_available" in body

    @pytest.mark.asyncio
    async def test_config_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/v1/config")
        assert resp.status_code == 200
        body = resp.json()
        assert "max_upload_size_mb" in body
        assert "allowed_video_extensions" in body
        assert "blob_storage" in body


# --- Tests: Damage Report Endpoints ---


class TestReportEndpoints:
    @pytest.mark.asyncio
    async def test_report_for_assessment_with_no_damages(
        self, client: AsyncClient, sample_assessment: Assessment
    ):
        resp = await client.get(f"/api/v1/assessments/{sample_assessment.id}/report")
        assert resp.status_code == 200
        body = resp.json()
        assert body["assessment_id"] == str(sample_assessment.id)
        assert body["summary"]["total_damage_count"] == 0
        assert body["damages"] == []

    @pytest.mark.asyncio
    async def test_damages_list_empty(
        self, client: AsyncClient, sample_assessment: Assessment
    ):
        resp = await client.get(f"/api/v1/assessments/{sample_assessment.id}/damages")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    @pytest.mark.asyncio
    async def test_damages_list_with_items(
        self, client: AsyncClient, sample_assessment: Assessment, db_session: AsyncSession
    ):
        # Insert damage items directly
        d = DamageItem(
            id=uuid.uuid4(),
            assessment_id=sample_assessment.id,
            damage_id="DMG-001",
            location="Front bumper",
            vehicle_zone=VehicleZone.FRONT_CENTER,
            damage_type="Dent",
            severity=DamageSeverity.MODERATE,
            description="8-inch dent on bumper",
            affected_parts=["Front bumper cover"],
            repair_method="Replace",
            estimated_cost_low=800,
            estimated_cost_high=1200,
            confidence_score=0.85,
            reference_frame_paths=["frame_0001.jpg"],
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(d)
        await db_session.commit()

        resp = await client.get(f"/api/v1/assessments/{sample_assessment.id}/damages")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["damage_id"] == "DMG-001"
        assert body["items"][0]["severity"] == "moderate"

    @pytest.mark.asyncio
    async def test_report_nonexistent_assessment(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/v1/assessments/{fake_id}/report")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_pdf_not_ready(
        self, client: AsyncClient, sample_assessment: Assessment
    ):
        mock_blob.download_blob.side_effect = FileNotFoundError("not found")
        resp = await client.get(f"/api/v1/assessments/{sample_assessment.id}/report/pdf")
        assert resp.status_code == 404
        mock_blob.download_blob.side_effect = None  # reset


# --- Tests: Frames Endpoint ---


class TestFramesEndpoint:
    @pytest.mark.asyncio
    async def test_frames_for_assessment(
        self, client: AsyncClient, sample_assessment: Assessment
    ):
        resp = await client.get(f"/api/v1/assessments/{sample_assessment.id}/frames")
        assert resp.status_code == 200
        body = resp.json()
        assert body["frames"]["exterior"]["count"] == 0
        assert body["frames"]["interior"]["count"] == 0

    @pytest.mark.asyncio
    async def test_frames_nonexistent(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/v1/assessments/{fake_id}/frames")
        assert resp.status_code == 404


# --- Tests: Splat Endpoints ---


class TestSplatEndpoints:
    @pytest.mark.asyncio
    async def test_splat_not_ready(
        self, client: AsyncClient, sample_assessment: Assessment
    ):
        resp = await client.get(
            f"/api/v1/assessments/{sample_assessment.id}/splat/exterior"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_splat_invalid_type(
        self, client: AsyncClient, sample_assessment: Assessment
    ):
        resp = await client.get(
            f"/api/v1/assessments/{sample_assessment.id}/splat/invalid"
        )
        assert resp.status_code == 400
