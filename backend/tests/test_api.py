"""Integration tests for the Car Damage Quote API.

Mocks the TripoSR model (no GPU required) and uses the placeholder damage
assessment (no Azure OpenAI credentials required) to validate the full
upload → process → result flow.
"""

from __future__ import annotations

import asyncio
import io
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image


# ── Patch heavy imports before they're loaded ──────────────────────────────

# Create a fake `tsr` package so triposr.py can import from it without
# the real TripoSR repo on the PYTHONPATH.
import sys
fake_tsr = MagicMock()
sys.modules["tsr"] = fake_tsr
sys.modules["tsr.system"] = fake_tsr.system
sys.modules["tsr.bake_texture"] = fake_tsr.bake_texture

# Stub out rembg so it doesn't download ONNX models
fake_rembg = MagicMock()
fake_rembg.remove = lambda img, **kw: img.convert("RGBA")
fake_rembg.new_session = MagicMock(return_value=MagicMock())
fake_rembg.sessions = MagicMock()
sys.modules.setdefault("rembg", fake_rembg)
sys.modules.setdefault("rembg.sessions", fake_rembg.sessions)

# Stub optional heavy deps that aren't used during testing
for mod in ("torch", "trimesh", "trimesh.visual", "trimesh.visual.material",
            "xatlas", "einops"):
    sys.modules.setdefault(mod, MagicMock())

# ── Now safe to import application code ────────────────────────────────────

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
# Legacy services are lazy-loaded in main.py lifespan; import them after app is created
import app.main as main_module


# ── Fixtures ───────────────────────────────────────────────────────────────


