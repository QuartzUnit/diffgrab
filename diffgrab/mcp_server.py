"""MCP server for diffgrab — 5 tools for web page change tracking."""

from __future__ import annotations

import json
import sys

try:
    from fastmcp import FastMCP
except ImportError:
    print("MCP dependencies not installed. Run: pip install 'diffgrab[mcp]'", file=sys.stderr)
    sys.exit(1)

from diffgrab.differ import DiffResult
from diffgrab.tracker import DiffTracker

mcp = FastMCP("diffgrab", instructions="Web page change tracking with structured diffs.")

# Shared tracker instance (lazily initialized)
_tracker: DiffTracker | None = None


def _get_tracker() -> DiffTracker:
    global _tracker
    if _tracker is None:
        _tracker = DiffTracker()
    return _tracker


def _diff_result_to_json(result: DiffResult) -> str:
    """Serialize a DiffResult to JSON string."""
    return json.dumps(
        {
            "url": result.url,
            "changed": result.changed,
            "added_lines": result.added_lines,
            "removed_lines": result.removed_lines,
            "changed_sections": result.changed_sections,
            "unified_diff": result.unified_diff[:2000] if result.unified_diff else "",
            "summary": result.summary,
            "before_snapshot_id": result.before_snapshot_id,
            "after_snapshot_id": result.after_snapshot_id,
            "before_timestamp": result.before_timestamp,
            "after_timestamp": result.after_timestamp,
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
async def track_url(url: str, interval_hours: int = 24) -> str:
    """Register a URL for change tracking. Takes an initial snapshot.

    Args:
        url: The URL to track for changes.
        interval_hours: How often to check for changes (default: 24 hours).

    Returns:
        Status message confirming tracking registration.
    """
    tracker = _get_tracker()
    return await tracker.track(url, interval_hours)


@mcp.tool()
async def check_changes(url: str | None = None) -> str:
    """Check tracked URLs for changes. Compares current content with last snapshot.

    Args:
        url: Specific URL to check, or None to check all tracked URLs.

    Returns:
        JSON array of change results for each checked URL.
    """
    tracker = _get_tracker()
    results = await tracker.check(url)
    return json.dumps(
        [json.loads(_diff_result_to_json(r)) for r in results],
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
async def get_diff(url: str, before_id: int | None = None, after_id: int | None = None) -> str:
    """Get structured diff between two snapshots of a URL.

    Args:
        url: The URL to get diff for.
        before_id: Snapshot ID for the older version (optional, uses latest pair if omitted).
        after_id: Snapshot ID for the newer version (optional, uses latest pair if omitted).

    Returns:
        JSON object with diff details including unified diff and changed sections.
    """
    tracker = _get_tracker()
    result = await tracker.diff(url, before_id, after_id)
    return _diff_result_to_json(result)


@mcp.tool()
async def get_history(url: str, count: int = 10) -> str:
    """Get snapshot history for a tracked URL.

    Args:
        url: The URL to get history for.
        count: Maximum number of snapshots to return (default: 10).

    Returns:
        JSON array of snapshot metadata (id, title, word_count, hash, timestamp).
    """
    tracker = _get_tracker()
    snapshots = await tracker.history(url, count)
    return json.dumps(snapshots, ensure_ascii=False, indent=2)


@mcp.tool()
async def untrack_url(url: str) -> str:
    """Remove a URL from change tracking. Deletes all stored snapshots.

    Args:
        url: The URL to stop tracking.

    Returns:
        Status message confirming removal.
    """
    tracker = _get_tracker()
    return await tracker.untrack(url)


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
