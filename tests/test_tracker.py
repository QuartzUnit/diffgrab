"""Tests for diffgrab.tracker — DiffTracker orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from diffgrab.tracker import DiffTracker, _content_hash

# ── Mock markgrab result ──────────────────────────────────


@dataclass
class MockExtractResult:
    """Mock markgrab.ExtractResult for testing."""

    title: str = "Example Page"
    text: str = "Hello world"
    markdown: str = "# Example Page\n\nHello world."
    word_count: int = 2
    language: str = "en"
    content_type: str = "html"
    source_url: str = "https://example.com"


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture()
def tracker(tmp_path: Path) -> DiffTracker:
    """Create a DiffTracker with a temp database."""
    db_path = str(tmp_path / "test.db")
    return DiffTracker(db_path)


@pytest.fixture()
def mock_extract():
    """Patch markgrab.extract to return mock results."""
    with patch("diffgrab.tracker.mg_extract", new_callable=AsyncMock) as mock:
        mock.return_value = MockExtractResult()
        yield mock


# ── _content_hash ─────────────────────────────────────────


class TestContentHash:
    def test_deterministic(self) -> None:
        h1 = _content_hash("hello")
        h2 = _content_hash("hello")
        assert h1 == h2

    def test_different_input(self) -> None:
        h1 = _content_hash("hello")
        h2 = _content_hash("world")
        assert h1 != h2

    def test_sha256_length(self) -> None:
        h = _content_hash("test")
        assert len(h) == 64  # SHA-256 hex digest


# ── track ─────────────────────────────────────────────────


class TestTrack:
    async def test_track_new_url(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        result = await tracker.track("https://example.com")
        assert "Now tracking" in result
        assert "example.com" in result
        mock_extract.assert_awaited_once()

    async def test_track_duplicate(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://example.com")
        result = await tracker.track("https://example.com")
        assert "Already tracking" in result

    async def test_track_with_interval(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        result = await tracker.track("https://example.com", interval_hours=6)
        assert "6h" in result

    async def test_track_fetch_failure(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        mock_extract.side_effect = Exception("Connection error")
        result = await tracker.track("https://example.com")
        assert "initial snapshot failed" in result

    async def test_track_creates_snapshot(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://example.com")
        history = await tracker.history("https://example.com")
        assert len(history) == 1
        assert history[0]["title"] == "Example Page"


# ── check ─────────────────────────────────────────────────


class TestCheck:
    async def test_check_no_change(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://example.com")
        results = await tracker.check("https://example.com")
        assert len(results) == 1
        assert results[0].changed is False

    async def test_check_with_change(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://example.com")

        # Change the mock return to simulate content change
        mock_extract.return_value = MockExtractResult(
            markdown="# Example Page\n\nUpdated content.",
            word_count=3,
        )

        results = await tracker.check("https://example.com")
        assert len(results) == 1
        assert results[0].changed is True
        assert results[0].added_lines > 0

    async def test_check_untracked_url(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        results = await tracker.check("https://unknown.com")
        assert len(results) == 1
        assert results[0].changed is False
        assert "not tracked" in results[0].summary

    async def test_check_all(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://a.com")
        await tracker.track("https://b.com")
        results = await tracker.check()
        assert len(results) == 2

    async def test_check_stores_new_snapshot(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://example.com")

        mock_extract.return_value = MockExtractResult(
            markdown="# Changed\n\nNew content.",
            word_count=2,
        )
        await tracker.check("https://example.com")

        history = await tracker.history("https://example.com")
        assert len(history) == 2

    async def test_check_fetch_failure(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://example.com")
        mock_extract.side_effect = Exception("Timeout")
        results = await tracker.check("https://example.com")
        assert len(results) == 1
        assert results[0].changed is False
        assert "Fetch failed" in results[0].summary


# ── diff ──────────────────────────────────────────────────


class TestDiff:
    async def test_diff_with_two_snapshots(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://example.com")
        mock_extract.return_value = MockExtractResult(
            markdown="# Example Page\n\nUpdated content.",
            word_count=3,
        )
        await tracker.check("https://example.com")

        result = await tracker.diff("https://example.com")
        assert result.changed is True
        assert result.unified_diff != ""

    async def test_diff_no_snapshots(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        result = await tracker.diff("https://example.com")
        assert result.changed is False
        assert "No snapshots" in result.summary

    async def test_diff_single_snapshot(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://example.com")
        result = await tracker.diff("https://example.com")
        assert result.changed is False
        assert "Only one snapshot" in result.summary

    async def test_diff_with_explicit_ids(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://example.com")
        mock_extract.return_value = MockExtractResult(
            markdown="# Changed\n\nNew.",
            word_count=1,
        )
        await tracker.check("https://example.com")

        history = await tracker.history("https://example.com")
        before_id = history[-1]["id"]  # Oldest
        after_id = history[0]["id"]  # Newest

        result = await tracker.diff("https://example.com", before_id=before_id, after_id=after_id)
        assert result.changed is True
        assert result.before_snapshot_id == before_id
        assert result.after_snapshot_id == after_id


# ── history ───────────────────────────────────────────────


class TestHistory:
    async def test_history_empty(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        history = await tracker.history("https://example.com")
        assert history == []

    async def test_history_returns_metadata(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://example.com")
        history = await tracker.history("https://example.com")
        assert len(history) == 1
        snap = history[0]
        assert "id" in snap
        assert "url" in snap
        assert "content_hash" in snap
        assert "title" in snap
        assert "word_count" in snap
        assert "captured_at" in snap
        # Should NOT contain full markdown
        assert "markdown" not in snap

    async def test_history_count(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://example.com")
        for i in range(5):
            mock_extract.return_value = MockExtractResult(markdown=f"Version {i}", word_count=1)
            await tracker.check("https://example.com")

        history = await tracker.history("https://example.com", count=3)
        assert len(history) == 3

    async def test_history_newest_first(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://example.com")
        mock_extract.return_value = MockExtractResult(markdown="# V2\n\nNew.", word_count=1)
        await tracker.check("https://example.com")

        history = await tracker.history("https://example.com")
        assert len(history) == 2
        # First entry should be newest
        assert history[0]["captured_at"] >= history[1]["captured_at"]


# ── untrack ───────────────────────────────────────────────


class TestUntrack:
    async def test_untrack_existing(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://example.com")
        result = await tracker.untrack("https://example.com")
        assert "Untracked" in result

        # Verify cleanup
        history = await tracker.history("https://example.com")
        assert history == []

    async def test_untrack_nonexistent(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        result = await tracker.untrack("https://missing.com")
        assert "not being tracked" in result


# ── close ─────────────────────────────────────────────────


class TestClose:
    async def test_close(self, tracker: DiffTracker, mock_extract: AsyncMock) -> None:
        await tracker.track("https://example.com")
        await tracker.close()
        # Should not raise
