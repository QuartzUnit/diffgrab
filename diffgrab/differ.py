"""Text diff engine — unified diff + section-level analysis."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

# Markdown heading pattern (ATX style: # Heading)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass
class DiffResult:
    """Structured result of comparing two snapshots."""

    url: str
    changed: bool
    added_lines: int = 0
    removed_lines: int = 0
    changed_sections: list[str] = field(default_factory=list)
    unified_diff: str = ""
    summary: str = ""
    before_snapshot_id: int | None = None
    after_snapshot_id: int | None = None
    before_timestamp: str = ""
    after_timestamp: str = ""


def _count_diff_lines(diff_text: str) -> tuple[int, int]:
    """Count added and removed lines from unified diff output."""
    added = 0
    removed = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return added, removed


def _find_changed_sections(before_text: str, after_text: str) -> list[str]:
    """Identify markdown headings whose sections contain changes.

    Strategy: split each document by headings, compare section content.
    """
    before_sections = _split_by_headings(before_text)
    after_sections = _split_by_headings(after_text)

    changed: list[str] = []
    all_headings = set(before_sections.keys()) | set(after_sections.keys())

    for heading in sorted(all_headings):
        b_content = before_sections.get(heading, "")
        a_content = after_sections.get(heading, "")
        if b_content != a_content:
            changed.append(heading)

    return changed


def _split_by_headings(text: str) -> dict[str, str]:
    """Split markdown text into sections keyed by heading.

    Text before the first heading goes under "(top)".
    """
    sections: dict[str, str] = {}
    current_heading = "(top)"
    current_lines: list[str] = []

    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            # Save previous section
            sections[current_heading] = "\n".join(current_lines)
            current_heading = match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    sections[current_heading] = "\n".join(current_lines)
    return sections


def _generate_summary(
    added: int,
    removed: int,
    changed_sections: list[str],
    url: str,
) -> str:
    """Generate a human-readable summary of changes."""
    if added == 0 and removed == 0:
        return f"No changes detected for {url}."

    parts: list[str] = []

    if added > 0 and removed > 0:
        parts.append(f"{added} lines added, {removed} lines removed")
    elif added > 0:
        parts.append(f"{added} lines added")
    else:
        parts.append(f"{removed} lines removed")

    if changed_sections:
        section_names = ", ".join(changed_sections[:5])
        if len(changed_sections) > 5:
            section_names += f" (+{len(changed_sections) - 5} more)"
        parts.append(f"in sections: {section_names}")

    return ". ".join(parts) + "."


def compute_diff(
    before_text: str,
    after_text: str,
    url: str = "",
    before_snapshot_id: int | None = None,
    after_snapshot_id: int | None = None,
    before_timestamp: str = "",
    after_timestamp: str = "",
) -> DiffResult:
    """Compute structured diff between two markdown texts.

    Args:
        before_text: The older markdown content.
        after_text: The newer markdown content.
        url: The URL being compared.
        before_snapshot_id: Database ID of the older snapshot.
        after_snapshot_id: Database ID of the newer snapshot.
        before_timestamp: Timestamp of the older snapshot.
        after_timestamp: Timestamp of the newer snapshot.

    Returns:
        DiffResult with all diff details.
    """
    changed = before_text != after_text

    if not changed:
        return DiffResult(
            url=url,
            changed=False,
            summary=f"No changes detected for {url}.",
            before_snapshot_id=before_snapshot_id,
            after_snapshot_id=after_snapshot_id,
            before_timestamp=before_timestamp,
            after_timestamp=after_timestamp,
        )

    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"before ({before_timestamp})" if before_timestamp else "before",
            tofile=f"after ({after_timestamp})" if after_timestamp else "after",
            lineterm="",
        )
    )
    unified_diff = "\n".join(diff_lines)

    added, removed = _count_diff_lines(unified_diff)
    changed_sections = _find_changed_sections(before_text, after_text)
    summary = _generate_summary(added, removed, changed_sections, url)

    return DiffResult(
        url=url,
        changed=True,
        added_lines=added,
        removed_lines=removed,
        changed_sections=changed_sections,
        unified_diff=unified_diff,
        summary=summary,
        before_snapshot_id=before_snapshot_id,
        after_snapshot_id=after_snapshot_id,
        before_timestamp=before_timestamp,
        after_timestamp=after_timestamp,
    )
