"""Tests for ``harness.health`` — configuration validation system."""

from pathlib import Path
from harness.health import (
    HealthCheck,
    HealthReport,
    format_health_report,
)


class TestHealthCheck:
    """Verify HealthCheck dataclass behaviour."""

    def test_default_severity(self):
        hc = HealthCheck(
            name="test",
            description="A test check",
            status="pass",
            message="All good",
        )
        assert hc.severity == "WARN"
        assert hc.fix is None

    def test_full_initialization(self):
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


class TestHealthReport:
    """Verify HealthReport aggregation and counts."""

    def test_all_pass(self):
        report = HealthReport(checks=[
            HealthCheck(name="a", description="", status="pass", message="ok"),
            HealthCheck(name="b", description="", status="pass", message="ok"),
        ])
        assert report.status == "pass"
        assert report.pass_count() == 2
        assert report.warn_count() == 0
        assert report.fail_count() == 0

    def test_mixed_status(self):
        report = HealthReport(checks=[
            HealthCheck(name="a", description="", status="pass", message="ok"),
            HealthCheck(name="b", description="", status="warn", message="warning"),
            HealthCheck(name="c", description="", status="fail", message="failed"),
        ])
        assert report.status == "fail"  # any fail = fail
        assert report.pass_count() == 1
        assert report.warn_count() == 1
        assert report.fail_count() == 1

    def test_warn_only(self):
        report = HealthReport(checks=[
            HealthCheck(name="a", description="", status="pass", message="ok"),
            HealthCheck(name="b", description="", status="warn", message="warning"),
        ])
        assert report.status == "warn"  # no fail, some warn = warn

    def test_summary_all_pass(self):
        report = HealthReport(checks=[
            HealthCheck(name="a", description="", status="pass", message="ok"),
        ])
        report.summary = "All checks passed"
        assert report.summary == "All checks passed"


class TestFormatHealthReport:
    """Verify health report output formatting."""

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

        # Without verbose — INFO should be hidden
        quiet = format_health_report(report, verbose=False)
        assert "Info detail" not in quiet

        # With verbose — INFO should appear
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
