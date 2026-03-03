"""Tests for the COLMAP SfM service."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from app.services.colmap_service import COLMAPService


@pytest.fixture
def colmap():
    return COLMAPService(colmap_path="colmap", use_gpu=True)


class TestRunSfm:
    @patch("app.services.colmap_service.subprocess.run")
    def test_runs_all_three_steps(
        self,
        mock_run: MagicMock,
        colmap: COLMAPService,
        tmp_path: Path,
    ):
        """SfM should run feature_extractor, exhaustive_matcher, mapper."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        output_dir = tmp_path / "colmap_output"

        # Create a fake sparse reconstruction dir that mapper would produce
        def side_effect(cmd, **kwargs):
            if "mapper" in cmd:
                # Simulate mapper creating output
                sparse_0 = output_dir / "sparse" / "0"
                sparse_0.mkdir(parents=True, exist_ok=True)
                (sparse_0 / "cameras.bin").touch()
                (sparse_0 / "images.bin").touch()
                (sparse_0 / "points3D.bin").touch()
            return MagicMock(returncode=0, stderr="")

        mock_run.side_effect = side_effect

        result = colmap.run_sfm(frames_dir, output_dir)

        # Should have been called 3 times
        assert mock_run.call_count == 3

        # Verify each step was called
        calls = [c[0][0] for c in mock_run.call_args_list]
        assert "feature_extractor" in calls[0][1]
        assert "exhaustive_matcher" in calls[1][1]
        assert "mapper" in calls[2][1]

        # Result should be the sparse/0 directory
        assert result.name == "0"
        assert result.parent.name == "sparse"

    @patch("app.services.colmap_service.subprocess.run")
    def test_feature_extractor_uses_gpu_flag(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ):
        """GPU flag should be passed to feature extractor."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        gpu_colmap = COLMAPService(use_gpu=True)
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        db_path = tmp_path / "db.db"

        gpu_colmap._run_feature_extractor(frames_dir, db_path)

        cmd = mock_run.call_args[0][0]
        gpu_idx = cmd.index("--SiftExtraction.use_gpu")
        assert cmd[gpu_idx + 1] == "1"

    @patch("app.services.colmap_service.subprocess.run")
    def test_no_gpu_flag(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ):
        """CPU-only mode should pass use_gpu=0."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        cpu_colmap = COLMAPService(use_gpu=False)
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        db_path = tmp_path / "db.db"

        cpu_colmap._run_feature_extractor(frames_dir, db_path)

        cmd = mock_run.call_args[0][0]
        gpu_idx = cmd.index("--SiftExtraction.use_gpu")
        assert cmd[gpu_idx + 1] == "0"

    @patch("app.services.colmap_service.subprocess.run")
    def test_mapper_failure_raises(
        self,
        mock_run: MagicMock,
        colmap: COLMAPService,
        tmp_path: Path,
    ):
        """If mapper fails, run_sfm should raise RuntimeError."""

        def side_effect(cmd, **kwargs):
            if "mapper" in cmd:
                return MagicMock(returncode=1, stderr="Mapper crashed")
            return MagicMock(returncode=0, stderr="")

        mock_run.side_effect = side_effect

        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        output_dir = tmp_path / "colmap_output"

        with pytest.raises(RuntimeError, match="COLMAP mapper failed"):
            colmap.run_sfm(frames_dir, output_dir)

    @patch("app.services.colmap_service.subprocess.run")
    def test_no_reconstruction_raises(
        self,
        mock_run: MagicMock,
        colmap: COLMAPService,
        tmp_path: Path,
    ):
        """If mapper produces no reconstruction dirs, should raise."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        output_dir = tmp_path / "colmap_output"

        with pytest.raises(RuntimeError, match="no reconstructions"):
            colmap.run_sfm(frames_dir, output_dir)

    @patch("app.services.colmap_service.subprocess.run")
    def test_timeout_raises(
        self,
        mock_run: MagicMock,
        colmap: COLMAPService,
        tmp_path: Path,
    ):
        """Subprocess timeout should raise RuntimeError."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("colmap", 600)

        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()

        with pytest.raises(RuntimeError, match="timed out"):
            colmap._run_feature_extractor(frames_dir, tmp_path / "db.db")
