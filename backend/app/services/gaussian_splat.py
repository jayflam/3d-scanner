"""Gaussian Splatting training and PLY export service.

Wraps a Gaussian Splatting training tool (nerfstudio ns-train or standalone
gsplat) as a subprocess to produce .ply splat files from frames + COLMAP poses.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

TRAIN_TIMEOUT = 1800  # 30 min max for training
EXPORT_TIMEOUT = 120  # 2 min for export


class GaussianSplatService:
    """Trains 3D Gaussian Splatting models and exports .ply files."""

    def __init__(
        self,
        method: str = "splatfacto",
        ns_train_path: str = "ns-train",
        ns_export_path: str = "ns-export",
    ) -> None:
        """
        Args:
            method: Nerfstudio method name (e.g. "splatfacto", "gaussian-splatting").
            ns_train_path: Path to the ns-train command.
            ns_export_path: Path to the ns-export command.
        """
        self._method = method
        self._ns_train = ns_train_path
        self._ns_export = ns_export_path

    def train(
        self,
        data_dir: Path,
        output_dir: Path,
        iterations: int = 7000,
    ) -> Path:
        """Train a Gaussian Splatting model from COLMAP-formatted data.

        Expects data_dir to contain:
          - images/ (frame images)
          - sparse/0/ (COLMAP sparse reconstruction: cameras.bin, images.bin, points3D.bin)

        Args:
            data_dir: Directory with COLMAP-formatted input data.
            output_dir: Directory to write trained model output.
            iterations: Number of training iterations (7k fast, 15k quality).

        Returns:
            Path to the trained model output directory.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            self._ns_train,
            self._method,
            "--data", str(data_dir),
            "--output-dir", str(output_dir),
            "--max-num-iterations", str(iterations),
            "--viewer.quit-on-train-completion", "True",
            "colmap",  # data parser type
        ]

        logger.info(
            "Starting Gaussian Splatting training: method=%s, iterations=%d",
            self._method,
            iterations,
        )
        logger.info("Command: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=TRAIN_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Gaussian Splatting training timed out after {TRAIN_TIMEOUT}s"
            )

        if result.returncode != 0:
            logger.error("Training stderr: %s", result.stderr[:1000])
            raise RuntimeError(
                f"Gaussian Splatting training failed (exit {result.returncode}): "
                f"{result.stderr[:500]}"
            )

        # Find the latest config.yml to locate model checkpoint
        model_dir = self._find_model_dir(output_dir)
        logger.info("Training complete: %s", model_dir)
        return model_dir

    def export_ply(
        self,
        model_dir: Path,
        output_path: Path | None = None,
    ) -> Path:
        """Export a trained Gaussian Splatting model to .ply format.

        Args:
            model_dir: Path to the trained model directory (containing config.yml).
            output_path: Explicit output .ply path. If None, writes to model_dir/point_cloud.ply.

        Returns:
            Path to the exported .ply file.
        """
        if output_path is None:
            output_path = model_dir / "point_cloud.ply"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        config_path = self._find_config(model_dir)

        cmd = [
            self._ns_export,
            "gaussian-splat",
            "--load-config", str(config_path),
            "--output-dir", str(output_path.parent),
        ]

        logger.info("Exporting PLY: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=EXPORT_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"PLY export timed out after {EXPORT_TIMEOUT}s"
            )

        if result.returncode != 0:
            logger.error("Export stderr: %s", result.stderr[:1000])
            raise RuntimeError(
                f"PLY export failed (exit {result.returncode}): "
                f"{result.stderr[:500]}"
            )

        # ns-export writes splat.ply by default; rename if needed
        default_ply = output_path.parent / "splat.ply"
        if default_ply.exists() and default_ply != output_path:
            shutil.move(str(default_ply), str(output_path))

        if not output_path.exists():
            # Check for any .ply file in the output dir
            ply_files = list(output_path.parent.glob("*.ply"))
            if ply_files:
                output_path = ply_files[0]
            else:
                raise RuntimeError(
                    f"PLY export completed but no .ply file found in {output_path.parent}"
                )

        logger.info("PLY exported: %s (%.1f MB)", output_path, output_path.stat().st_size / 1e6)
        return output_path

    def prepare_data_dir(
        self,
        frames_dir: Path,
        colmap_model_dir: Path,
        output_data_dir: Path,
    ) -> Path:
        """Prepare a COLMAP-formatted data directory for nerfstudio.

        Nerfstudio expects:
          data_dir/
            images/       <- symlink or copy of frames
            sparse/0/     <- COLMAP sparse reconstruction

        Args:
            frames_dir: Directory containing extracted frame images.
            colmap_model_dir: Path to COLMAP sparse/0/ model directory.
            output_data_dir: Where to create the formatted directory.

        Returns:
            Path to the prepared data directory.
        """
        output_data_dir.mkdir(parents=True, exist_ok=True)

        # Link or copy images
        images_dir = output_data_dir / "images"
        if not images_dir.exists():
            images_dir.symlink_to(frames_dir.resolve())

        # Link or copy COLMAP sparse reconstruction
        sparse_dir = output_data_dir / "sparse" / "0"
        sparse_dir.parent.mkdir(parents=True, exist_ok=True)
        if not sparse_dir.exists():
            sparse_dir.symlink_to(colmap_model_dir.resolve())

        return output_data_dir

    def _find_model_dir(self, output_dir: Path) -> Path:
        """Find the latest model directory within nerfstudio output."""
        # Nerfstudio creates: output_dir/{method}/{timestamp}/
        for method_dir in sorted(output_dir.iterdir(), reverse=True):
            if method_dir.is_dir():
                for ts_dir in sorted(method_dir.iterdir(), reverse=True):
                    if ts_dir.is_dir():
                        return ts_dir
        return output_dir

    def _find_config(self, model_dir: Path) -> Path:
        """Find config.yml in or under model_dir."""
        config = model_dir / "config.yml"
        if config.exists():
            return config
        # Search recursively
        configs = list(model_dir.rglob("config.yml"))
        if configs:
            return configs[0]
        raise FileNotFoundError(
            f"No config.yml found in {model_dir}. "
            "Ensure training completed successfully."
        )
