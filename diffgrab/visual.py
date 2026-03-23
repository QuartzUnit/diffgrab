"""Visual diff — optional snapgrab integration for screenshot comparison."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from snapgrab import capture as sg_capture

    _SNAPGRAB_AVAILABLE = True
except ImportError:
    _SNAPGRAB_AVAILABLE = False

try:
    from PIL import Image, ImageChops

    _PILLOW_AVAILABLE = True
except ImportError:
    _PILLOW_AVAILABLE = False


@dataclass
class VisualDiffResult:
    """Result of visual comparison between two screenshots."""

    url: str
    changed: bool
    before_path: str = ""
    after_path: str = ""
    diff_path: str = ""
    pixel_change_ratio: float = 0.0
    error: str = ""


def is_available() -> bool:
    """Check if visual diff dependencies are installed."""
    return _SNAPGRAB_AVAILABLE


async def capture_screenshot(url: str, output_dir: str = "/tmp/diffgrab") -> str:
    """Capture a screenshot of a URL using snapgrab.

    Args:
        url: The URL to capture.
        output_dir: Directory to store the screenshot.

    Returns:
        Path to the screenshot file.

    Raises:
        ImportError: If snapgrab is not installed.
    """
    if not _SNAPGRAB_AVAILABLE:
        raise ImportError("snapgrab is not installed. Run: pip install 'diffgrab[visual]'")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    result = await sg_capture(url, output_dir=output_dir, full_page=True)
    return result.path


def compute_pixel_diff(before_path: str, after_path: str, output_path: str = "") -> tuple[bool, float, str]:
    """Compare two screenshots pixel-by-pixel.

    Args:
        before_path: Path to the before screenshot.
        after_path: Path to the after screenshot.
        output_path: Optional path to save the diff image.

    Returns:
        Tuple of (changed, pixel_change_ratio, diff_path).

    Raises:
        ImportError: If Pillow is not installed.
    """
    if not _PILLOW_AVAILABLE:
        raise ImportError("Pillow is not installed. Run: pip install Pillow")

    img_before = Image.open(before_path).convert("RGB")
    img_after = Image.open(after_path).convert("RGB")

    # Resize to same dimensions if needed
    if img_before.size != img_after.size:
        target_w = max(img_before.width, img_after.width)
        target_h = max(img_before.height, img_after.height)
        img_before = img_before.resize((target_w, target_h))
        img_after = img_after.resize((target_w, target_h))

    diff_img = ImageChops.difference(img_before, img_after)

    # Calculate change ratio
    total_pixels = diff_img.width * diff_img.height
    if total_pixels == 0:
        return False, 0.0, ""

    # Count non-zero pixels (changed pixels)
    changed_pixels = 0
    for pixel in diff_img.getdata():
        if pixel != (0, 0, 0):
            changed_pixels += 1

    ratio = changed_pixels / total_pixels
    changed = ratio > 0.001  # threshold: 0.1% pixels changed

    diff_path = ""
    if output_path and changed:
        diff_img.save(output_path)
        diff_path = output_path

    return changed, ratio, diff_path


async def visual_diff(
    url: str,
    before_path: str | None = None,
    after_path: str | None = None,
    output_dir: str = "/tmp/diffgrab",
) -> VisualDiffResult:
    """Perform visual diff between two screenshots of a URL.

    If before_path or after_path are not provided, captures new screenshot(s).

    Args:
        url: The URL being compared.
        before_path: Path to the before screenshot (or None to skip).
        after_path: Path to the after screenshot (or None to capture new).
        output_dir: Directory for screenshots and diff images.

    Returns:
        VisualDiffResult with comparison details.
    """
    if not _SNAPGRAB_AVAILABLE:
        return VisualDiffResult(
            url=url,
            changed=False,
            error="snapgrab is not installed. Run: pip install 'diffgrab[visual]'",
        )

    try:
        if after_path is None:
            after_path = await capture_screenshot(url, output_dir=output_dir)

        if before_path is None:
            return VisualDiffResult(
                url=url,
                changed=False,
                after_path=after_path,
                error="No before screenshot available for comparison.",
            )

        if not _PILLOW_AVAILABLE:
            return VisualDiffResult(
                url=url,
                changed=False,
                before_path=before_path,
                after_path=after_path,
                error="Pillow is not installed for pixel comparison.",
            )

        diff_output = str(Path(output_dir) / "diff.png")
        changed, ratio, diff_path = compute_pixel_diff(before_path, after_path, diff_output)

        return VisualDiffResult(
            url=url,
            changed=changed,
            before_path=before_path,
            after_path=after_path,
            diff_path=diff_path,
            pixel_change_ratio=ratio,
        )

    except Exception as exc:
        logger.error("Visual diff failed for %s: %s", url, exc)
        return VisualDiffResult(
            url=url,
            changed=False,
            error=str(exc),
        )