def _make_test_image() -> bytes:
    """Create a small red PNG in memory."""
    img = Image.new("RGB", (64, 64), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def _stub_generate_glb(image, output_path, **kwargs) -> Path:
    """Write a tiny placeholder file instead of running real inference."""
    glb_path = Path(output_path).with_suffix(".glb")
    glb_path.parent.mkdir(parents=True, exist_ok=True)
    glb_path.write_bytes(b"FAKE-GLB-CONTENT")
    return glb_path


@pytest.fixture(autouse=True)
def _setup_legacy_services():
    """Initialize legacy services on main_module for testing.

    Sets module-level globals BEFORE the TestClient lifespan runs so the
    lifespan's ``if triposr_service is None`` guard skips re-creation.
    """
    from app.services.triposr import TripoSRService
    from app.services.damage import DamageAssessmentService
    from app.services.job_manager import JobManager
    from app.api.routes import init_routes, router as legacy_router
    from app.api.websocket import init_ws

    triposr_svc = TripoSRService()
    damage_svc = DamageAssessmentService()
    job_mgr = JobManager(triposr_svc, damage_svc)

    main_module.triposr_service = triposr_svc
    main_module.damage_service = damage_svc
    main_module.job_manager = job_mgr

    triposr_svc._model = MagicMock()
    triposr_svc._rembg_session = MagicMock()
    triposr_svc._device = "cpu"

    damage_svc.load()
    init_routes(job_mgr)
    init_ws(job_mgr)

    # Mount legacy routes on the app for testing
    app.include_router(legacy_router)

    with patch.object(triposr_svc, "generate_glb", side_effect=_stub_generate_glb):
        yield

    # Clean up module globals so other test files aren't affected
    main_module.triposr_service = None
    main_module.damage_service = None
    main_module.job_manager = None


@pytest.fixture()
def client(_setup_legacy_services):
    """Provide a TestClient with lifespan events handled."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── Tests ──────────────────────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestUploadEndpoint:
    def test_upload_accepts_png(self, client: TestClient):
        image_bytes = _make_test_image()
        resp = client.post(
            "/api/upload",
            files={"file": ("car.png", image_bytes, "image/png")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "pending"
        assert body["message"] == "Image uploaded — processing started"

    def test_upload_rejects_non_image(self, client: TestClient):
        resp = client.post(
            "/api/upload",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400

    def test_upload_rejects_unsupported_extension(self, client: TestClient):
        resp = client.post(
            "/api/upload",
            files={"file": ("car.bmp", b"\x00" * 100, "image/bmp")},
        )
        assert resp.status_code == 400


class TestJobStatusEndpoint:
    def test_unknown_job_returns_404(self, client: TestClient):
        resp = client.get("/api/jobs/nonexistent")
        assert resp.status_code == 404

    def test_status_returns_after_upload(self, client: TestClient):
        image_bytes = _make_test_image()
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("car.png", image_bytes, "image/png")},
        )
        job_id = upload_resp.json()["job_id"]

        resp = client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == job_id
        assert body["status"] in (
            "pending", "preprocessing", "generating_3d",
            "assessing_damage", "complete",
        )
        assert 0 <= body["progress_pct"] <= 100


class TestFullPipeline:
    def test_upload_then_poll_until_complete(self, client: TestClient):
        """End-to-end: upload → poll → get result → download model."""
        image_bytes = _make_test_image()

        # 1. Upload
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("car.png", image_bytes, "image/png")},
        )
        assert upload_resp.status_code == 200
        job_id = upload_resp.json()["job_id"]
        print(f"\n  ✓ Upload succeeded — job_id={job_id}")

        # 2. Poll until complete (timeout after 10s)
        deadline = time.time() + 10
        final_status = None
        while time.time() < deadline:
            status_resp = client.get(f"/api/jobs/{job_id}")
            assert status_resp.status_code == 200
            body = status_resp.json()
            final_status = body["status"]
            print(f"  … status={final_status}  progress={body['progress_pct']}%  msg={body['message']}")
            if final_status in ("complete", "failed"):
                break
            time.sleep(0.3)

        assert final_status == "complete", f"Job did not complete, last status: {final_status}"
        print("  ✓ Job completed")

        # 3. Get result
        result_resp = client.get(f"/api/jobs/{job_id}/result")
        assert result_resp.status_code == 200
        result = result_resp.json()

        assert result["job_id"] == job_id
        assert result["status"] == "complete"
        assert result["model_url"] == f"/api/jobs/{job_id}/model"
        print(f"  ✓ Result retrieved — model_url={result['model_url']}")

        # 4. Validate damage assessment structure
        assessment = result["assessment"]
        assert "vehicle_description" in assessment
        assert "overall_severity" in assessment
        assert assessment["total_cost_low"] > 0
        assert assessment["total_cost_high"] >= assessment["total_cost_low"]
        assert len(assessment["parts"]) > 0
        for part in assessment["parts"]:
            assert "part_name" in part
            assert "severity" in part
            assert "repair_type" in part
            assert "cost_low" in part
            assert "cost_high" in part
            assert "description" in part
        print(f"  ✓ Damage assessment valid — {len(assessment['parts'])} parts found:")
        for p in assessment["parts"]:
            print(f"      • {p['part_name']}: {p['severity']} — ${p['cost_low']}-${p['cost_high']} ({p['repair_type']})")
        print(f"    Total: ${assessment['total_cost_low']}-${assessment['total_cost_high']}")
        print(f"    Summary: {assessment['summary']}")

        # 5. Download GLB model
        model_resp = client.get(f"/api/jobs/{job_id}/model")
        assert model_resp.status_code == 200
        assert model_resp.headers["content-type"] == "model/gltf-binary"
        assert len(model_resp.content) > 0
        print(f"  ✓ GLB model downloaded — {len(model_resp.content)} bytes")


class TestResultEdgeCases:
    def test_result_before_complete_returns_409(self, client: TestClient):
        """Requesting result for an in-progress job should return 409."""
        from app.services.job_manager import Job
        job = main_module.job_manager.create_job(image_path=Path("/fake"))
        resp = client.get(f"/api/jobs/{job.id}/result")
        assert resp.status_code == 409

    def test_model_download_before_ready_returns_409(self, client: TestClient):
        from app.services.job_manager import Job
        job = main_module.job_manager.create_job(image_path=Path("/fake"))
        resp = client.get(f"/api/jobs/{job.id}/model")
        assert resp.status_code == 409
