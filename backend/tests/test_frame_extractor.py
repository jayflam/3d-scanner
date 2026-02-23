"""Tests for the FFmpeg frame extraction service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from app.services.frame_extractor import FrameExtractorService


@pytest.fixture
def extractor():
    return FrameExtractorService()


@pytest.fixture
def sharp_frame(tmp_path: Path) -> Path:
    """Create a sharp test image with high-frequency edges."""
    arr = np.zeros((100, 100), dtype=np.uint8)
    # Checkerboard pattern = high frequency = not blurry
    arr[::2, ::2] = 200
    arr[1::2, 1::2] = 200
    img = Image.fromarray(arr, mode="L").convert("RGB")
    path = tmp_path / "sharp.jpg"
    img.save(path)
    return path


@pytest.fixture
def blurry_frame(tmp_path: Path) -> Path:
    """Create a blurry test image with uniform grey."""
    arr = np.full((100, 100), 128, dtype=np.uint8)
    img = Image.fromarray(arr, mode="L").convert("RGB")
    path = tmp_path / "blurry.jpg"
    img.save(path)
    return path


@pytest.fixture
def dark_frame(tmp_path: Path) -> Path:
    """Create an underexposed test image."""
    arr = np.full((100, 100), 10, dtype=np.uint8)
    img = Image.fromarray(arr, mode="L").convert("RGB")
    path = tmp_path / "dark.jpg"
    img.save(path)
    return path


@pytest.fixture
def bright_frame(tmp_path: Path) -> Path:
    """Create an overexposed test image."""
    arr = np.full((100, 100), 250, dtype=np.uint8)
    img = Image.fromarray(arr, mode="L").convert("RGB")
    path = tmp_path / "bright.jpg"
    img.save(path)
    return path


class TestFilterQuality:
    def test_sharp_frame_passes(self, extractor: FrameExtractorService, sharp_frame: Path):
        assert extractor.filter_quality(sharp_frame) is True

    def test_blurry_frame_rejected(self, extractor: FrameExtractorService, blurry_frame: Path):
        assert extractor.filter_quality(blurry_frame) is False

    def test_dark_frame_rejected(self, extractor: FrameExtractorService, dark_frame: Path):
        assert extractor.filter_quality(dark_frame) is False

    def test_bright_frame_rejected(self, extractor: FrameExtractorService, bright_frame: Path):
        assert extractor.filter_quality(bright_frame) is False

    def test_nonexistent_file_rejected(self, extractor: FrameExtractorService, tmp_path: Path):
        assert extractor.filter_quality(tmp_path / "nonexistent.jpg") is False


class TestExtractFrames:
    @patch("app.services.frame_extractor.subprocess.run")
    def test_extract_frames_calls_ffmpeg(
        self,
        mock_run: MagicMock,
        extractor: FrameExtractorService,
        tmp_path: Path,
        sharp_frame: Path,
    ):
        """Verify ffmpeg is called with correct arguments."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        # Create fake output frames that will be found after ffmpeg "runs"
        output_dir = tmp_path / "frames"
        output_dir.mkdir()
        # Copy sharp frame to simulate ffmpeg output
        for i in range(3):
            import shutil
            shutil.copy(sharp_frame, output_dir / f"frame_{i + 1:04d}.jpg")

        result = extractor.extract_frames(
            video_path=tmp_path / "test.mp4",
            output_dir=output_dir,
            fps=2,
        )

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "ffmpeg" in call_args[0]
        assert "-vf" in call_args
        assert "fps=2" in call_args[call_args.index("-vf") + 1]

        # Should return frames that pass quality
        assert len(result) == 3
        assert all(p.suffix == ".jpg" for p in result)

    @patch("app.services.frame_extractor.subprocess.run")
    def test_extract_frames_ffmpeg_failure(
        self,
        mock_run: MagicMock,
        extractor: FrameExtractorService,
        tmp_path: Path,
    ):
        """FFmpeg failure should raise RuntimeError."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="No such file or directory",
        )

        with pytest.raises(RuntimeError, match="FFmpeg frame extraction failed"):
            extractor.extract_frames(
                video_path=tmp_path / "missing.mp4",
                output_dir=tmp_path / "frames",
            )


class TestLaplacianVariance:
    def test_uniform_image_low_variance(self):
        """Uniform grey image should have zero Laplacian variance."""
        arr = np.full((50, 50), 128.0)
        variance = FrameExtractorService._laplacian_variance(arr)
        assert variance < 1.0

    def test_checkerboard_high_variance(self):
        """Checkerboard pattern should have high Laplacian variance."""
        arr = np.zeros((50, 50))
        arr[::2, ::2] = 255.0
        arr[1::2, 1::2] = 255.0
        variance = FrameExtractorService._laplacian_variance(arr)
        assert variance > 100.0
