"""Tests for diffgrab.differ — text diff engine."""

from __future__ import annotations

from diffgrab.differ import (
    DiffResult,
    _count_diff_lines,
    _find_changed_sections,
    _generate_summary,
    _split_by_headings,
    compute_diff,
)

# ── DiffResult dataclass ─────────────────────────────────


class TestDiffResult:
    def test_default_values(self) -> None:
        r = DiffResult(url="https://example.com", changed=False)
        assert r.url == "https://example.com"
        assert r.changed is False
        assert r.added_lines == 0
        assert r.removed_lines == 0
        assert r.changed_sections == []
        assert r.unified_diff == ""
        assert r.summary == ""
        assert r.before_snapshot_id is None
        assert r.after_snapshot_id is None

    def test_custom_values(self) -> None:
        r = DiffResult(
            url="https://example.com",
            changed=True,
            added_lines=5,
            removed_lines=3,
            changed_sections=["Introduction"],
            summary="5 lines added, 3 lines removed.",
        )
        assert r.changed is True
        assert r.added_lines == 5
        assert r.changed_sections == ["Introduction"]


# ── _count_diff_lines ─────────────────────────────────────


class TestCountDiffLines:
    def test_empty_diff(self) -> None:
        assert _count_diff_lines("") == (0, 0)

    def test_additions_only(self) -> None:
        diff = "+++ b/file\n+new line 1\n+new line 2"
        added, removed = _count_diff_lines(diff)
        assert added == 2
        assert removed == 0

    def test_removals_only(self) -> None:
        diff = "--- a/file\n-old line 1\n-old line 2\n-old line 3"
        added, removed = _count_diff_lines(diff)
        assert added == 0
        assert removed == 3

    def test_mixed_changes(self) -> None:
        diff = "--- a/file\n+++ b/file\n-old\n+new\n+extra"
        added, removed = _count_diff_lines(diff)
        assert added == 2
        assert removed == 1

    def test_header_lines_not_counted(self) -> None:
        diff = "--- a/file\n+++ b/file\n@@ -1,3 +1,3 @@\n context\n-old\n+new"
        added, removed = _count_diff_lines(diff)
        assert added == 1
        assert removed == 1


# ── _split_by_headings ────────────────────────────────────


class TestSplitByHeadings:
    def test_no_headings(self) -> None:
        sections = _split_by_headings("Just a paragraph.\nAnother line.")
        assert "(top)" in sections
        assert sections["(top)"] == "Just a paragraph.\nAnother line."

    def test_single_heading(self) -> None:
        text = "Intro text\n# Section One\nSection content"
        sections = _split_by_headings(text)
        assert "(top)" in sections
        assert "Section One" in sections
        assert "Intro text" in sections["(top)"]
        assert "Section content" in sections["Section One"]

    def test_multiple_headings(self) -> None:
        text = "# First\nAAA\n## Second\nBBB\n# Third\nCCC"
        sections = _split_by_headings(text)
        assert "First" in sections
        assert "Second" in sections
        assert "Third" in sections
        assert "AAA" in sections["First"]
        assert "BBB" in sections["Second"]
        assert "CCC" in sections["Third"]

    def test_empty_text(self) -> None:
        sections = _split_by_headings("")
        assert "(top)" in sections
        assert sections["(top)"] == ""


# ── _find_changed_sections ────────────────────────────────


class TestFindChangedSections:
    def test_no_changes(self) -> None:
        text = "# Section\nSame content."
        assert _find_changed_sections(text, text) == []

    def test_content_change_in_section(self) -> None:
        before = "# Intro\nOld text.\n# Methods\nSame."
        after = "# Intro\nNew text.\n# Methods\nSame."
        changed = _find_changed_sections(before, after)
        assert "Intro" in changed
        assert "Methods" not in changed

    def test_new_section_added(self) -> None:
        before = "# Intro\nHello"
        after = "# Intro\nHello\n# New Section\nContent"
        changed = _find_changed_sections(before, after)
        assert "New Section" in changed

    def test_section_removed(self) -> None:
        before = "# Intro\nHello\n# Removed\nGone"
        after = "# Intro\nHello"
        changed = _find_changed_sections(before, after)
        assert "Removed" in changed

    def test_top_level_change(self) -> None:
        before = "Before heading.\n# Section\nContent"
        after = "After heading.\n# Section\nContent"
        changed = _find_changed_sections(before, after)
        assert "(top)" in changed


