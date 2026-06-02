"""Tests for harness.docs.changelog."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from harness.docs.changelog import (
    ANNOTATIONS_MARKER,
    CHANGELOG_DIR,
    ChangelogEntry,
    _parse_annotations,
    _parse_files_table,
    _parse_list_section,
    _parse_table_section,
    _parse_tests_table,
    _render_entry,
    _scan_decisions,
    _scan_files_written,
    _scan_tests,
    annotate_changelog,
    generate_changelog_entry,
    rollup_project_changelog,
    write_changelog_entry,
)


class TestChangelogEntry:
    def test_default_timestamp(self):
        entry = ChangelogEntry(wave="wave-01", engagement_slug="test-eng")
        assert entry.timestamp == ""

    def test_from_entry_file_roundtrip(self, tmp_path):
        entry = ChangelogEntry(
            wave="wave-01",
            engagement_slug="test-eng",
            timestamp="2026-05-23T12:00:00+00:00",
            files_written=[{"path": "src/main.py", "type": "PY", "size": "1.2 KB"}],
            tests_added=[{"name": "test_main", "result": "✅"}],
            decisions=["Added new API"],
        )
        content = _render_entry(entry)
        entry_path = tmp_path / "wave-01.md"
        entry_path.write_text(content)
        parsed = ChangelogEntry.from_entry_file(entry_path)
        assert parsed.wave == "wave-01"
        assert parsed.engagement_slug == "test-eng"
        assert len(parsed.files_written) == 1
        assert len(parsed.tests_added) == 1
        assert "Added new API" in parsed.decisions

    def test_from_entry_file_invalid(self, tmp_path):
        path = tmp_path / "bad.md"
        path.write_text("No frontmatter")
        with pytest.raises(ValueError):
            ChangelogEntry.from_entry_file(path)


class TestParseHelpers:
    def test_parse_table_section(self):
        body = "### Files Written\n\n| Path | Type | Size |\n|------|------|------|\n| `a` | PY | 1KB |\n"
        result = _parse_table_section(body, "Files Written")
        assert "| Path |" in result

    def test_parse_files_table(self):
        body = "### Files Written\n\n| Path | Type | Size |\n|------|------|------|\n| `a.py` | PY | 1KB |\n| `b.py` | MD | 2KB |\n"
        files = _parse_files_table(body, "Files Written")
        assert len(files) == 2
        assert files[0]["path"] == "a.py"
        assert files[1]["type"] == "MD"

    def test_parse_files_table_empty(self):
        body = "No table here\n"
        assert _parse_files_table(body, "Files Written") == []

    def test_parse_tests_table(self):
        body = "### Tests Added\n\n| Test | Result |\n|------|--------|\n| `test_a` | ✅ |\n"
        tests = _parse_tests_table(body, "Tests Added")
        assert len(tests) == 1
        assert tests[0]["name"] == "`test_a`"

    def test_parse_list_section(self):
        body = "### Decisions\n\n- Decision A\n- Decision B\n\n### Other\n"
        items = _parse_list_section(body, "Decisions")
        assert items == ["Decision A", "Decision B"]

    def test_parse_list_section_empty(self):
        body = "### Decisions\n\nNo items here\n"
        assert _parse_list_section(body, "Decisions") == []

    def test_parse_annotations(self):
        body = f"content\n{ANNOTATIONS_MARKER}_2026-05-23T12:00:00_: note text\n"
        anns = _parse_annotations(body)
        assert len(anns) == 1
        assert anns[0]["text"] == "note text"

    def test_parse_annotations_none(self):
        body = "no annotations here"
        assert _parse_annotations(body) == []


class TestScanFilesWritten:
    def test_scans_directory(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "main.py").write_text("")
        (tmp_path / "config.yaml").write_text("")
        (tmp_path / "ignore.bin").write_text("")  # binary not in supported types... actually .bin should be skipped
        files = _scan_files_written(tmp_path)
        ext_types = {f["type"] for f in files}
        assert "PY" in ext_types
        assert "YAML" in ext_types


class TestScanTests:
    def test_finds_test_files(self, tmp_path):
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_a.py").write_text("")
        (test_dir / "test_b.py").write_text("")
        tests = _scan_tests(tmp_path)
        assert len(tests) == 2


class TestScanDecisions:
    def test_detects_feedback_dir(self, tmp_path):
        (tmp_path / "feedback").mkdir(parents=True)
        decisions = _scan_decisions(tmp_path)
        assert any("Feedback" in d for d in decisions)

    def test_reads_decisions_file(self, tmp_path):
        decisions_file = tmp_path / "decisions.md"
        decisions_file.write_text("- Decision A\n- Decision B\n")
        decisions = _scan_decisions(tmp_path)
        assert "Decision A" in decisions
        assert "Decision B" in decisions


class TestGenerateChangelogEntry:
    def test_generates_entry(self, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        entry = generate_changelog_entry("wave-01", "test-eng", tmp_path)
        assert entry.wave == "wave-01"
        assert entry.engagement_slug == "test-eng"

    def test_includes_extra_decisions(self, tmp_path):
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        entry = generate_changelog_entry("wave-01", "test-eng", tmp_path, decisions=["Custom decision"])
        assert any("Custom decision" in d for d in entry.decisions)


class TestWriteChangelogEntry:
    def test_writes_entry(self, tmp_path):
        entry = ChangelogEntry(wave="wave-01", engagement_slug="test-eng")
        path = write_changelog_entry(entry, tmp_path)
        assert path.is_file()
        assert path.name == "wave-01.md"

    def test_raises_on_duplicate(self, tmp_path):
        entry = ChangelogEntry(wave="wave-01", engagement_slug="test-eng")
        write_changelog_entry(entry, tmp_path)
        with pytest.raises(FileExistsError):
            write_changelog_entry(entry, tmp_path)


class TestAnnotateChangelog:
    def test_appends_annotation(self, tmp_path):
        entry = ChangelogEntry(wave="wave-01", engagement_slug="test-eng")
        write_changelog_entry(entry, tmp_path)
        annotate_changelog(tmp_path, "wave-01", "Human note")
        content = (tmp_path / CHANGELOG_DIR / "wave-01.md").read_text()
        assert ANNOTATIONS_MARKER in content
        assert "Human note" in content

    def test_appends_to_existing_annotation_block(self, tmp_path):
        entry = ChangelogEntry(wave="wave-01", engagement_slug="test-eng")
        write_changelog_entry(entry, tmp_path)
        annotate_changelog(tmp_path, "wave-01", "First note")
        annotate_changelog(tmp_path, "wave-01", "Second note")
        content = (tmp_path / CHANGELOG_DIR / "wave-01.md").read_text()
        # Should have exactly one annotations marker
        assert content.count(ANNOTATIONS_MARKER) == 1
        assert "First note" in content
        assert "Second note" in content

    def test_raises_if_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            annotate_changelog(tmp_path, "nonexistent", "note")


class TestRollupProjectChangelog:
    def test_generates_rollup_from_entries(self, tmp_path):
        # Create engagement with entry
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        entry = ChangelogEntry(
            wave="wave-01",
            engagement_slug="test-eng",
            timestamp="2026-05-23T12:00:00+00:00",
            files_written=[{"path": "a.py", "type": "PY", "size": "1KB"}],
        )
        write_changelog_entry(entry, eng_dir)

        output_path = tmp_path / "CHANGELOG.md"
        rollup_project_changelog(tmp_path, output_path)
        content = output_path.read_text()
        assert "wave-01" in content
        assert "test-eng" in content
        assert "a.py" in content

    def test_handles_no_engagements(self, tmp_path):
        output_path = tmp_path / "CHANGELOG.md"
        rollup_project_changelog(tmp_path, output_path)
        content = output_path.read_text()
        assert "No engagements" in content
