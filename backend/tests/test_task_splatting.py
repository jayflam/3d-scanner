"""Tests for the run_splatting Celery task."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestRunSplattingTask:
    @patch("app.tasks.run_splatting._complete_processing_job")
    @patch("app.tasks.run_splatting._create_processing_job", return_value="job-123")
    @patch("app.tasks.run_splatting._update_db")
    @patch("app.tasks.run_splatting._publish_progress")
    @patch("app.tasks.run_splatting.GaussianSplatService")
    @patch("app.tasks.run_splatting.COLMAPService")
    @patch("app.tasks.run_splatting.blob_storage")
    def test_successful_splatting(
        self,
        mock_blob,
        MockCOLMAP,
        MockGS,
        mock_progress,
        mock_update_db,
        mock_create_job,
        mock_complete_job,
        tmp_path: Path,
    ):
        """Happy path: COLMAP + splatting + PLY export."""
        from app.tasks.run_splatting import run_splatting_task

        # Setup: blob has 2 frames, then raises FileNotFoundError on 3rd
        call_count = [0]

        def download_side_effect(blob_path):
            call_count[0] += 1
            if call_count[0] <= 2:
                return b"fake jpeg"
            raise FileNotFoundError("No more frames")

        mock_blob.download_blob.side_effect = download_side_effect
        mock_blob.upload_splat.return_value = "splats/test-id/exterior.ply"

        # Setup COLMAP mock
        colmap_instance = MagicMock()
        colmap_instance.run_sfm.return_value = tmp_path / "colmap" / "sparse" / "0"
        MockCOLMAP.return_value = colmap_instance

        # Setup GS mock
        gs_instance = MagicMock()
        gs_instance.prepare_data_dir.return_value = tmp_path / "ns_data"
        gs_instance.train.return_value = tmp_path / "gs_output"

        def export_side_effect(model_dir, output_path):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake ply data")
            return output_path

        gs_instance.export_ply.side_effect = export_side_effect
        MockGS.return_value = gs_instance

        mock_self = MagicMock()
        mock_self.request.id = "celery-task-123"

        result = run_splatting_task.__wrapped__(mock_self, "test-id", "exterior")

        assert result["splat_blob_path"] == "splats/test-id/exterior.ply"
        colmap_instance.run_sfm.assert_called_once()
        gs_instance.train.assert_called_once()
        gs_instance.export_ply.assert_called_once()
        mock_complete_job.assert_called_once_with("job-123")

    @patch("app.tasks.run_splatting._complete_processing_job")
    @patch("app.tasks.run_splatting._create_processing_job", return_value="job-123")
    @patch("app.tasks.run_splatting._update_db")
    @patch("app.tasks.run_splatting._publish_progress")
    @patch("app.tasks.run_splatting.blob_storage")
    def test_no_frames_raises(
        self,
        mock_blob,
        mock_progress,
        mock_update_db,
        mock_create_job,
        mock_complete_job,
    ):
        """Should fail if no frames found in blob."""
        from app.tasks.run_splatting import run_splatting_task

        mock_blob.download_blob.side_effect = FileNotFoundError("No frames")

        mock_self = MagicMock()
        mock_self.request.id = "celery-task-456"

        with pytest.raises(RuntimeError, match="No frames found"):
            run_splatting_task.__wrapped__(mock_self, "test-id", "exterior")

        mock_complete_job.assert_called_once()
        assert "No frames found" in mock_complete_job.call_args[1]["error"]
