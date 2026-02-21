#!/usr/bin/env python3
"""Demo script: runs the backend, uploads a test image, polls for completion,
downloads the GLB file to disk, and prints the damage assessment.

Usage:
    cd backend && source .venv/bin/activate && python run_demo.py

Produces:
    demo_output/model.glb   — a real GLB 3D model file (viewable in any 3D viewer)
    demo_output/result.json  — the full job result including damage assessment
"""

from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import trimesh
from PIL import Image

# ---------------------------------------------------------------------------
# Stub out heavy ML dependencies that aren't available locally
# ---------------------------------------------------------------------------
import importlib

for mod_name in (
    "tsr", "tsr.system", "tsr.bake_texture",
    "torch", "einops", "xatlas", "moderngl",
):
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

fake_rembg = MagicMock()
fake_rembg.remove = lambda img, **kw: img.convert("RGBA")
fake_rembg.new_session = MagicMock(return_value=MagicMock())
fake_rembg.sessions = MagicMock()
sys.modules["rembg"] = fake_rembg
sys.modules["rembg.sessions"] = fake_rembg.sessions

# ---------------------------------------------------------------------------
# Build a real GLB mesh (simple car-like box shape)
# ---------------------------------------------------------------------------


def _generate_real_glb(self, image: Image.Image, output_path: Path, **kwargs) -> Path:
    """Generate a real textured GLB file using trimesh primitives."""
    body = trimesh.creation.box(extents=[4.0, 1.5, 1.2])
    body.apply_translation([0, 0, 0.6])

    cabin = trimesh.creation.box(extents=[2.0, 1.3, 0.9])
    cabin.apply_translation([0, 0, 1.65])

    fl_wheel = trimesh.creation.cylinder(radius=0.35, height=0.2)
    fl_wheel.apply_translation([-1.2, -0.85, 0.0])
    fr_wheel = trimesh.creation.cylinder(radius=0.35, height=0.2)
    fr_wheel.apply_translation([-1.2, 0.85, 0.0])
    rl_wheel = trimesh.creation.cylinder(radius=0.35, height=0.2)
    rl_wheel.apply_translation([1.2, -0.85, 0.0])
    rr_wheel = trimesh.creation.cylinder(radius=0.35, height=0.2)
    rr_wheel.apply_translation([1.2, 0.85, 0.0])

    body.visual.face_colors = [70, 130, 180, 255]
    cabin.visual.face_colors = [200, 220, 240, 200]
    for w in (fl_wheel, fr_wheel, rl_wheel, rr_wheel):
        w.visual.face_colors = [40, 40, 40, 255]

    scene = trimesh.Scene([body, cabin, fl_wheel, fr_wheel, rl_wheel, rr_wheel])

    glb_path = Path(output_path).with_suffix(".glb")
    glb_path.parent.mkdir(parents=True, exist_ok=True)
    scene.export(str(glb_path), file_type="glb")
    return glb_path


# ---------------------------------------------------------------------------
# Patch TripoSRService to use the real GLB generator
# ---------------------------------------------------------------------------
from app.services.triposr import TripoSRService

_original_init = TripoSRService.__init__


def _patched_init(self):
    _original_init(self)
    self._model = MagicMock()
    self._rembg_session = MagicMock()
    self._device = "cpu"


TripoSRService.__init__ = _patched_init
TripoSRService.load = lambda self, **kw: None
TripoSRService.generate_glb = _generate_real_glb
TripoSRService.is_ready = lambda self: True

# ---------------------------------------------------------------------------
# Now import and run the app
# ---------------------------------------------------------------------------
from fastapi.testclient import TestClient
from app.main import app

OUTPUT_DIR = Path("demo_output")
OUTPUT_DIR.mkdir(exist_ok=True)


def main():
    print("=" * 60)
    print("  Car Damage Quote API — Backend Demo")
    print("=" * 60)

    # Create a test image (red square simulating a car photo)
    img = Image.new("RGB", (256, 256), color=(180, 40, 40))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    image_bytes = buf.getvalue()

    with TestClient(app) as client:
        # 1. Health check
        print("\n[1/5] Health check …")
        resp = client.get("/api/health")
        assert resp.status_code == 200
        print(f"      GET /api/health → {resp.json()}")

        # 2. Upload image
        print("\n[2/5] Uploading image …")
        resp = client.post(
            "/api/upload",
            files={"file": ("damaged_car.png", image_bytes, "image/png")},
        )
        assert resp.status_code == 200
        upload = resp.json()
        job_id = upload["job_id"]
        print(f"      POST /api/upload → job_id={job_id}  status={upload['status']}")

        # 3. Poll until complete
        print("\n[3/5] Polling job status …")
        deadline = time.time() + 15
        status_body = None
        while time.time() < deadline:
            resp = client.get(f"/api/jobs/{job_id}")
            status_body = resp.json()
            s = status_body["status"]
            pct = status_body["progress_pct"]
            msg = status_body["message"]
            print(f"      GET /api/jobs/{job_id} → status={s}  progress={pct}%  msg={msg}")
            if s in ("complete", "failed"):
                break
            time.sleep(0.3)

        assert status_body["status"] == "complete", f"Job failed: {status_body}"

        # 4. Get result (assessment + model URL)
        print("\n[4/5] Fetching result …")
        resp = client.get(f"/api/jobs/{job_id}/result")
        assert resp.status_code == 200
        result = resp.json()

        result_path = OUTPUT_DIR / "result.json"
        result_path.write_text(json.dumps(result, indent=2))
        print(f"      GET /api/jobs/{job_id}/result → saved to {result_path}")

        assessment = result["assessment"]
        print(f"\n      Vehicle:  {assessment['vehicle_description']}")
        print(f"      Severity: {assessment['overall_severity']}")
        print(f"      Cost:     ${assessment['total_cost_low']:,.0f} – ${assessment['total_cost_high']:,.0f}")
        print(f"      Parts:")
        for p in assessment["parts"]:
            print(f"        • {p['part_name']}: {p['severity']} — "
                  f"${p['cost_low']:,.0f}–${p['cost_high']:,.0f} ({p['repair_type']})")
            print(f"          {p['description']}")
        print(f"      Summary: {assessment['summary']}")

        # 5. Download GLB
        print(f"\n[5/5] Downloading 3D model …")
        resp = client.get(f"/api/jobs/{job_id}/model")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "model/gltf-binary"

        glb_path = OUTPUT_DIR / "model.glb"
        glb_path.write_bytes(resp.content)
        size_kb = len(resp.content) / 1024
        print(f"      GET /api/jobs/{job_id}/model → saved to {glb_path}  ({size_kb:.1f} KB)")

        # Verify the GLB is a valid trimesh scene
        loaded = trimesh.load(str(glb_path), file_type="glb")
        if isinstance(loaded, trimesh.Scene):
            geom_count = len(loaded.geometry)
        else:
            geom_count = 1
        print(f"      Verified: valid GLB with {geom_count} geometries")

    print("\n" + "=" * 60)
    print("  Demo complete!")
    print(f"  Output files:")
    print(f"    {glb_path.resolve()}  — open in any 3D viewer")
    print(f"    {result_path.resolve()}  — damage assessment JSON")
    print("=" * 60)


if __name__ == "__main__":
    main()
