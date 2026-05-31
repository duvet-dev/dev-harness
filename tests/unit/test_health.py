"""Tests for ``harness.health`` — thin wrapper delegation."""

from pathlib import Path
from unittest.mock import patch

from unittest.mock import MagicMock

import pytest

from harness.health import (
    HealthCheck,
    HealthReport,
    format_health_report,
    run_health_checks,
    run_fixes,
)


class TestReExports:
    """Verify HealthCheck and HealthReport are re-exported from domain."""

    def test_health_check_constructable(self):
        hc = HealthCheck(
            name="test",
            description="A test check",
            status="pass",
            message="All good",
        )
        assert hc.severity == "WARN"
        assert hc.fix is None

    def test_health_check_full_init(self):
        hc = HealthCheck(
            name="test",
            description="A test check",
            status="fail",
            message="Something broke",
            severity="CRITICAL",
            fix="harness init",
        )
        assert hc.name == "test"
        assert hc.status == "fail"
        assert hc.severity == "CRITICAL"
        assert hc.fix == "harness init"

    def test_health_report_aggregation(self):
        report = HealthReport(checks=[
            HealthCheck(name="a", description="", status="pass", message="ok"),
            HealthCheck(name="b", description="", status="warn", message="warning"),
            HealthCheck(name="c", description="", status="fail", message="failed"),
        ])
        assert report.status == "fail"
        assert report.pass_count() == 1
        assert report.warn_count() == 1
        assert report.fail_count() == 1


class TestFormatHealthReport:
    """Verify format_health_report wrapper delegates correctly."""

    def test_output_contains_status(self):
        report = HealthReport(checks=[
            HealthCheck(
                name="test", description="Test",
                status="pass", message="Everything OK",
                severity="CRITICAL",
            ),
        ])
        report.summary = "1 passed"
        output = format_health_report(report)
        assert "Harness Health" in output
        assert "Everything OK" in output
        assert "PASS" in output

    def test_verbose_includes_info(self):
        report = HealthReport(checks=[
            HealthCheck(
                name="info-check", description="Info",
                status="pass", message="Info detail",
                severity="INFO",
            ),
        ])
        report.summary = "1 passed"

        quiet = format_health_report(report, verbose=False)
        assert "Info detail" not in quiet

        verbose = format_health_report(report, verbose=True)
        assert "Info detail" in verbose

    def test_fix_suggestion_shown_on_failure(self):
        report = HealthReport(checks=[
            HealthCheck(
                name="test", description="Test",
                status="fail", message="Broken",
                severity="CRITICAL", fix="harness init",
            ),
        ])
        report.summary = "1 failure"
        output = format_health_report(report)
        assert "Fix:" in output
        assert "harness init" in output


class TestRunHealthChecks:
    """Verify run_health_checks wrapper delegates."""

    def test_returns_health_report(self, tmp_path, monkeypatch):
        mock_service = MagicMock()
        mock_report = MagicMock(spec=HealthReport)
        mock_report.checks = []
        mock_service.run_all_checks.return_value = mock_report
        monkeypatch.setattr(
            "harness.health._build_service",
            lambda _: mock_service,
        )
        report = run_health_checks(tmp_path)
        assert isinstance(report, HealthReport) or hasattr(report, "checks")
        mock_service.run_all_checks.assert_called_once_with(tmp_path)


class TestRunFixes:
    """Verify run_fixes wrapper delegates."""

    def test_returns_list(self, tmp_path, monkeypatch):
        mock_service = MagicMock()
        mock_service.run_fixes.return_value = ["Attempting auto-fixes...", ""]
        monkeypatch.setattr(
            "harness.health._build_service",
            lambda _: mock_service,
        )
        messages = run_fixes(tmp_path)
        assert isinstance(messages, list)
        assert len(messages) > 0
