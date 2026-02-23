"""Tests for the pipeline orchestration module."""

from unittest.mock import MagicMock, patch

import pytest


class TestStartPipeline:
    @patch("app.tasks.pipeline.generate_report_task")
    @patch("app.tasks.pipeline.analyze_damage_task")
    @patch("app.tasks.pipeline.run_splatting_task")
    @patch("app.tasks.pipeline.extract_frames_task")
    @patch("app.tasks.pipeline._noop")
    def test_full_pipeline_both_videos(
        self,
        mock_noop,
        mock_extract,
        mock_splat,
        mock_analyze,
        mock_report,
    ):
        """Pipeline with both exterior and interior videos."""
        from app.tasks.pipeline import start_pipeline

        # Mock task signatures
        mock_extract.si.return_value = MagicMock()
        mock_splat.si.return_value = MagicMock()
        mock_analyze.si.return_value = MagicMock()
        mock_report.si.return_value = MagicMock()
        mock_noop.si.return_value = MagicMock()

        # Mock the chain/chord apply_async
        with patch("app.tasks.pipeline.chain") as mock_chain:
            mock_result = MagicMock()
            mock_result.id = "pipeline-task-id"
            mock_chain.return_value.apply_async.return_value = mock_result

            task_id = start_pipeline("test-assessment-id")

        assert task_id == "pipeline-task-id"
        # Should create extraction tasks for both videos
        assert mock_extract.si.call_count == 2
        # Should create splatting tasks for both + analysis
        assert mock_splat.si.call_count == 2
        mock_analyze.si.assert_called_once()
        mock_report.si.assert_called_once()

    @patch("app.tasks.pipeline.generate_report_task")
    @patch("app.tasks.pipeline.analyze_damage_task")
    @patch("app.tasks.pipeline.run_splatting_task")
    @patch("app.tasks.pipeline.extract_frames_task")
    @patch("app.tasks.pipeline._noop")
    def test_exterior_only_pipeline(
        self,
        mock_noop,
        mock_extract,
        mock_splat,
        mock_analyze,
        mock_report,
    ):
        """Pipeline with only exterior video."""
        from app.tasks.pipeline import start_pipeline

        mock_extract.si.return_value = MagicMock()
        mock_splat.si.return_value = MagicMock()
        mock_analyze.si.return_value = MagicMock()
        mock_report.si.return_value = MagicMock()
        mock_noop.si.return_value = MagicMock()

        with patch("app.tasks.pipeline.chain") as mock_chain:
            mock_result = MagicMock()
            mock_result.id = "pipeline-task-id"
            mock_chain.return_value.apply_async.return_value = mock_result

            start_pipeline("test-id", has_exterior=True, has_interior=False)

        # Should only create 1 extraction and 1 splatting task
        assert mock_extract.si.call_count == 1
        assert mock_splat.si.call_count == 1

    def test_no_videos_raises(self):
        """Should raise ValueError if no videos specified."""
        from app.tasks.pipeline import start_pipeline

        with pytest.raises(ValueError, match="At least one video"):
            start_pipeline("test-id", has_exterior=False, has_interior=False)


class TestStartSingleVideoPipeline:
    @patch("app.tasks.pipeline.generate_report_task")
    @patch("app.tasks.pipeline.analyze_damage_task")
    @patch("app.tasks.pipeline.run_splatting_task")
    @patch("app.tasks.pipeline.extract_frames_task")
    @patch("app.tasks.pipeline._noop")
    def test_single_video_pipeline(
        self,
        mock_noop,
        mock_extract,
        mock_splat,
        mock_analyze,
        mock_report,
    ):
        """Single video pipeline: extract -> (splat + analyze) -> report."""
        from app.tasks.pipeline import start_single_video_pipeline

        mock_extract.si.return_value = MagicMock()
        mock_splat.si.return_value = MagicMock()
        mock_analyze.si.return_value = MagicMock()
        mock_report.si.return_value = MagicMock()
        mock_noop.si.return_value = MagicMock()

        with patch("app.tasks.pipeline.chain") as mock_chain:
            mock_result = MagicMock()
            mock_result.id = "single-pipeline-id"
            mock_chain.return_value.apply_async.return_value = mock_result

            task_id = start_single_video_pipeline("test-id", "exterior")

        assert task_id == "single-pipeline-id"
        mock_extract.si.assert_called_once_with("test-id", "exterior")
        mock_splat.si.assert_called_once_with("test-id", "exterior")
        mock_analyze.si.assert_called_once_with("test-id")
        mock_report.si.assert_called_once_with("test-id")
