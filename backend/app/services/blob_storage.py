"""Azure Blob Storage service with local filesystem fallback.

When AZURE_BLOB_CONNECTION_STRING is not set, files are stored
under data/blob/ on the local filesystem for development.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import BinaryIO

from app.config import settings

logger = logging.getLogger(__name__)


class BlobStorageService:
    """Upload/download blobs to Azure Blob Storage or local disk."""

    def __init__(self) -> None:
        self._container_client = None
        self._local_root: Path = settings.output_dir / "blob"

    def init(self) -> None:
        if settings.azure_blob_connection_string:
            try:
                from azure.storage.blob import ContainerClient

                self._container_client = ContainerClient.from_connection_string(
                    settings.azure_blob_connection_string,
                    container_name=settings.azure_blob_container_name,
                )
                # Ensure container exists
                try:
                    self._container_client.create_container()
                except Exception:
                    pass  # container already exists
                logger.info(
                    "Azure Blob Storage ready (container=%s)",
                    settings.azure_blob_container_name,
                )
                return
            except Exception as exc:
                logger.warning("Azure Blob init failed, falling back to local: %s", exc)

        self._local_root.mkdir(parents=True, exist_ok=True)
        logger.info("Using local filesystem blob storage at %s", self._local_root)

    @property
    def is_azure(self) -> bool:
        return self._container_client is not None

    # ── Upload methods ────────────────────────────────────────────────

    def upload_video(
        self, assessment_id: str, video_type: str, file_stream: BinaryIO
    ) -> str:
        blob_path = f"videos/{assessment_id}/{video_type}.mp4"
        self._upload(blob_path, file_stream)
        return blob_path

    def upload_frame(
        self,
        assessment_id: str,
        video_type: str,
        frame_number: int,
        image_bytes: bytes,
    ) -> str:
        blob_path = f"frames/{assessment_id}/{video_type}/frame_{frame_number:04d}.jpg"
        self._upload_bytes(blob_path, image_bytes)
        return blob_path

    def upload_splat(
        self, assessment_id: str, splat_type: str, file_path: str | Path
    ) -> str:
        blob_path = f"splats/{assessment_id}/{splat_type}.ply"
        with open(file_path, "rb") as f:
            self._upload(blob_path, f)
        return blob_path

    def upload_report(
        self, assessment_id: str, report_bytes: bytes, fmt: str = "pdf"
    ) -> str:
        blob_path = f"reports/{assessment_id}/report.{fmt}"
        self._upload_bytes(blob_path, report_bytes)
        return blob_path

    # ── Download / URL methods ────────────────────────────────────────

    def get_blob_url(self, blob_path: str) -> str:
        if self._container_client is not None:
            from datetime import datetime, timedelta, timezone

            from azure.storage.blob import BlobSasPermissions, generate_blob_sas

            sas_token = generate_blob_sas(
                account_name=self._container_client.account_name,
                container_name=self._container_client.container_name,
                blob_name=blob_path,
                account_key=self._container_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now(timezone.utc) + timedelta(hours=1),
            )
            return f"{self._container_client.url}/{blob_path}?{sas_token}"

        # Local fallback: serve from the file system path
        return f"/blob/{blob_path}"

    def download_blob(self, blob_path: str) -> bytes:
        if self._container_client is not None:
            try:
                blob_client = self._container_client.get_blob_client(blob_path)
                return blob_client.download_blob().readall()
            except Exception as exc:
                # Normalize Azure ResourceNotFoundError to FileNotFoundError so callers
                # can use a single exception type regardless of storage backend.
                err_code = getattr(exc, "error_code", None)
                if err_code == "BlobNotFound" or "BlobNotFound" in str(exc):
                    raise FileNotFoundError(f"Blob not found: {blob_path}") from exc
                raise

        local_path = self._local_root / blob_path
        if not local_path.exists():
            raise FileNotFoundError(f"Blob not found: {blob_path}")
        return local_path.read_bytes()

    def get_local_path(self, blob_path: str) -> Path:
        """For local fallback, return the filesystem path."""
        return self._local_root / blob_path

    # ── Internal helpers ──────────────────────────────────────────────

    def _upload(self, blob_path: str, stream: BinaryIO) -> None:
        if self._container_client is not None:
            blob_client = self._container_client.get_blob_client(blob_path)
            blob_client.upload_blob(stream, overwrite=True)
            logger.debug("Uploaded to Azure: %s", blob_path)
            return

        local_path = self._local_root / blob_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            shutil.copyfileobj(stream, f)
        logger.debug("Saved locally: %s", local_path)

    def _upload_bytes(self, blob_path: str, data: bytes) -> None:
        if self._container_client is not None:
            blob_client = self._container_client.get_blob_client(blob_path)
            blob_client.upload_blob(data, overwrite=True)
            logger.debug("Uploaded to Azure: %s", blob_path)
            return

        local_path = self._local_root / blob_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
        logger.debug("Saved locally: %s", local_path)


# Module-level singleton
blob_storage = BlobStorageService()
