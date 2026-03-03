"""COLMAP Structure-from-Motion wrapper.

Runs COLMAP's feature extraction, matching, and sparse reconstruction
as subprocess calls to produce camera poses for Gaussian Splatting.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Default COLMAP timeouts (seconds)
FEATURE_EXTRACT_TIMEOUT = 600  # 10 min
MATCHER_TIMEOUT = 600  # 10 min
MAPPER_TIMEOUT = 900  # 15 min


class COLMAPService:
    """Wraps COLMAP CLI to run Structure-from-Motion on extracted frames."""

    def __init__(
        self,
        colmap_path: str = "colmap",
        use_gpu: bool = True,
    ) -> None:
        self._colmap = colmap_path
        self._use_gpu = use_gpu

    def run_sfm(
        self,
        frames_dir: Path,
        output_dir: Path,
    ) -> Path:
        """Run the full COLMAP SfM pipeline.

        Steps: feature_extractor -> exhaustive_matcher -> mapper

        Args:
            frames_dir: Directory containing input frame images.
            output_dir: Directory for COLMAP output (database + sparse model).

        Returns:
            Path to the sparse reconstruction directory.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        db_path = output_dir / "database.db"
        sparse_dir = output_dir / "sparse"
        sparse_dir.mkdir(parents=True, exist_ok=True)

        self._run_feature_extractor(frames_dir, db_path)
        self._run_exhaustive_matcher(db_path)
        self._run_mapper(frames_dir, db_path, sparse_dir)

        # COLMAP mapper creates numbered subdirectories (0, 1, ...).
        # Return the first (usually best) reconstruction.
        model_dirs = sorted(sparse_dir.iterdir())
        if not model_dirs:
            raise RuntimeError(
                "COLMAP mapper produced no reconstructions. "
                "Check that input frames have sufficient overlap."
            )

        model_dir = model_dirs[0]
        logger.info(
            "COLMAP SfM complete: %d model(s), using %s",
            len(model_dirs),
            model_dir.name,
        )
        return model_dir

    def _run_feature_extractor(self, frames_dir: Path, db_path: Path) -> None:
        """Extract SIFT features from all frames."""
        gpu_flag = "1" if self._use_gpu else "0"
        cmd = [
            self._colmap, "feature_extractor",
            "--database_path", str(db_path),
            "--image_path", str(frames_dir),
            "--ImageReader.single_camera", "1",
            "--SiftExtraction.use_gpu", gpu_flag,
        ]
        logger.info("COLMAP feature_extractor: %s", " ".join(cmd))
        self._execute(cmd, timeout=FEATURE_EXTRACT_TIMEOUT, step="feature_extractor")

    def _run_exhaustive_matcher(self, db_path: Path) -> None:
        """Run exhaustive feature matching."""
        gpu_flag = "1" if self._use_gpu else "0"
        cmd = [
            self._colmap, "exhaustive_matcher",
            "--database_path", str(db_path),
            "--SiftMatching.use_gpu", gpu_flag,
        ]
        logger.info("COLMAP exhaustive_matcher: %s", " ".join(cmd))
        self._execute(cmd, timeout=MATCHER_TIMEOUT, step="exhaustive_matcher")

    def _run_mapper(
        self,
        frames_dir: Path,
        db_path: Path,
        sparse_dir: Path,
    ) -> None:
        """Run incremental mapper (sparse reconstruction)."""
        cmd = [
            self._colmap, "mapper",
            "--database_path", str(db_path),
            "--image_path", str(frames_dir),
            "--output_path", str(sparse_dir),
        ]
        logger.info("COLMAP mapper: %s", " ".join(cmd))
        self._execute(cmd, timeout=MAPPER_TIMEOUT, step="mapper")

    def _execute(self, cmd: list[str], timeout: int, step: str) -> None:
        """Run a COLMAP subprocess with error handling."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"COLMAP {step} timed out after {timeout}s"
            )

        if result.returncode != 0:
            logger.error("COLMAP %s stderr: %s", step, result.stderr[:1000])
            raise RuntimeError(
                f"COLMAP {step} failed (exit {result.returncode}): "
                f"{result.stderr[:500]}"
            )

        logger.info("COLMAP %s completed successfully", step)

    def convert_model_to_text(
        self,
        model_dir: Path,
        output_dir: Path,
    ) -> Path:
        """Convert binary COLMAP model to text format (useful for debugging)."""
        output_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            self._colmap, "model_converter",
            "--input_path", str(model_dir),
            "--output_path", str(output_dir),
            "--output_type", "TXT",
        ]
        self._execute(cmd, timeout=60, step="model_converter")
        return output_dir