# ── _generate_summary ─────────────────────────────────────


class TestGenerateSummary:
    def test_no_changes(self) -> None:
        s = _generate_summary(0, 0, [], "https://example.com")
        assert "No changes" in s

    def test_additions_only(self) -> None:
        s = _generate_summary(5, 0, [], "https://example.com")
        assert "5 lines added" in s

    def test_removals_only(self) -> None:
        s = _generate_summary(0, 3, [], "https://example.com")
        assert "3 lines removed" in s

    def test_mixed(self) -> None:
        s = _generate_summary(5, 3, ["Intro", "Methods"], "https://example.com")
        assert "5 lines added" in s
        assert "3 lines removed" in s
        assert "Intro" in s
        assert "Methods" in s

    def test_many_sections_truncated(self) -> None:
        sections = ["A", "B", "C", "D", "E", "F", "G"]
        s = _generate_summary(1, 1, sections, "https://example.com")
        assert "+2 more" in s


# ── compute_diff ──────────────────────────────────────────


class TestComputeDiff:
    def test_identical_content(self) -> None:
        result = compute_diff("Same content.", "Same content.", url="https://example.com")
        assert result.changed is False
        assert result.added_lines == 0
        assert result.removed_lines == 0
        assert "No changes" in result.summary

    def test_different_content(self) -> None:
        result = compute_diff(
            "# Title\n\nOld paragraph.",
            "# Title\n\nNew paragraph.",
            url="https://example.com",
            before_snapshot_id=1,
            after_snapshot_id=2,
            before_timestamp="2026-01-01",
            after_timestamp="2026-01-02",
        )
        assert result.changed is True
        assert result.added_lines > 0
        assert result.removed_lines > 0
        assert result.unified_diff != ""
        assert result.before_snapshot_id == 1
        assert result.after_snapshot_id == 2

    def test_lines_added(self) -> None:
        result = compute_diff("Line 1\n", "Line 1\nLine 2\nLine 3\n", url="https://example.com")
        assert result.changed is True
        assert result.added_lines == 2
        assert result.removed_lines == 0

    def test_lines_removed(self) -> None:
        result = compute_diff("Line 1\nLine 2\nLine 3\n", "Line 1\n", url="https://example.com")
        assert result.changed is True
        assert result.added_lines == 0
        assert result.removed_lines == 2

    def test_section_detection(self) -> None:
        before = "# Intro\nOld intro.\n# Methods\nSame methods."
        after = "# Intro\nNew intro.\n# Methods\nSame methods."
        result = compute_diff(before, after, url="https://example.com")
        assert result.changed is True
        assert "Intro" in result.changed_sections
        assert "Methods" not in result.changed_sections

    def test_empty_before(self) -> None:
        result = compute_diff("", "New content.", url="https://example.com")
        assert result.changed is True
        assert result.added_lines > 0

    def test_empty_after(self) -> None:
        result = compute_diff("Old content.", "", url="https://example.com")
        assert result.changed is True
        assert result.removed_lines > 0

    def test_both_empty(self) -> None:
        result = compute_diff("", "", url="https://example.com")
        assert result.changed is False

    def test_timestamps_in_diff(self) -> None:
        result = compute_diff(
            "Old",
            "New",
            url="https://example.com",
            before_timestamp="2026-01-01",
            after_timestamp="2026-01-02",
        )
        assert "2026-01-01" in result.unified_diff
        assert "2026-01-02" in result.unified_diff

    def test_multiline_content(self) -> None:
        before = "# Page\n\nParagraph one.\n\nParagraph two.\n\n## Details\n\nSome details."
        after = "# Page\n\nParagraph one MODIFIED.\n\nParagraph two.\n\n## Details\n\nSome details.\n\nNew detail."
        result = compute_diff(before, after, url="https://example.com")
        assert result.changed is True
        assert result.added_lines >= 2
        assert result.removed_lines >= 1
