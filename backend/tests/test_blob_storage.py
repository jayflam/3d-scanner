"""Tests for BlobStorageService with local filesystem fallback."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Stub heavy deps
for mod in ("torch", "trimesh", "trimesh.visual", "trimesh.visual.material",
            "xatlas", "einops", "rembg", "rembg.sessions"):
    sys.modules.setdefault(mod, MagicMock())
fake_tsr = MagicMock()
sys.modules.setdefault("tsr", fake_tsr)
sys.modules.setdefault("tsr.system", fake_tsr.system)
sys.modules.setdefault("tsr.bake_texture", fake_tsr.bake_texture)

import pytest

from app.services.blob_storage import BlobStorageService


@pytest.fixture
def blob_service(tmp_path: Path) -> BlobStorageService:
    """Create a BlobStorageService backed by a temporary directory."""
    svc = BlobStorageService()
    svc._local_root = tmp_path
    svc._container_client = None  # ensure local fallback
    return svc


class TestLocalFallbackInit:
    def test_is_not_azure(self, blob_service: BlobStorageService):
        assert blob_service.is_azure is False

    def test_get_blob_url_returns_local_path(self, blob_service: BlobStorageService):
        url = blob_service.get_blob_url("videos/abc/exterior.mp4")
        assert url == "/blob/videos/abc/exterior.mp4"


class TestUploadVideo:
    def test_upload_video_creates_file(self, blob_service: BlobStorageService):
        stream = io.BytesIO(b"fake video data")
        path = blob_service.upload_video("test-id", "exterior", stream)

        assert path == "videos/test-id/exterior.mp4"
        local_file = blob_service._local_root / path
        assert local_file.exists()
        assert local_file.read_bytes() == b"fake video data"

    def test_upload_interior_video(self, blob_service: BlobStorageService):
        stream = io.BytesIO(b"interior data")
        path = blob_service.upload_video("test-id", "interior", stream)

        assert path == "videos/test-id/interior.mp4"
        local_file = blob_service._local_root / path
        assert local_file.read_bytes() == b"interior data"


class TestUploadFrame:
    def test_upload_frame_creates_numbered_file(self, blob_service: BlobStorageService):
        path = blob_service.upload_frame("test-id", "exterior", 1, b"jpg-bytes")

        assert path == "frames/test-id/exterior/frame_0001.jpg"
        local_file = blob_service._local_root / path
        assert local_file.exists()
        assert local_file.read_bytes() == b"jpg-bytes"

    def test_upload_multiple_frames(self, blob_service: BlobStorageService):
        for i in range(1, 4):
            blob_service.upload_frame("test-id", "exterior", i, f"frame-{i}".encode())

        for i in range(1, 4):
            local_file = blob_service._local_root / f"frames/test-id/exterior/frame_{i:04d}.jpg"
            assert local_file.read_bytes() == f"frame-{i}".encode()


class TestUploadSplat:
    def test_upload_splat_from_file(self, blob_service: BlobStorageService, tmp_path: Path):
        # Create a fake .ply file
        ply_file = tmp_path / "source.ply"
        ply_file.write_bytes(b"ply data")

        path = blob_service.upload_splat("test-id", "exterior", ply_file)

        assert path == "splats/test-id/exterior.ply"
        stored = blob_service._local_root / path
        assert stored.read_bytes() == b"ply data"


class TestUploadReport:
    def test_upload_pdf_report(self, blob_service: BlobStorageService):
        path = blob_service.upload_report("test-id", b"pdf-bytes", "pdf")

        assert path == "reports/test-id/report.pdf"
        stored = blob_service._local_root / path
        assert stored.read_bytes() == b"pdf-bytes"

    def test_upload_json_report(self, blob_service: BlobStorageService):
        path = blob_service.upload_report("test-id", b'{"key":"val"}', "json")

        assert path == "reports/test-id/report.json"
        stored = blob_service._local_root / path
        assert stored.read_bytes() == b'{"key":"val"}'


class TestDownloadBlob:
    def test_download_existing_blob(self, blob_service: BlobStorageService):
        # Upload first
        blob_service._upload_bytes("test/file.txt", b"hello world")

        data = blob_service.download_blob("test/file.txt")
        assert data == b"hello world"

    def test_download_missing_blob_raises(self, blob_service: BlobStorageService):
        with pytest.raises(FileNotFoundError, match="Blob not found"):
            blob_service.download_blob("nonexistent/path.txt")


class TestGetLocalPath:
    def test_returns_correct_path(self, blob_service: BlobStorageService):
        path = blob_service.get_local_path("videos/abc/exterior.mp4")
        assert path == blob_service._local_root / "videos/abc/exterior.mp4"


class TestRoundTrip:
    def test_upload_then_download_video(self, blob_service: BlobStorageService):
        original = b"roundtrip video content"
        stream = io.BytesIO(original)
        blob_path = blob_service.upload_video("rt-id", "exterior", stream)

        downloaded = blob_service.download_blob(blob_path)
        assert downloaded == original

    def test_upload_then_download_frame(self, blob_service: BlobStorageService):
        original = b"frame pixel data"
        blob_path = blob_service.upload_frame("rt-id", "interior", 42, original)

        downloaded = blob_service.download_blob(blob_path)
        assert downloaded == original
