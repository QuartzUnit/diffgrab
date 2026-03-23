"""DiffTracker — main orchestrator for web page change tracking."""

from __future__ import annotations

import hashlib
import logging

from markgrab import extract as mg_extract

from diffgrab.db import DEFAULT_DB_PATH, Database
from diffgrab.differ import DiffResult, compute_diff

logger = logging.getLogger(__name__)


def _content_hash(text: str) -> str:
    """Compute SHA-256 hash of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class DiffTracker:
    """Main orchestrator for tracking web page changes.

    Usage::

        tracker = DiffTracker()
        await tracker.track("https://example.com")
        changes = await tracker.check()
        await tracker.close()
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self._db = Database(db_path)

    async def track(self, url: str, interval_hours: int = 24) -> str:
        """Register URL for tracking and take initial snapshot.

        Args:
            url: The URL to track.
            interval_hours: How often to check for changes (default: 24h).

        Returns:
            Status message.
        """
        existing = self._db.get_tracked_url(url)
        if existing:
            return f"Already tracking: {url}"

        self._db.add_tracked_url(url, interval_hours)

        # Take initial snapshot
        try:
            result = await mg_extract(url)
            markdown = result.markdown
            title = result.title
            word_count = result.word_count
        except Exception as exc:
            logger.error("Failed to fetch initial snapshot for %s: %s", url, exc)
            return f"Tracking registered but initial snapshot failed: {exc}"

        content = _content_hash(markdown)
        self._db.add_snapshot(url, content, markdown, title, word_count)
        self._db.update_last_checked(url)

        return f"Now tracking: {url} (interval: {interval_hours}h, initial snapshot: {word_count} words)"

    async def check(self, url: str | None = None) -> list[DiffResult]:
        """Check tracked URLs for changes.

        If url is None, checks all tracked URLs.
        Fetches new content, compares hash with latest snapshot.
        If different, stores new snapshot and returns DiffResult with changed=True.

        Args:
            url: Specific URL to check, or None for all tracked URLs.

        Returns:
            List of DiffResult objects (one per checked URL).
        """
        if url is not None:
            tracked = self._db.get_tracked_url(url)
            if tracked is None:
                return [DiffResult(url=url, changed=False, summary=f"URL not tracked: {url}")]
            urls_to_check = [tracked]
        else:
            urls_to_check = self._db.get_all_tracked_urls()

        results: list[DiffResult] = []

        for tracked_info in urls_to_check:
            target_url = tracked_info["url"]
            result = await self._check_single(target_url)
            results.append(result)

        return results

    async def _check_single(self, url: str) -> DiffResult:
        """Check a single URL for changes."""
        try:
            result = await mg_extract(url)
            new_markdown = result.markdown
            new_title = result.title
            new_word_count = result.word_count
        except Exception as exc:
            logger.error("Failed to fetch %s: %s", url, exc)
            return DiffResult(url=url, changed=False, summary=f"Fetch failed: {exc}")

        new_hash = _content_hash(new_markdown)
        latest = self._db.get_latest_snapshot(url)

        if latest is None:
            # No previous snapshot — store this one
            self._db.add_snapshot(url, new_hash, new_markdown, new_title, new_word_count)
            self._db.update_last_checked(url)
            return DiffResult(url=url, changed=False, summary=f"First snapshot captured for {url}.")

        if new_hash == latest["content_hash"]:
            self._db.update_last_checked(url)
            return DiffResult(
                url=url,
                changed=False,
                summary=f"No changes detected for {url}.",
                after_snapshot_id=latest["id"],
                after_timestamp=latest["captured_at"],
            )

        # Content changed — store new snapshot and compute diff
        new_id = self._db.add_snapshot(url, new_hash, new_markdown, new_title, new_word_count)
        self._db.update_last_checked(url)

        new_snapshot = self._db.get_snapshot_by_id(new_id)
        after_timestamp = new_snapshot["captured_at"] if new_snapshot else ""

        diff_result = compute_diff(
            before_text=latest["markdown"],
            after_text=new_markdown,
            url=url,
            before_snapshot_id=latest["id"],
            after_snapshot_id=new_id,
            before_timestamp=latest["captured_at"],
            after_timestamp=after_timestamp,
        )

        return diff_result

    async def diff(
        self,
        url: str,
        before_id: int | None = None,
        after_id: int | None = None,
    ) -> DiffResult:
        """Get structured diff between two snapshots.

        If before_id/after_id are not provided, uses the two most recent snapshots.

        Args:
            url: The URL to diff.
            before_id: Database ID of the older snapshot (optional).
            after_id: Database ID of the newer snapshot (optional).

        Returns:
            DiffResult with structured diff details.
        """
        if before_id is not None and after_id is not None:
            before = self._db.get_snapshot_by_id(before_id)
            after = self._db.get_snapshot_by_id(after_id)
        else:
            before, after = self._db.get_snapshot_pair(url)

        if before is None and after is None:
            return DiffResult(url=url, changed=False, summary=f"No snapshots found for {url}.")

        if before is None:
            return DiffResult(
                url=url,
                changed=False,
                summary=f"Only one snapshot exists for {url}. Need at least two for diff.",
                after_snapshot_id=after["id"] if after else None,
                after_timestamp=after["captured_at"] if after else "",
            )

        if after is None:
            return DiffResult(
                url=url,
                changed=False,
                summary=f"After snapshot not found for {url}.",
                before_snapshot_id=before["id"],
                before_timestamp=before["captured_at"],
            )

        return compute_diff(
            before_text=before["markdown"],
            after_text=after["markdown"],
            url=url,
            before_snapshot_id=before["id"],
            after_snapshot_id=after["id"],
            before_timestamp=before["captured_at"],
            after_timestamp=after["captured_at"],
        )

    async def history(self, url: str, count: int = 10) -> list[dict]:
        """Get snapshot history for a URL.

        Args:
            url: The URL to get history for.
            count: Maximum number of snapshots to return (default: 10).

        Returns:
            List of snapshot dicts (without full markdown content), newest first.
        """
        snapshots = self._db.get_snapshots(url, count)
        # Return metadata only, exclude full markdown for brevity
        return [
            {
                "id": s["id"],
                "url": s["url"],
                "content_hash": s["content_hash"],
                "title": s["title"],
                "word_count": s["word_count"],
                "captured_at": s["captured_at"],
            }
            for s in snapshots
        ]

    async def untrack(self, url: str) -> str:
        """Remove URL from tracking and delete all its snapshots.

        Args:
            url: The URL to untrack.

        Returns:
            Status message.
        """
        removed = self._db.remove_tracked_url(url)
        if removed:
            return f"Untracked: {url}"
        return f"URL was not being tracked: {url}"

    async def close(self) -> None:
        """Close the database connection."""
        self._db.close()
