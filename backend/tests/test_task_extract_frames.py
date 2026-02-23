"""Tests for the extract_frames Celery task."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestExtractFramesTask:
    @patch("app.tasks.extract_frames._complete_processing_job")
    @patch("app.tasks.extract_frames._create_processing_job", return_value="job-123")
    @patch("app.tasks.extract_frames._update_db")
    @patch("app.tasks.extract_frames._publish_progress")
    @patch("app.tasks.extract_frames.blob_storage")
    @patch("app.tasks.extract_frames.FrameExtractorService")
    def test_successful_extraction(
        self,
        MockExtractor,
        mock_blob,
        mock_progress,
        mock_update_db,
        mock_create_job,
        mock_complete_job,
        tmp_path: Path,
    ):
        """Happy path: frames extracted and uploaded."""
        from app.tasks.extract_frames import extract_frames_task

        # Setup mock extractor
        extractor_instance = MagicMock()
        frame_paths = [tmp_path / f"frame_{i:04d}.jpg" for i in range(1, 4)]
        for p in frame_paths:
            p.write_bytes(b"fake jpeg")
        extractor_instance.extract_frames.return_value = frame_paths
        MockExtractor.return_value = extractor_instance

        # Setup mock blob
        mock_blob.download_blob.return_value = b"fake video data"
        mock_blob.upload_frame.side_effect = [
            f"frames/test-id/exterior/frame_{i:04d}.jpg" for i in range(1, 4)
        ]

        # Mock self (Celery task context)
        mock_self = MagicMock()
        mock_self.request.id = "celery-task-123"

        result = extract_frames_task.__wrapped__(
            mock_self, "test-id", "exterior"
        )

        assert result["frame_count"] == 3
        assert result["video_type"] == "exterior"
        assert len(result["frame_paths"]) == 3
        mock_blob.download_blob.assert_called_once()
        assert mock_blob.upload_frame.call_count == 3
        mock_complete_job.assert_called_once_with("job-123")

    @patch("app.tasks.extract_frames._complete_processing_job")
    @patch("app.tasks.extract_frames._create_processing_job", return_value="job-123")
    @patch("app.tasks.extract_frames._update_db")
    @patch("app.tasks.extract_frames._publish_progress")
    @patch("app.tasks.extract_frames.blob_storage")
    @patch("app.tasks.extract_frames.FrameExtractorService")
    def test_extraction_failure_marks_failed(
        self,
        MockExtractor,
        mock_blob,
        mock_progress,
        mock_update_db,
        mock_create_job,
        mock_complete_job,
    ):
        """When FFmpeg fails, task should mark job as failed and re-raise."""
        from app.tasks.extract_frames import extract_frames_task

        mock_blob.download_blob.side_effect = FileNotFoundError("Video not found")

        mock_self = MagicMock()
        mock_self.request.id = "celery-task-456"

        with pytest.raises(FileNotFoundError):
            extract_frames_task.__wrapped__(mock_self, "test-id", "exterior")

        # Should mark job as failed
        mock_complete_job.assert_called_once_with("job-123", error="Video not found")
        # Should update assessment status to failed
        mock_update_db.assert_called()
