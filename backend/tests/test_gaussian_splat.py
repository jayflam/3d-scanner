"""Tests for the Gaussian Splatting service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.gaussian_splat import GaussianSplatService


@pytest.fixture
def splat():
    return GaussianSplatService(method="splatfacto")


class TestTrain:
    @patch("app.services.gaussian_splat.subprocess.run")
    def test_train_calls_ns_train(
        self,
        mock_run: MagicMock,
        splat: GaussianSplatService,
        tmp_path: Path,
    ):
        """Train should call ns-train with correct arguments."""

        def side_effect(cmd, **kwargs):
            # Simulate nerfstudio output directory structure
            method_dir = tmp_path / "output" / "splatfacto" / "2026-01-01_000000"
            method_dir.mkdir(parents=True, exist_ok=True)
            (method_dir / "config.yml").touch()
            return MagicMock(returncode=0, stderr="")

        mock_run.side_effect = side_effect

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        output_dir = tmp_path / "output"

        result = splat.train(data_dir, output_dir, iterations=7000)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "ns-train" in cmd[0]
        assert "splatfacto" in cmd
        assert "--max-num-iterations" in cmd
        assert "7000" in cmd
        assert str(data_dir) in cmd

    @patch("app.services.gaussian_splat.subprocess.run")
    def test_train_failure_raises(
        self,
        mock_run: MagicMock,
        splat: GaussianSplatService,
        tmp_path: Path,
    ):
        """Training failure should raise RuntimeError."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="CUDA out of memory",
        )

        with pytest.raises(RuntimeError, match="training failed"):
            splat.train(
                tmp_path / "data",
                tmp_path / "output",
            )

    @patch("app.services.gaussian_splat.subprocess.run")
    def test_train_timeout_raises(
        self,
        mock_run: MagicMock,
        splat: GaussianSplatService,
        tmp_path: Path,
    ):
        """Training timeout should raise RuntimeError."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("ns-train", 1800)

        with pytest.raises(RuntimeError, match="timed out"):
            splat.train(
                tmp_path / "data",
                tmp_path / "output",
            )


class TestExportPly:
    @patch("app.services.gaussian_splat.subprocess.run")
    def test_export_ply_calls_ns_export(
        self,
        mock_run: MagicMock,
        splat: GaussianSplatService,
        tmp_path: Path,
    ):
        """Export should call ns-export and return .ply path."""
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / "config.yml").touch()
        output_ply = model_dir / "output.ply"

        def side_effect(cmd, **kwargs):
            # Simulate ns-export creating the splat.ply
            output_ply.write_bytes(b"ply\n")
            return MagicMock(returncode=0, stderr="")

        mock_run.side_effect = side_effect

        result = splat.export_ply(model_dir, output_ply)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "ns-export" in cmd[0]
        assert "gaussian-splat" in cmd
        assert result == output_ply

    @patch("app.services.gaussian_splat.subprocess.run")
    def test_export_finds_default_ply(
        self,
        mock_run: MagicMock,
        splat: GaussianSplatService,
        tmp_path: Path,
    ):
        """If ns-export creates splat.ply, it should be found."""
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / "config.yml").touch()

        def side_effect(cmd, **kwargs):
            # ns-export writes splat.ply by default
            (model_dir / "splat.ply").write_bytes(b"ply data")
            return MagicMock(returncode=0, stderr="")

        mock_run.side_effect = side_effect

        output = model_dir / "point_cloud.ply"
        result = splat.export_ply(model_dir, output)

        # Should have moved splat.ply to point_cloud.ply
        assert result == output
        assert output.exists()


class TestPrepareDataDir:
    def test_creates_symlinks(self, splat: GaussianSplatService, tmp_path: Path):
        """prepare_data_dir should create images/ and sparse/0/ structure."""
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        (frames_dir / "frame_0001.jpg").touch()

        colmap_dir = tmp_path / "colmap" / "sparse" / "0"
        colmap_dir.mkdir(parents=True)
        (colmap_dir / "cameras.bin").touch()

        data_dir = tmp_path / "ns_data"
        result = splat.prepare_data_dir(frames_dir, colmap_dir, data_dir)

        assert (result / "images").exists()
        assert (result / "sparse" / "0").exists()


class TestFindConfig:
    def test_finds_config_at_root(self, splat: GaussianSplatService, tmp_path: Path):
        config = tmp_path / "config.yml"
        config.touch()
        assert splat._find_config(tmp_path) == config

    def test_finds_nested_config(self, splat: GaussianSplatService, tmp_path: Path):
        nested = tmp_path / "sub" / "dir"
        nested.mkdir(parents=True)
        config = nested / "config.yml"
        config.touch()
        assert splat._find_config(tmp_path) == config

    def test_missing_config_raises(self, splat: GaussianSplatService, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="No config.yml"):
            splat._find_config(tmp_path)
