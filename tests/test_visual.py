"""Tests for diffgrab.visual — visual diff with snapgrab integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from diffgrab.visual import VisualDiffResult, is_available

# ── VisualDiffResult ──────────────────────────────────────


class TestVisualDiffResult:
    def test_default_values(self) -> None:
        r = VisualDiffResult(url="https://example.com", changed=False)
        assert r.url == "https://example.com"
        assert r.changed is False
        assert r.before_path == ""
        assert r.after_path == ""
        assert r.diff_path == ""
        assert r.pixel_change_ratio == 0.0
        assert r.error == ""

    def test_with_values(self) -> None:
        r = VisualDiffResult(
            url="https://example.com",
            changed=True,
            before_path="/tmp/before.png",
            after_path="/tmp/after.png",
            pixel_change_ratio=0.15,
        )
        assert r.changed is True
        assert r.pixel_change_ratio == 0.15


# ── is_available ──────────────────────────────────────────


class TestIsAvailable:
    def test_returns_bool(self) -> None:
        result = is_available()
        assert isinstance(result, bool)


# ── capture_screenshot ────────────────────────────────────


class TestCaptureScreenshot:
    async def test_raises_when_snapgrab_missing(self) -> None:
        with patch("diffgrab.visual._SNAPGRAB_AVAILABLE", False):
            from diffgrab.visual import capture_screenshot

            with pytest.raises(ImportError, match="snapgrab"):
                await capture_screenshot("https://example.com")

    async def test_calls_snapgrab(self, tmp_path: Path) -> None:
        mock_result = MagicMock()
        mock_result.path = str(tmp_path / "screenshot.png")

        with (
            patch("diffgrab.visual._SNAPGRAB_AVAILABLE", True),
            patch("diffgrab.visual.sg_capture", new_callable=AsyncMock, return_value=mock_result, create=True),
        ):
            from diffgrab.visual import capture_screenshot

            path = await capture_screenshot("https://example.com", output_dir=str(tmp_path))
            assert path == mock_result.path


# ── compute_pixel_diff ────────────────────────────────────


class TestComputePixelDiff:
    def test_raises_when_pillow_missing(self) -> None:
        with patch("diffgrab.visual._PILLOW_AVAILABLE", False):
            from diffgrab.visual import compute_pixel_diff

            with pytest.raises(ImportError, match="Pillow"):
                compute_pixel_diff("/tmp/a.png", "/tmp/b.png")

    def test_identical_images(self, tmp_path: Path) -> None:
        """Test with identical mock images."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img = Image.new("RGB", (100, 100), (255, 255, 255))
        path_a = str(tmp_path / "a.png")
        path_b = str(tmp_path / "b.png")
        img.save(path_a)
        img.save(path_b)

        from diffgrab.visual import compute_pixel_diff

        changed, ratio, diff_path = compute_pixel_diff(path_a, path_b)
        assert changed is False
        assert ratio == 0.0

    def test_different_images(self, tmp_path: Path) -> None:
        """Test with different mock images."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img_a = Image.new("RGB", (100, 100), (255, 255, 255))
        img_b = Image.new("RGB", (100, 100), (0, 0, 0))
        path_a = str(tmp_path / "a.png")
        path_b = str(tmp_path / "b.png")
        img_a.save(path_a)
        img_b.save(path_b)

        from diffgrab.visual import compute_pixel_diff

        diff_output = str(tmp_path / "diff.png")
        changed, ratio, diff_path = compute_pixel_diff(path_a, path_b, diff_output)
        assert changed is True
        assert ratio == 1.0
        assert diff_path == diff_output

    def test_different_sizes(self, tmp_path: Path) -> None:
        """Test images with different dimensions are resized."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img_a = Image.new("RGB", (100, 100), (255, 0, 0))
        img_b = Image.new("RGB", (200, 150), (0, 255, 0))
        path_a = str(tmp_path / "a.png")
        path_b = str(tmp_path / "b.png")
        img_a.save(path_a)
        img_b.save(path_b)

        from diffgrab.visual import compute_pixel_diff

        changed, ratio, _ = compute_pixel_diff(path_a, path_b)
        assert changed is True
        assert ratio > 0


# ── visual_diff ───────────────────────────────────────────


class TestVisualDiff:
    async def test_no_snapgrab(self) -> None:
        with patch("diffgrab.visual._SNAPGRAB_AVAILABLE", False):
            from diffgrab.visual import visual_diff

            result = await visual_diff("https://example.com")
            assert result.changed is False
            assert "snapgrab" in result.error

    async def test_no_before_screenshot(self, tmp_path: Path) -> None:
        mock_result = MagicMock()
        mock_result.path = str(tmp_path / "after.png")

        with (
            patch("diffgrab.visual._SNAPGRAB_AVAILABLE", True),
            patch("diffgrab.visual.sg_capture", new_callable=AsyncMock, return_value=mock_result, create=True),
        ):
            from diffgrab.visual import visual_diff

            result = await visual_diff("https://example.com", output_dir=str(tmp_path))
            assert result.changed is False
            assert "No before screenshot" in result.error
            assert result.after_path == mock_result.path

    async def test_with_both_screenshots(self, tmp_path: Path) -> None:
        """Test visual diff when both screenshots are provided."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img_a = Image.new("RGB", (100, 100), (255, 255, 255))
        img_b = Image.new("RGB", (100, 100), (0, 0, 0))
        path_a = str(tmp_path / "before.png")
        path_b = str(tmp_path / "after.png")
        img_a.save(path_a)
        img_b.save(path_b)

        with (
            patch("diffgrab.visual._SNAPGRAB_AVAILABLE", True),
            patch("diffgrab.visual._PILLOW_AVAILABLE", True),
        ):
            from diffgrab.visual import visual_diff

            result = await visual_diff(
                "https://example.com",
                before_path=path_a,
                after_path=path_b,
                output_dir=str(tmp_path),
            )
            assert result.changed is True
            assert result.pixel_change_ratio > 0

    async def test_exception_handling(self) -> None:
        with (
            patch("diffgrab.visual._SNAPGRAB_AVAILABLE", True),
            patch("diffgrab.visual.sg_capture", new_callable=AsyncMock, side_effect=Exception("Browser crash"), create=True),
        ):
            from diffgrab.visual import visual_diff

            result = await visual_diff("https://example.com")
            assert result.changed is False
            assert "Browser crash" in result.error
