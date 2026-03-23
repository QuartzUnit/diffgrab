"""diffgrab — Web page change tracking with structured diffs."""

from __future__ import annotations

from diffgrab.differ import DiffResult
from diffgrab.tracker import DiffTracker

__all__ = ["DiffTracker", "DiffResult", "track", "check", "diff", "history", "untrack"]
__version__ = "0.1.0"


async def track(url: str, interval_hours: int = 24, *, db_path: str = "") -> str:
    """Register a URL for change tracking.

    Args:
        url: The URL to track.
        interval_hours: Check interval in hours (default: 24).
        db_path: Custom database path (optional).

    Returns:
        Status message.
    """
    kwargs = {"db_path": db_path} if db_path else {}
    tracker = DiffTracker(**kwargs)
    try:
        return await tracker.track(url, interval_hours)
    finally:
        await tracker.close()


async def check(url: str | None = None, *, db_path: str = "") -> list[DiffResult]:
    """Check tracked URLs for changes.

    Args:
        url: Specific URL to check, or None for all.
        db_path: Custom database path (optional).

    Returns:
        List of DiffResult objects.
    """
    kwargs = {"db_path": db_path} if db_path else {}
    tracker = DiffTracker(**kwargs)
    try:
        return await tracker.check(url)
    finally:
        await tracker.close()


async def diff(
    url: str,
    before_id: int | None = None,
    after_id: int | None = None,
    *,
    db_path: str = "",
) -> DiffResult:
    """Get structured diff between two snapshots of a URL.

    Args:
        url: The URL to diff.
        before_id: Database ID of the older snapshot.
        after_id: Database ID of the newer snapshot.
        db_path: Custom database path (optional).

    Returns:
        DiffResult with structured diff.
    """
    kwargs = {"db_path": db_path} if db_path else {}
    tracker = DiffTracker(**kwargs)
    try:
        return await tracker.diff(url, before_id, after_id)
    finally:
        await tracker.close()


async def history(url: str, count: int = 10, *, db_path: str = "") -> list[dict]:
    """Get snapshot history for a URL.

    Args:
        url: The URL to get history for.
        count: Maximum number of snapshots (default: 10).
        db_path: Custom database path (optional).

    Returns:
        List of snapshot metadata dicts.
    """
    kwargs = {"db_path": db_path} if db_path else {}
    tracker = DiffTracker(**kwargs)
    try:
        return await tracker.history(url, count)
    finally:
        await tracker.close()


async def untrack(url: str, *, db_path: str = "") -> str:
    """Remove a URL from tracking.

    Args:
        url: The URL to untrack.
        db_path: Custom database path (optional).

    Returns:
        Status message.
    """
    kwargs = {"db_path": db_path} if db_path else {}
    tracker = DiffTracker(**kwargs)
    try:
        return await tracker.untrack(url)
    finally:
        await tracker.close()
