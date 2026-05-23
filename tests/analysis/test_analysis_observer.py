"""Tests for harness.analysis.observer — observer mode analysis.

Tests analyse() and analyse_async() functions.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from harness.analysis.base import ScanResult


class TestAnalyse:
    """Tests for analyse()."""

    def test_path_not_found(self):
        """Returns error dict when path does not exist."""
        result = analyse("/nonexistent")
        assert result["status"] == "error"
        assert "Path does not exist" in result["message"]

    def test_basic_analysis(self, tmp_path):
        """Basic analysis runs fast scans."""
        from harness.analysis.observer import analyse
        (tmp_path / "hello.py").write_text("print('hello')\n")
        result = analyse(tmp_path, deep=False)
        assert result["status"] == "ok"
        assert "structure" in result["scans"]
        assert "git-diff" in result["scans"]
        assert result["deep"] is False

    def test_deep_analysis(self, tmp_path):
        """Deep analysis runs additional scans."""
        from harness.analysis.observer import analyse
        (tmp_path / "src" / "module.py").parent.mkdir(parents=True)
        (tmp_path / "src" / "module.py").write_text("x=1\n")
        (tmp_path / "tests" / "test_module.py").parent.mkdir(parents=True)
        (tmp_path / "tests" / "test_module.py").write_text("def test_x(): pass\n")

        result = analyse(tmp_path, deep=True)
        assert result["status"] == "ok"
        assert "arch-conformance" in result["scans"]
        assert "coverage" in result["scans"]
        assert "dead-code" in result["scans"]

    def test_deep_with_llm_fallback(self, tmp_path):
        """Deep analysis gracefully degrades when LLM assessment fails."""
        from harness.analysis.observer import analyse
        (tmp_path / "hello.py").write_text("x=1\n")

        result = analyse(tmp_path, deep=True)
        assert result["status"] == "ok"
        # LLM assessment may fail gracefully — check report has content
        assert result["report"] != ""

    def test_report_file_written(self, tmp_path):
        """Report is written to disk when report_file is provided."""
        from harness.analysis.observer import analyse
        (tmp_path / "hello.py").write_text("x=1\n")
        report_file = tmp_path / "report.md"

        result = analyse(tmp_path, deep=False, report_file=str(report_file))
        assert result["report_file"] == str(report_file)
        assert report_file.exists()
        content = report_file.read_text()
        assert len(content) > 0

    def test_report_file_creates_parents(self, tmp_path):
        """Parent directories for report_file are created."""
        from harness.analysis.observer import analyse
        (tmp_path / "hello.py").write_text("x=1\n")
        report_file = tmp_path / "subdir" / "report.md"

        result = analyse(tmp_path, deep=False, report_file=str(report_file))
        assert result["report_file"] == str(report_file)
        assert report_file.exists()

    def test_scan_summaries_included(self, tmp_path):
        """Result includes scan summaries."""
        from harness.analysis.observer import analyse
        (tmp_path / "hello.py").write_text("print('hello')\n")
        result = analyse(tmp_path)
        scans = result["scans"]
        assert all("findings" in s for s in scans.values())
        assert all("summary" in s for s in scans.values())


# Import here to avoid issues with module-level asyncio
from harness.analysis.observer import analyse


class TestAnalyseAsync:
    """Tests for analyse_async()."""

    @pytest.mark.asyncio
    async def test_path_not_found(self):
        """Returns error dict when path does not exist."""
        from harness.analysis.observer import analyse_async
        result = await analyse_async("/nonexistent")
        assert result["status"] == "error"
        assert "Path does not exist" in result["message"]

    @pytest.mark.asyncio
    async def test_basic_async_analysis(self, tmp_path):
        """Basic async analysis runs fast scans."""
        from harness.analysis.observer import analyse_async
        (tmp_path / "hello.py").write_text("print('hello')\n")
        result = await analyse_async(tmp_path, deep=False)
        assert result["status"] == "ok"
        assert "structure" in result["scans"]
        assert "git-diff" in result["scans"]

    @pytest.mark.asyncio
    async def test_deep_async_analysis(self, tmp_path):
        """Deep async analysis runs additional scans."""
        from harness.analysis.observer import analyse_async
        (tmp_path / "src" / "module.py").parent.mkdir(parents=True)
        (tmp_path / "src" / "module.py").write_text("x=1\n")
        (tmp_path / "tests" / "test_module.py").parent.mkdir(parents=True)
        (tmp_path / "tests" / "test_module.py").write_text("def test_x(): pass\n")

        result = await analyse_async(tmp_path, deep=True)
        assert result["status"] == "ok"
        assert "arch-conformance" in result["scans"]

    @pytest.mark.asyncio
    async def test_async_with_report_file(self, tmp_path):
        """Async analysis writes report to disk."""
        from harness.analysis.observer import analyse_async
        (tmp_path / "hello.py").write_text("x=1\n")
        report_file = tmp_path / "async_report.md"

        result = await analyse_async(tmp_path, report_file=str(report_file))
        assert result["report_file"] == str(report_file)
        assert report_file.exists()
