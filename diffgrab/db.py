"""SQLite storage for tracked URLs and snapshots."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "~/.local/share/diffgrab/diffgrab.db"

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS tracked_urls (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    interval_hours INTEGER DEFAULT 24,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_checked_at TEXT
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    markdown TEXT NOT NULL,
    title TEXT DEFAULT '',
    word_count INTEGER DEFAULT 0,
    captured_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (url) REFERENCES tracked_urls(url)
);
"""


class Database:
    """SQLite database for diffgrab storage."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        resolved = Path(db_path).expanduser()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        self._path = str(resolved)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._init_schema()
        return self._conn

    def _init_schema(self) -> None:
        conn = self._conn
        if conn is None:
            return
        conn.executescript(_SCHEMA)
        conn.commit()

    # ── tracked_urls ──────────────────────────────────────────

    def add_tracked_url(self, url: str, interval_hours: int = 24) -> int:
        """Add a URL to tracking. Returns row id."""
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT OR IGNORE INTO tracked_urls (url, interval_hours) VALUES (?, ?)",
            (url, interval_hours),
        )
        conn.commit()
        if cur.lastrowid and cur.rowcount > 0:
            return cur.lastrowid
        # Already existed — fetch id
        row = conn.execute("SELECT id FROM tracked_urls WHERE url = ?", (url,)).fetchone()
        return row["id"] if row else 0

    def get_tracked_url(self, url: str) -> dict | None:
        """Get a single tracked URL record."""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM tracked_urls WHERE url = ?", (url,)).fetchone()
        return dict(row) if row else None

    def get_all_tracked_urls(self) -> list[dict]:
        """Get all tracked URLs."""
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM tracked_urls ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    def update_last_checked(self, url: str) -> None:
        """Update the last_checked_at timestamp for a URL."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE tracked_urls SET last_checked_at = CURRENT_TIMESTAMP WHERE url = ?",
            (url,),
        )
        conn.commit()

    def remove_tracked_url(self, url: str) -> bool:
        """Remove a URL from tracking. Returns True if removed."""
        conn = self._get_conn()
        conn.execute("DELETE FROM snapshots WHERE url = ?", (url,))
        cur = conn.execute("DELETE FROM tracked_urls WHERE url = ?", (url,))
        conn.commit()
        return cur.rowcount > 0

    # ── snapshots ─────────────────────────────────────────────

    def add_snapshot(
        self,
        url: str,
        content_hash: str,
        markdown: str,
        title: str = "",
        word_count: int = 0,
    ) -> int:
        """Store a new snapshot. Returns row id."""
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO snapshots (url, content_hash, markdown, title, word_count) VALUES (?, ?, ?, ?, ?)",
            (url, content_hash, markdown, title, word_count),
        )
        conn.commit()
        return cur.lastrowid or 0

    def get_latest_snapshot(self, url: str) -> dict | None:
        """Get the most recent snapshot for a URL."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM snapshots WHERE url = ? ORDER BY captured_at DESC LIMIT 1",
            (url,),
        ).fetchone()
        return dict(row) if row else None

    def get_snapshot_by_id(self, snapshot_id: int) -> dict | None:
        """Get a snapshot by its ID."""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        return dict(row) if row else None

    def get_snapshots(self, url: str, count: int = 10) -> list[dict]:
        """Get recent snapshots for a URL, newest first."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM snapshots WHERE url = ? ORDER BY captured_at DESC LIMIT ?",
            (url, count),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_snapshot_pair(self, url: str) -> tuple[dict | None, dict | None]:
        """Get the two most recent snapshots (before, after). Returns (older, newer)."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM snapshots WHERE url = ? ORDER BY captured_at DESC LIMIT 2",
            (url,),
        ).fetchall()
        if len(rows) == 0:
            return None, None
        if len(rows) == 1:
            return None, dict(rows[0])
        return dict(rows[1]), dict(rows[0])

    # ── lifecycle ─────────────────────────────────────────────

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
