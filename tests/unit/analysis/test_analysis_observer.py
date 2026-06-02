"""Tests for harness.analysis.observer — observer mode analysis.

Tests analyse() and analyse_async() functions.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from harness.analysis.base import ScanResult

# ── Helper: a mock AssessmentReport that avoids real LLM calls ──────────────


def _mock_assessment_report() -> MagicMock:
    """Return a minimal AssessmentReport-like mock.

    Matches what analyse()/analyse_async() need from
    ``assess(path, deep=True).to_dict()``: a dict with
    ``{"assessment": ..., "report": str}``.
    """
    r = MagicMock()
    r.to_dict.return_value = {
        "assessment": {"path": "/mock", "score": "good", "metrics": {}},
        "report": "# Mock Assessment\n\nThis is a stubbed report.",
    }
    return r


# ── Tests for analyse() (sync) ─────────────────────────────────────────────


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
        """Deep analysis runs additional scans (LLM assessment mocked)."""
        from harness.analysis.observer import analyse
        (tmp_path / "src" / "module.py").parent.mkdir(parents=True)
        (tmp_path / "src" / "module.py").write_text("x=1\n")
        (tmp_path / "tests" / "test_module.py").parent.mkdir(parents=True)
        (tmp_path / "tests" / "test_module.py").write_text("def test_x(): pass\n")

        with patch(
            "harness.analysis.assessment.assess",
            return_value=_mock_assessment_report(),
        ):
            result = analyse(tmp_path, deep=True)

        assert result["status"] == "ok"
        assert "arch-conformance" in result["scans"]
        assert "coverage" in result["scans"]
        assert "dead-code" in result["scans"]

    def test_deep_with_llm_fallback(self, tmp_path):
        """Deep analysis gracefully degrades when LLM assessment fails."""
        from harness.analysis.observer import analyse
        (tmp_path / "hello.py").write_text("x=1\n")

        with patch(
            "harness.analysis.assessment.assess",
            side_effect=RuntimeError("API unavailable"),
        ):
            result = analyse(tmp_path, deep=True)

        assert result["status"] == "ok"
        # Graceful degradation: fallback text appears in report
        assert result["report"] != ""
        assert "Assessment agents unavailable" in result["report"]

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


# ── Tests for analyse_async() ──────────────────────────────────────────────


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
        """Deep async analysis runs additional scans (LLM assessment mocked)."""
        from harness.analysis.observer import analyse_async
        (tmp_path / "src" / "module.py").parent.mkdir(parents=True)
        (tmp_path / "src" / "module.py").write_text("x=1\n")
        (tmp_path / "tests" / "test_module.py").parent.mkdir(parents=True)
        (tmp_path / "tests" / "test_module.py").write_text("def test_x(): pass\n")

        with patch(
            "harness.analysis.assessment.assess",
            return_value=_mock_assessment_report(),
        ):
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

    @pytest.mark.asyncio
    async def test_deep_async_llm_fallback(self, tmp_path):
        """Async deep analysis gracefully degrades when LLM fails (lines 186-188)."""
        from harness.analysis.observer import analyse_async
        (tmp_path / "hello.py").write_text("x=1\n")

        with patch(
            "harness.analysis.assessment.assess",
            side_effect=RuntimeError("API unavailable"),
        ):
            result = await analyse_async(tmp_path, deep=True)

        assert result["status"] == "ok"
        assert "Assessment agents unavailable" in result["report"]
