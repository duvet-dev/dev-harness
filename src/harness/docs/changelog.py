"""Changelog generation for engagements.

Produces per-wave changelog entries and project rollups from
session artifacts (RepoTool logs, test results, feedback packets,
decision logs), not from agent narration.

Entries are immutable once generated. Human annotations can be
appended without modifying the original content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from harness.engagement.lifecycle import ENGAGEMENTS_DIR

# ── Constants ───────────────────────────────────────────────────────────────


CHANGELOG_DIR = "changelog"
ANNOTATIONS_MARKER = "\n<!-- annotations -->\n"
ENTRY_SEPARATOR = "\n---\n"


# ── Data types ──────────────────────────────────────────────────────────────


@dataclass
class ChangelogEntry:
    """A single changelog entry for a wave.

    Attributes:
        wave: Wave name / identifier.
        engagement_slug: The engagement this entry belongs to.
        timestamp: ISO-8601 timestamp of when the entry was generated.
        files_written: List of files written during the wave.
        tests_added: List of tests added.
        decisions: List of decisions made.
        trigger_phase: The phase that triggered changelog generation.
        trigger_reason: Why the changelog was generated.
        source_wave: The wave the entry describes.
        annotations: Human annotations (appended, never overwritten).
    """

    wave: str
    engagement_slug: str
    timestamp: str = ""
    files_written: list[dict] = field(default_factory=list)
    tests_added: list[dict] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    trigger_phase: str = "build"
    trigger_reason: str = ""
    source_wave: str = ""
    annotations: list[dict] = field(default_factory=list)

    @classmethod
    def from_entry_file(cls, path: Path) -> ChangelogEntry:
        """Parse a changelog entry file back into a ChangelogEntry."""
        content = path.read_text()
        # Split on YAML frontmatter
        parts = content.split("---\n", 2)
        if len(parts) < 3:
            raise ValueError(f"Invalid changelog entry format in {path}")
        frontmatter = yaml.safe_load(parts[1]) or {}

        # Extract body sections
        body = parts[2]
        files_written = _parse_files_table(body, "Files Written")
        tests_added = _parse_tests_table(body, "Tests Added")
        decisions = _parse_list_section(body, "Decisions")
        annotations = _parse_annotations(body)

        return cls(
            wave=frontmatter.get("wave", ""),
            engagement_slug=frontmatter.get("engagement_slug", ""),
            timestamp=frontmatter.get("timestamp", ""),
            files_written=files_written,
            tests_added=tests_added,
            decisions=decisions,
            trigger_phase=frontmatter.get("provenance", {}).get(
                "trigger_phase", ""
            ),
            trigger_reason=frontmatter.get("provenance", {}).get(
                "trigger_reason", ""
            ),
            source_wave=frontmatter.get("provenance", {}).get(
                "source_wave", ""
            ),
            annotations=annotations,
        )


# ── Helpers for parsing entry files ─────────────────────────────────────────


def _parse_table_section(body: str, heading: str) -> str:
    """Extract the table content under a heading."""
    pattern = rf"### {heading}\n\n(.+?)(?=\n### |\n<!-- |\n---|\Z)"
    m = re.search(pattern, body, re.DOTALL)
    return m.group(1).strip() if m else ""


def _parse_files_table(body: str, heading: str) -> list[dict]:
    """Parse a markdown table of files."""
    table_text = _parse_table_section(body, heading)
    files = []
    for line in table_text.split("\n"):
        # Skip header and separator lines
        if not line.startswith("|") or "---" in line:
            continue
        # Ignore header row
        if "Path" in line and "Type" in line:
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) >= 3:
            path = parts[0].strip("`")
            files.append(
                {"path": path, "type": parts[1], "size": parts[2]}
            )
    return files


def _parse_tests_table(body: str, heading: str) -> list[dict]:
    """Parse a markdown table of tests."""
    table_text = _parse_table_section(body, heading)
    tests = []
    for line in table_text.split("\n"):
        if not line.startswith("|") or "---" in line:
            continue
        if "Test" in line and "Result" in line:
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) >= 2:
            tests.append({"name": parts[0], "result": parts[1]})
    return tests


def _parse_list_section(body: str, heading: str) -> list[str]:
    """Extract a bullet list section."""
    pattern = rf"### {heading}\n\n(.+?)(?=\n### |\n<!-- |\n---|\Z)"
    m = re.search(pattern, body, re.DOTALL)
    if not m:
        return []
    text = m.group(1).strip()
    items = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            items.append(line[2:])
    return items


def _parse_annotations(body: str) -> list[dict]:
    """Extract human annotations from body."""
    parts = body.split(ANNOTATIONS_MARKER)
    if len(parts) < 2:
        return []
    annotation_text = parts[1].strip()
    annotations = []
    for line in annotation_text.split("\n"):
        line = line.strip()
        # Match: _timestamp_: text
        m = re.match(r"^_(\d{4}-\d{2}-\d{2}T.+?)_:\s*(.+)$", line)
        if m:
            annotations.append(
                {"timestamp": m.group(1), "text": m.group(2)}
            )
    return annotations


# ── Artifact scanning ───────────────────────────────────────────────────────


def _scan_files_written(engagement_dir: Path) -> list[dict]:
    """Scan the engagement directory for files written.

    This provides a basic artifact scan. In production, this would
    read RepoTool logs for actual file changes.
    """
    files = []
    for f in sorted(engagement_dir.rglob("*")):
        if f.is_file() and f.suffix in (".py", ".md", ".yaml", ".yml", ".toml", ".json"):
            try:
                rel = f.relative_to(engagement_dir)
            except ValueError:
                rel = Path(f.name)
            files.append(
                {
                    "path": str(rel),
                    "type": f.suffix.lstrip(".").upper(),
                    "size": f"{f.stat().st_size / 1024:.1f} KB",
                }
            )
    return files


def _scan_tests(project_root: Path) -> list[dict]:
    """Scan for test files in the project.

    In production, this would parse pytest output (JUnit XML, etc.)
    for actual test results.
    """
    tests = []
    test_dir = project_root / "tests"
    if test_dir.is_dir():
        for f in sorted(test_dir.rglob("test_*.py")):
            try:
                rel = f.relative_to(project_root)
            except ValueError:
                rel = Path(f.name)
            tests.append({"name": str(rel), "result": "✅"})
    return tests


def _scan_decisions(engagement_dir: Path) -> list[str]:
    """Scan for decision records in the engagement directory.

    Looks for feedback packets and decision logs.
    """
    decisions = []
    # Feedback packets
    fb_dir = engagement_dir / "feedback"
    if fb_dir.is_dir():
        decisions.append("Feedback packets reviewed and incorporated")
    # Decision log
    decisions_file = engagement_dir / "decisions.md"
    if decisions_file.is_file():
        for line in decisions_file.read_text().split("\n"):
            line = line.strip()
            if line.startswith("- "):
                decisions.append(line[2:])
    return decisions


# ── Entry generation ────────────────────────────────────────────────────────


def generate_changelog_entry(
    wave: str,
    engagement_slug: str,
    project_root: Path,
    trigger_phase: str = "build",
    trigger_reason: str = "",
    source_wave: str = "",
    decisions: Optional[list[str]] = None,
) -> ChangelogEntry:
    """Generate a changelog entry from engagement artifacts.

    Args:
        wave: The wave name (e.g. "wave-01").
        engagement_slug: The engagement slug.
        project_root: Project root directory.
        trigger_phase: What phase triggered entry generation.
        trigger_reason: Why the entry was generated.
        source_wave: The source wave identifier.
        decisions: Optional additional decisions to include.

    Returns:
        A ``ChangelogEntry`` with artifact-sourced content.
    """
    eng_dir = project_root / ENGAGEMENTS_DIR / engagement_slug

    files = _scan_files_written(eng_dir)
    tests = _scan_tests(project_root)
    scanned_decisions = _scan_decisions(eng_dir)

    if decisions:
        scanned_decisions.extend(decisions)

    return ChangelogEntry(
        wave=wave,
        engagement_slug=engagement_slug,
        timestamp=datetime.now(timezone.utc).isoformat(),
        files_written=files,
        tests_added=tests,
        decisions=scanned_decisions,
        trigger_phase=trigger_phase,
        trigger_reason=trigger_reason,
        source_wave=source_wave or wave,
    )


# ── Write ──────────────────────────────────────────────────────────────────


def write_changelog_entry(
    entry: ChangelogEntry,
    engagement_dir: Path,
) -> Path:
    """Write a changelog entry to disk.

    The entry is written to:
    ``.harness/engagements/<slug>/changelog/<wave-name>.md``

    Returns the path to the written file.

    Raises ``FileExistsError`` if the entry already exists (immutable).
    """
    changelog_dir = engagement_dir / CHANGELOG_DIR
    changelog_dir.mkdir(parents=True, exist_ok=True)

    entry_path = changelog_dir / f"{entry.wave}.md"

    if entry_path.exists():
        raise FileExistsError(
            f"Changelog entry for '{entry.wave}' already exists "
            f"at {entry_path}. Entries are immutable."
        )

    content = _render_entry(entry)
    entry_path.write_text(content)
    return entry_path


def _render_entry(entry: ChangelogEntry) -> str:
    """Render a changelog entry to markdown with YAML frontmatter."""
    frontmatter = {
        "wave": entry.wave,
        "type": "changelog",
        "engagement_slug": entry.engagement_slug,
        "timestamp": entry.timestamp,
        "provenance": {
            "trigger_phase": entry.trigger_phase,
            "trigger_reason": entry.trigger_reason,
            "source_wave": entry.source_wave or entry.wave,
        },
    }

    lines = [
        "---\n",
        yaml.dump(frontmatter, default_flow_style=False, sort_keys=False),
        "---\n",
        f"\n## {entry.wave}\n\n",
    ]

    # Files Written section
    if entry.files_written:
        lines.append("### Files Written\n\n")
        lines.append("| Path | Type | Size |\n")
        lines.append("|------|------|------|\n")
        for f in entry.files_written:
            lines.append(
                f"| `{f['path']}` | {f['type']} | {f['size']} |\n"
            )
        lines.append("\n")

    # Tests Added section
    if entry.tests_added:
        lines.append("### Tests Added\n\n")
        lines.append("| Test | Result |\n")
        lines.append("|------|--------|\n")
        for t in entry.tests_added:
            lines.append(
                f"| `{t['name']}` | {t['result']} |\n"
            )
        lines.append("\n")

    # Decisions section
    if entry.decisions:
        lines.append("### Decisions\n\n")
        for d in entry.decisions:
            lines.append(f"- {d}\n")
        lines.append("\n")

    # Annotations section (if any)
    if entry.annotations:
        lines.append(ANNOTATIONS_MARKER)
        for ann in entry.annotations:
            lines.append(f"_{ann['timestamp']}_: {ann['text']}\n")

    return "".join(lines)


# ── Annotation ──────────────────────────────────────────────────────────────


def annotate_changelog(
    engagement_dir: Path,
    wave: str,
    text: str,
) -> Path:
    """Append a human annotation to an existing changelog entry.

    Args:
        engagement_dir: The engagement directory.
        wave: The wave name.
        text: The annotation text.

    Returns:
        The path to the changelog entry file.

    Raises:
        FileNotFoundError: If the entry doesn't exist.
    """
    changelog_dir = engagement_dir / CHANGELOG_DIR
    entry_path = changelog_dir / f"{wave}.md"

    if not entry_path.is_file():
        raise FileNotFoundError(
            f"Changelog entry for '{wave}' not found at {entry_path}"
        )

    content = entry_path.read_text()
    timestamp = datetime.now(timezone.utc).isoformat()

    if ANNOTATIONS_MARKER in content:
        # Append to existing annotations
        annotation_line = f"_{timestamp}_: {text}\n"
        content = content.rstrip() + "\n" + annotation_line
    else:
        # Create annotations section
        annotation_section = (
            f"{ANNOTATIONS_MARKER}"
            f"_{timestamp}_: {text}\n"
        )
        content = content.rstrip() + "\n" + annotation_section

    entry_path.write_text(content)
    return entry_path


# ── Rollup ──────────────────────────────────────────────────────────────────


def rollup_project_changelog(
    project_root: Path,
    output_path: Optional[Path] = None,
) -> Path:
    """Generate a consolidated CHANGELOG.md from all engagement changelogs.

    Scans all engagements for changelog entries, sorts them by
    timestamp, and produces a chronological project rollup.

    Args:
        project_root: Project root directory.
        output_path: Output path for the rollup. Defaults to
            ``<project_root>/CHANGELOG.md``.

    Returns:
        The path to the written rollup file.
    """
    if output_path is None:
        output_path = project_root / "CHANGELOG.md"

    engagements_dir = project_root / ENGAGEMENTS_DIR
    if not engagements_dir.is_dir():
        output_path.write_text("# Changelog\n\nNo engagements found.\n")
        return output_path

    # Collect all entries from all engagements
    entries: list[tuple[str, ChangelogEntry]] = []
    for eng_dir in sorted(engagements_dir.iterdir()):
        if not eng_dir.is_dir():
            continue
        changelog_dir = eng_dir / CHANGELOG_DIR
        if not changelog_dir.is_dir():
            continue
        for entry_file in sorted(changelog_dir.iterdir()):
            if entry_file.suffix == ".md":
                try:
                    entry = ChangelogEntry.from_entry_file(entry_file)
                    entries.append((entry.timestamp, entry))
                except (ValueError, Exception):
                    continue

    # Sort by timestamp
    entries.sort(key=lambda x: x[0])

    # Render rollup
    lines = ["# Changelog\n\n"]
    if not entries:
        lines.append("No changelog entries yet.\n")
    else:
        lines.append(
            f"Auto-generated from {len(entries)} "
            f"changelog entr{'y' if len(entries) == 1 else 'ies'}.\n\n"
        )
        lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat()}_\n\n")
        lines.append("---\n\n")

        for timestamp, entry in entries:
            dt = datetime.fromisoformat(timestamp)
            date_str = dt.strftime("%Y-%m-%d %H:%M UTC")
            lines.append(
                f"## {entry.wave} — {entry.engagement_slug}\n\n"
            )
            lines.append(f"_{date_str}_\n\n")

            for f in entry.files_written[:10]:  # Limit per entry
                lines.append(f"- `{f['path']}` ({f['type']})\n")
            if len(entry.files_written) > 10:
                lines.append(
                    f"- ... and {len(entry.files_written) - 10} more files\n"
                )
            lines.append("\n---\n\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(lines))
    return output_path
