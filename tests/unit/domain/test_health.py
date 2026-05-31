"""Tests for ``harness.domain.health`` — domain model for health checks."""

from harness.domain.health import (
    _CHECK_DESCRIPTIONS,
    _result,
    HealthCheck,
    HealthReport,
)


class TestCheckDescriptions:
    """Verify the check descriptions dictionary."""

    def test_contains_all_checks(self):
        expected = {
            "harness-dir",
            "providers-yaml",
            "api-keys",
            "engagement-fresh",
            "branch-match",
            "git-clean",
            "plan-consistency",
            "agent-roles",
            "manifest-link",
            "python-version",
        }
        assert set(_CHECK_DESCRIPTIONS.keys()) == expected

    def test_descriptions_are_non_empty(self):
        for name, desc in _CHECK_DESCRIPTIONS.items():
            assert desc, f"Description for {name!r} is empty"


class TestResult:
    """Verify the ``_result`` helper creates HealthCheck correctly."""

    def test_with_default_severity(self):
        hc = _result("test-check", "pass", "All good")
        assert isinstance(hc, HealthCheck)
        assert hc.name == "test-check"
        assert hc.status == "pass"
        assert hc.message == "All good"
        assert hc.severity == "WARN"
        assert hc.fix is None
        assert hc.description == _CHECK_DESCRIPTIONS.get("test-check", "test-check")

    def test_with_custom_severity_and_fix(self):
        hc = _result("harness-dir", "fail", "Missing", severity="CRITICAL", fix="harness init")
        assert hc.name == "harness-dir"
        assert hc.status == "fail"
        assert hc.severity == "CRITICAL"
        assert hc.fix == "harness init"
        assert hc.description == _CHECK_DESCRIPTIONS["harness-dir"]

    def test_unknown_check_name_uses_name_as_description(self):
        hc = _result("unknown-check", "pass", "ok")
        assert hc.description == "unknown-check"


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

    def test_all_severity_values_accepted(self):
        for sev in ("CRITICAL", "BRANCH", "WARN", "INFO"):
            hc = HealthCheck(
                name="test", description="", status="pass",
                message="ok", severity=sev,
            )
            assert hc.severity == sev


class TestHealthReport:
    """Verify HealthReport aggregation and counts."""

    def test_empty_report(self):
        report = HealthReport()
        assert report.status == "pass"
        assert report.pass_count() == 0
        assert report.warn_count() == 0
        assert report.fail_count() == 0
        assert report.summary == ""
        assert report.checks == []

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
        assert report.status == "fail"
        assert report.pass_count() == 1
        assert report.warn_count() == 1
        assert report.fail_count() == 1

    def test_warn_only(self):
        report = HealthReport(checks=[
            HealthCheck(name="a", description="", status="pass", message="ok"),
            HealthCheck(name="b", description="", status="warn", message="warning"),
        ])
        assert report.status == "warn"

    def test_fail_takes_priority_over_warn(self):
        report = HealthReport(checks=[
            HealthCheck(name="a", description="", status="fail", message="fail"),
            HealthCheck(name="b", description="", status="warn", message="warn"),
        ])
        assert report.status == "fail"

    def test_summary_set_manually(self):
        report = HealthReport(checks=[
            HealthCheck(name="a", description="", status="pass", message="ok"),
        ])
        report.summary = "All checks passed"
        assert report.summary == "All checks passed"
