"""Tests for diffgrab.db — SQLite storage layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from diffgrab.db import Database


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    """Create a fresh database for each test."""
    db_path = str(tmp_path / "test.db")
    d = Database(db_path)
    # Force schema init
    d._get_conn()
    return d


@pytest.fixture()
def db_with_data(db: Database) -> Database:
    """Database pre-populated with a tracked URL and snapshots."""
    db.add_tracked_url("https://example.com", 24)
    # Use explicit timestamps to ensure deterministic ordering
    conn = db._get_conn()
    conn.execute(
        "INSERT INTO snapshots (url, content_hash, markdown, title, word_count, captured_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("https://example.com", "hash_v1", "# Example\n\nHello world.", "Example", 2, "2026-01-01 00:00:00"),
    )
    conn.execute(
        "INSERT INTO snapshots (url, content_hash, markdown, title, word_count, captured_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("https://example.com", "hash_v2", "# Example\n\nHello updated world.", "Example", 3, "2026-01-02 00:00:00"),
    )
    conn.commit()
    return db


# ── tracked_urls ──────────────────────────────────────────


class TestTrackedUrls:
    def test_add_tracked_url(self, db: Database) -> None:
        row_id = db.add_tracked_url("https://example.com", 24)
        assert row_id > 0

    def test_add_tracked_url_duplicate(self, db: Database) -> None:
        id1 = db.add_tracked_url("https://example.com", 24)
        id2 = db.add_tracked_url("https://example.com", 24)
        assert id1 == id2

    def test_get_tracked_url(self, db: Database) -> None:
        db.add_tracked_url("https://example.com", 12)
        result = db.get_tracked_url("https://example.com")
        assert result is not None
        assert result["url"] == "https://example.com"
        assert result["interval_hours"] == 12

    def test_get_tracked_url_not_found(self, db: Database) -> None:
        result = db.get_tracked_url("https://missing.com")
        assert result is None

    def test_get_all_tracked_urls_empty(self, db: Database) -> None:
        result = db.get_all_tracked_urls()
        assert result == []

    def test_get_all_tracked_urls(self, db: Database) -> None:
        db.add_tracked_url("https://a.com", 6)
        db.add_tracked_url("https://b.com", 12)
        result = db.get_all_tracked_urls()
        assert len(result) == 2
        urls = {r["url"] for r in result}
        assert urls == {"https://a.com", "https://b.com"}

    def test_update_last_checked(self, db: Database) -> None:
        db.add_tracked_url("https://example.com")
        record = db.get_tracked_url("https://example.com")
        assert record is not None
        assert record["last_checked_at"] is None
        db.update_last_checked("https://example.com")
        record = db.get_tracked_url("https://example.com")
        assert record is not None
        assert record["last_checked_at"] is not None

    def test_remove_tracked_url(self, db_with_data: Database) -> None:
        removed = db_with_data.remove_tracked_url("https://example.com")
        assert removed is True
        assert db_with_data.get_tracked_url("https://example.com") is None
        assert db_with_data.get_snapshots("https://example.com") == []

    def test_remove_tracked_url_not_found(self, db: Database) -> None:
        removed = db.remove_tracked_url("https://missing.com")
        assert removed is False

    def test_default_interval(self, db: Database) -> None:
        db.add_tracked_url("https://example.com")
        record = db.get_tracked_url("https://example.com")
        assert record is not None
        assert record["interval_hours"] == 24


# ── snapshots ─────────────────────────────────────────────


class TestSnapshots:
    def test_add_snapshot(self, db: Database) -> None:
        db.add_tracked_url("https://example.com")
        sid = db.add_snapshot("https://example.com", "abc123", "# Hello", "Hello", 1)
        assert sid > 0

    def test_get_latest_snapshot(self, db_with_data: Database) -> None:
        latest = db_with_data.get_latest_snapshot("https://example.com")
        assert latest is not None
        assert latest["content_hash"] == "hash_v2"

    def test_get_latest_snapshot_no_snapshots(self, db: Database) -> None:
        db.add_tracked_url("https://example.com")
        latest = db.get_latest_snapshot("https://example.com")
        assert latest is None

    def test_get_snapshot_by_id(self, db_with_data: Database) -> None:
        latest = db_with_data.get_latest_snapshot("https://example.com")
        assert latest is not None
        by_id = db_with_data.get_snapshot_by_id(latest["id"])
        assert by_id is not None
        assert by_id["content_hash"] == latest["content_hash"]

    def test_get_snapshot_by_id_not_found(self, db: Database) -> None:
        result = db.get_snapshot_by_id(99999)
        assert result is None

    def test_get_snapshots(self, db_with_data: Database) -> None:
        snapshots = db_with_data.get_snapshots("https://example.com")
        assert len(snapshots) == 2
        # Newest first
        assert snapshots[0]["content_hash"] == "hash_v2"
        assert snapshots[1]["content_hash"] == "hash_v1"

    def test_get_snapshots_with_count(self, db_with_data: Database) -> None:
        snapshots = db_with_data.get_snapshots("https://example.com", count=1)
        assert len(snapshots) == 1

    def test_get_snapshots_empty(self, db: Database) -> None:
        snapshots = db.get_snapshots("https://example.com")
        assert snapshots == []

    def test_get_snapshot_pair(self, db_with_data: Database) -> None:
        before, after = db_with_data.get_snapshot_pair("https://example.com")
        assert before is not None
        assert after is not None
        assert before["content_hash"] == "hash_v1"
        assert after["content_hash"] == "hash_v2"

    def test_get_snapshot_pair_single(self, db: Database) -> None:
        db.add_tracked_url("https://example.com")
        db.add_snapshot("https://example.com", "only_one", "# Only", "Only", 1)
        before, after = db.get_snapshot_pair("https://example.com")
        assert before is None
        assert after is not None
        assert after["content_hash"] == "only_one"

    def test_get_snapshot_pair_empty(self, db: Database) -> None:
        before, after = db.get_snapshot_pair("https://example.com")
        assert before is None
        assert after is None

    def test_snapshot_fields(self, db: Database) -> None:
        db.add_tracked_url("https://example.com")
        db.add_snapshot("https://example.com", "h1", "# Title\n\nBody text.", "Title", 2)
        snap = db.get_latest_snapshot("https://example.com")
        assert snap is not None
        assert snap["url"] == "https://example.com"
        assert snap["content_hash"] == "h1"
        assert snap["markdown"] == "# Title\n\nBody text."
        assert snap["title"] == "Title"
        assert snap["word_count"] == 2
        assert snap["captured_at"] is not None


# ── lifecycle ─────────────────────────────────────────────


class TestLifecycle:
    def test_close_and_reopen(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = Database(db_path)
        db.add_tracked_url("https://example.com")
        db.close()

        # Reopen
        db2 = Database(db_path)
        record = db2.get_tracked_url("https://example.com")
        assert record is not None
        db2.close()

    def test_auto_create_parent_dirs(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "nested" / "deep" / "test.db")
        db = Database(db_path)
        db.add_tracked_url("https://example.com")
        assert db.get_tracked_url("https://example.com") is not None
        db.close()
        assert Path(db_path).exists()
