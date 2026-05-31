"""Tests for harness.analysis.fast — fast scan, git diff, and summary.

Tests scan_structure, scan_git_diff, and produce_summary with tmp_path
for filesystem operations and mock for subprocess calls.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from harness.analysis.base import ScanResult
from harness.scm.git_types import DiffResult
from harness.analysis.fast import (
    scan_structure,
    scan_git_diff,
    produce_summary,
    LANGUAGE_MAP,
    SKIP_DIRS,
    SKIP_EXTS,
)


class TestScanStructure:
    """Tests for scan_structure()."""

    def test_path_not_found(self):
        """Returns error ScanResult when path does not exist."""
        result = scan_structure("/nonexistent/path")
        assert result.scan_name == "structure"
        assert len(result.findings) == 1
        assert result.findings[0].severity == "error"
        assert "Path does not exist" in result.findings[0].message
        assert result.summary == "Path not found"

    def test_empty_directory(self, tmp_path):
        """Scans an empty directory."""
        result = scan_structure(tmp_path)
        assert result.scan_name == "structure"
        assert result.metrics["file_count"] == 0
        assert result.metrics["total_lines"] == 0
        assert result.metrics["dir_count"] >= 1
        assert "0 files, 0 lines" in result.summary

    def test_single_python_file(self, tmp_path):
        """Counts a single Python file correctly."""
        src = tmp_path / "hello.py"
        src.write_text("print('hello')\nprint('world')\n")
        result = scan_structure(tmp_path)
        assert result.metrics["file_count"] == 1
        assert result.metrics["total_lines"] == 2
        assert result.metrics["languages"].get("python", {}).get("files") == 1

    def test_skip_dirs_respected(self, tmp_path):
        """Directories in SKIP_DIRS are not scanned."""
        (tmp_path / "__pycache__" / "cached.py").parent.mkdir(parents=True)
        (tmp_path / "__pycache__" / "cached.py").write_text("x=1\n")
        (tmp_path / "real.py").write_text("y=2\n")
        result = scan_structure(tmp_path)
        assert result.metrics["file_count"] == 1  # only real.py
        assert "__pycache__" not in str(result.metrics)

    def test_skip_exts_respected(self, tmp_path):
        """Files with extensions in SKIP_EXTS are skipped."""
        (tmp_path / "module.pyc").write_text("binary")
        (tmp_path / "module.py").write_text("code\n")
        result = scan_structure(tmp_path)
        assert result.metrics["file_count"] == 1  # only .py

    def test_language_breakdown(self, tmp_path):
        """Multiple file types produce a language breakdown."""
        (tmp_path / "script.py").write_text("a\n")
        (tmp_path / "readme.md").write_text("# Title\n")
        (tmp_path / "config.yaml").write_text("key: val\n")
        result = scan_structure(tmp_path)
        langs = result.metrics["languages"]
        assert "python" in langs
        assert "markdown" in langs
        assert "yaml" in langs
        assert result.metrics["file_count"] == 3

    def test_line_count_across_languages(self, tmp_path):
        """Total lines aggregates across all languages."""
        (tmp_path / "a.py").write_text("line1\nline2\n")
        (tmp_path / "b.md").write_text("line1\n")
        result = scan_structure(tmp_path)
        assert result.metrics["total_lines"] == 3

    def test_summary_contains_language_info(self, tmp_path):
        """Summary includes language breakdown when appropriate."""
        (tmp_path / "test.py").write_text("x=1\n")
        result = scan_structure(tmp_path)
        assert "python" in result.summary
        assert "1 files" in result.summary or "1 file" in result.summary

    def test_oserror_file_handling(self, tmp_path):
        """OSError reading a file is handled gracefully (lines 99-100)."""
        from unittest.mock import patch, mock_open
        (tmp_path / "broken.py").write_text("some code\n")
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = scan_structure(tmp_path)
        assert result.metrics["file_count"] == 1
        assert result.metrics["total_lines"] == 0

    def test_unicode_file_handling(self, tmp_path):
        """Handles files that trigger UnicodeDecodeError gracefully."""
        file = tmp_path / "binary.bin"
        file.write_bytes(b"\x80\x81\x82\n")
        result = scan_structure(tmp_path)
        # Binary extension not in skip_exts, so it's counted; with errors="replace"
        # the newline is still found so lines = 1
        assert result.metrics["total_lines"] == 1


class TestScanGitDiff:
    """Tests for scan_git_diff()."""

    def test_non_git_repo(self, tmp_path):
        """Returns info finding when not a git repo."""
        result = scan_git_diff(tmp_path)
        assert result.scan_name == "git-diff"
        assert len(result.findings) >= 1
        assert "Not a git repository" in result.summary

    @patch("harness.analysis.fast.GitRepo")
    def test_git_available_success(self, mock_git_repo, tmp_path):
        """Returns diff metrics when git is available."""
        mock_instance = MagicMock()
        mock_instance.diff.return_value = DiffResult(
            files_changed=["src/main.py"], insertions=9, deletions=1
        )
        mock_instance.branch.return_value = "main"
        mock_git_repo.return_value = mock_instance

        result = scan_git_diff(tmp_path)
        assert result.scan_name == "git-diff"
        assert result.metrics.get("insertions") == 9
        assert result.metrics.get("deletions") == 1
        assert result.metrics.get("changed_count") == 1
        assert result.metrics.get("branch") == "main"
        assert "main" in result.summary

    @patch("harness.analysis.fast.GitRepo")
    def test_git_not_a_repo_via_rev_parse(self, mock_git_repo, tmp_path):
        """Returns info finding when GitRepo construction fails."""
        mock_git_repo.side_effect = Exception("not a git repo")
        result = scan_git_diff(tmp_path)
        assert "Not a git repository" in result.summary

    @patch("harness.analysis.fast.GitRepo")
    def test_git_command_not_found(self, mock_git_repo, tmp_path):
        """Returns info finding when git is not installed."""
        mock_git_repo.side_effect = Exception("git not found")
        result = scan_git_diff(tmp_path)
        assert "Git unavailable" in result.summary or "Not a git repository" in result.summary

    @patch("harness.analysis.fast.GitRepo")
    def test_git_diff_timeout(self, mock_git_repo, tmp_path):
        """Returns warning finding when git diff fails."""
        mock_instance = MagicMock()
        mock_instance.diff.side_effect = Exception("diff failed")
        mock_git_repo.return_value = mock_instance

        result = scan_git_diff(tmp_path)
        assert "Git diff failed" in result.summary

    @patch("harness.analysis.fast.GitRepo")
    def test_git_diff_name_only_timeout(self, mock_git_repo, tmp_path):
        """Handles diff failure with fallback."""
        mock_instance = MagicMock()
        mock_instance.diff.side_effect = Exception("diff failed")
        mock_git_repo.return_value = mock_instance

        result = scan_git_diff(tmp_path)
        assert "Git diff failed" in result.summary


class TestProduceSummary:
    """Tests for produce_summary()."""

    def test_empty_results(self):
        """Empty results list produces empty string."""
        assert produce_summary([]) == ""

    def test_single_result(self):
        """Single result returns its summary."""
        r = ScanResult(scan_name="scan", summary="1 file scanned")
        assert produce_summary([r]) == "1 file scanned"

    def test_multiple_results_with_findings(self):
        """Multiple results are joined with pipe separator."""
        r1 = ScanResult(scan_name="s1", summary="scan 1")
        r2 = ScanResult(scan_name="s2", summary="scan 2")
        result = produce_summary([r1, r2])
        assert " | " in result
        assert "scan 1" in result
        assert "scan 2" in result

    def test_results_with_counts(self):
        """Findings counts are appended in parentheses."""
        r = ScanResult(
            scan_name="scan",
            summary="project scan",
            findings=[
                ScanResult(severity="error") if False else None,
            ],
        )
        # Use a result with actual findings
        from harness.analysis.base import Finding
        r2 = ScanResult(
            scan_name="scan",
            summary="project scan",
            findings=[Finding(severity="error"), Finding(severity="warning")],
        )
        result = produce_summary([r2])
        assert "1 err" in result
        assert "1 warn" in result
        assert "project scan" in result
        assert "(" in result

    def test_result_without_counts(self):
        """Results with no findings don't show counts."""
        r = ScanResult(scan_name="scan", summary="clean scan")
        assert produce_summary([r]) == "clean scan"


class TestConstants:
    """Tests for module-level constants."""

    def test_language_map_has_python(self):
        assert "python" in LANGUAGE_MAP
        assert ".py" in LANGUAGE_MAP["python"]

    def test_language_map_no_duplicates(self):
        # Check for duplicate keys
        keys = list(LANGUAGE_MAP.keys())
        assert len(keys) == len(set(keys))

    def test_skip_dirs_has_git(self):
        assert ".git" in SKIP_DIRS

    def test_skip_exts_has_pyc(self):
        assert ".pyc" in SKIP_EXTS
