"""FFmpeg-based frame extraction with quality filtering.

Extracts frames from uploaded vehicle walkround videos at a configurable FPS,
then filters out blurry or poorly-exposed frames using Laplacian variance
and brightness checks.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Quality thresholds
BLUR_THRESHOLD = 100.0  # Laplacian variance below this = blurry
BRIGHTNESS_LOW = 40  # Mean pixel value below this = underexposed
BRIGHTNESS_HIGH = 240  # Mean pixel value above this = overexposed


class FrameExtractorService:
    """Extracts and quality-filters video frames using FFmpeg."""

    def __init__(
        self,
        ffmpeg_path: str = "ffmpeg",
        blur_threshold: float = BLUR_THRESHOLD,
        brightness_low: int = BRIGHTNESS_LOW,
        brightness_high: int = BRIGHTNESS_HIGH,
    ) -> None:
        self._ffmpeg = ffmpeg_path
        self._blur_threshold = blur_threshold
        self._brightness_low = brightness_low
        self._brightness_high = brightness_high

    def extract_frames(
        self,
        video_path: Path,
        output_dir: Path,
        fps: int = 2,
    ) -> list[Path]:
        """Extract frames from a video at the given FPS.

        Args:
            video_path: Path to the source video file.
            output_dir: Directory to write extracted frame JPEGs.
            fps: Frames per second to extract (default 2).

        Returns:
            Sorted list of paths to frames that pass quality filtering.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        pattern = str(output_dir / "frame_%04d.jpg")

        cmd = [
            self._ffmpeg,
            "-i", str(video_path),
            "-vf", f"fps={fps}",
            "-q:v", "2",
            pattern,
            "-y",  # overwrite existing
        ]

        logger.info("Extracting frames: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min timeout
        )

        if result.returncode != 0:
            logger.error("FFmpeg failed: %s", result.stderr)
            raise RuntimeError(f"FFmpeg frame extraction failed: {result.stderr[:500]}")

        # Collect all extracted frames, sorted by name
        all_frames = sorted(output_dir.glob("frame_*.jpg"))
        logger.info("Extracted %d raw frames from %s", len(all_frames), video_path.name)

        # Quality filter
        passing = [f for f in all_frames if self.filter_quality(f)]
        rejected = len(all_frames) - len(passing)
        if rejected:
            logger.info(
                "Quality filter: kept %d, rejected %d frames",
                len(passing),
                rejected,
            )

        return passing

    def filter_quality(self, frame_path: Path) -> bool:
        """Check whether a frame passes blur and brightness quality checks.

        Args:
            frame_path: Path to a JPEG frame image.

        Returns:
            True if the frame is acceptable quality.
        """
        try:
            img = Image.open(frame_path)
            arr = np.array(img.convert("L"), dtype=np.float64)
        except Exception:
            logger.warning("Could not open frame %s, rejecting", frame_path.name)
            return False

        # Blur detection via Laplacian variance
        # Laplacian kernel convolution approximation using numpy
        laplacian = self._laplacian_variance(arr)
        if laplacian < self._blur_threshold:
            logger.debug("Frame %s rejected: blurry (laplacian=%.1f)", frame_path.name, laplacian)
            return False

        # Brightness check
        mean_brightness = arr.mean()
        if mean_brightness < self._brightness_low:
            logger.debug(
                "Frame %s rejected: underexposed (brightness=%.1f)",
                frame_path.name,
                mean_brightness,
            )
            return False
        if mean_brightness > self._brightness_high:
            logger.debug(
                "Frame %s rejected: overexposed (brightness=%.1f)",
                frame_path.name,
                mean_brightness,
            )
            return False

        return True

    @staticmethod
    def _laplacian_variance(gray: np.ndarray) -> float:
        """Compute variance of the Laplacian (focus measure).

        Higher values indicate sharper images.
        """
        # 3x3 Laplacian kernel applied via convolution
        # kernel = [[0,1,0],[1,-4,1],[0,1,0]]
        # We use a simple finite-difference approximation
        padded = np.pad(gray, 1, mode="edge")
        laplacian = (
            padded[:-2, 1:-1]
            + padded[2:, 1:-1]
            + padded[1:-1, :-2]
            + padded[1:-1, 2:]
            - 4 * padded[1:-1, 1:-1]
        )
        return float(laplacian.var())

    def get_video_info(self, video_path: Path) -> dict:
        """Get video metadata (duration, resolution, fps) using ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                import json
                return json.loads(result.stdout)
        except Exception:
            logger.warning("ffprobe failed for %s", video_path.name)
        return {}
