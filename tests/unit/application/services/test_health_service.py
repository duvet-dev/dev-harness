"""Tests for ``harness.application.services.health_service``."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from harness.application.services.health_service import HealthService
from harness.domain.health import HealthCheck, HealthReport, _result


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_git_checker():
    checker = MagicMock()
    checker.check_branch_match.return_value = _result("branch-match", "pass", "OK")
    checker.check_git_clean.return_value = _result("git-clean", "pass", "OK")
    checker.fix_branch_match.return_value = ["Branch fixed"]
    checker.fix_git_state.return_value = ["Git state fixed"]
    return checker


@pytest.fixture
def mock_config_validator():
    checker = MagicMock()
    checker.check_providers_yaml.return_value = _result("providers-yaml", "pass", "OK")
    checker.check_api_keys.return_value = _result("api-keys", "pass", "OK")
    return checker


@pytest.fixture
def mock_engagement_checker():
    checker = MagicMock()
    checker.check_engagement_fresh.return_value = _result("engagement-fresh", "pass", "OK")
    checker.check_plan_consistency.return_value = _result("plan-consistency", "pass", "OK")
    checker.check_manifest_link.return_value = _result("manifest-link", "pass", "OK")
    checker.fix_missing_dir.return_value = ["Missing dir fixed"]
    checker.fix_plan_consistency.return_value = ["Plan fixed"]
    checker.fix_engagement.return_value = ["Engagement fixed"]
    return checker


@pytest.fixture
def service(mock_git_checker, mock_config_validator, mock_engagement_checker):
    return HealthService(mock_git_checker, mock_config_validator, mock_engagement_checker)


# ── Simple checks ──────────────────────────────────────────────────────────


class TestCheckHarnessDir:
    """Verify harness dir check."""

    def test_missing_harness_dir(self, service, tmp_path):
        result = service.check_harness_dir(tmp_path)
        assert result.name == "harness-dir"
        assert result.status == "fail"
        assert result.severity == "CRITICAL"

    def test_missing_required_files(self, service, tmp_path):
        (tmp_path / ".harness").mkdir(parents=True)
        result = service.check_harness_dir(tmp_path)
        assert result.status == "fail"
        assert "missing" in result.message.lower()

    def test_complete_structure(self, service, tmp_path):
        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir(parents=True)
        (harness_dir / "config.yaml").write_text("")
        (harness_dir / "active-engagements.yaml").write_text("")
        (harness_dir / "engagements").mkdir()
        result = service.check_harness_dir(tmp_path)
        assert result.status == "pass"


class TestCheckAgentRoles:
    """Verify agent roles check."""

    def test_no_fleets_file(self, service, tmp_path):
        result = service.check_agent_roles(tmp_path)
        assert result.name == "agent-roles"
        assert result.status == "pass"

    def test_fleets_with_agents_by_dict(self, service, tmp_path):
        fleet_dir = tmp_path / ".harness"
        fleet_dir.mkdir(parents=True)
        (fleet_dir / "fleets.yaml").write_text(
            "fleet1:\n  agents:\n    - name: nonexistent-role\n"
        )
        result = service.check_agent_roles(tmp_path)
        # 'nonexistent-role' is not in agent registry, so warning
        assert result.status == "warn"
        assert "nonexistent-role" in result.message

    def test_fleets_with_agents_by_str(self, service, tmp_path):
        fleet_dir = tmp_path / ".harness"
        fleet_dir.mkdir(parents=True)
        (fleet_dir / "fleets.yaml").write_text(
            "fleet1:\n  agents:\n    - missing-role\n"
        )
        result = service.check_agent_roles(tmp_path)
        assert result.status == "warn"
        assert "missing-role" in result.message

    def test_exception_handling(self, service, monkeypatch):
        import builtins
        original = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == "harness.agents.agent_registry":
                raise ImportError("No module named 'harness.agents.agent_registry'")
            return original(name, *args, **kwargs)
        monkeypatch.setattr(builtins, "__import__", mock_import)
        result = service.check_agent_roles(Path("/tmp"))
        assert result.status == "warn"


class TestCheckPythonVersion:
    """Verify python version check."""

    def test_current_version_passes(self, service, tmp_path):
        result = service.check_python_version(tmp_path)
        assert result.name == "python-version"
        assert result.status == "pass"

    def test_accepts_any_root(self, service):
        result = service.check_python_version(Path("/tmp"))
        assert result.status == "pass"


# ── Orchestration ──────────────────────────────────────────────────────────


class TestRunAllChecks:
    """Verify run_all_checks orchestration."""

    def test_runs_all_checkers(self, service, tmp_path, mock_git_checker, mock_config_validator, mock_engagement_checker):
        report = service.run_all_checks(tmp_path)
        assert isinstance(report, HealthReport)
        assert len(report.checks) == 10  # all 10 checks
        mock_config_validator.check_providers_yaml.assert_called_once()
        mock_config_validator.check_api_keys.assert_called_once()
        mock_git_checker.check_branch_match.assert_called_once()
        mock_git_checker.check_git_clean.assert_called_once()
        mock_engagement_checker.check_engagement_fresh.assert_called_once()
        mock_engagement_checker.check_plan_consistency.assert_called_once()
        mock_engagement_checker.check_manifest_link.assert_called_once()

    def test_builds_summary(self, service, tmp_path):
        report = service.run_all_checks(tmp_path)
        assert "passed" in report.summary.lower()
        assert len(report.summary) > 0

    def test_failure_summary(self, service, mock_config_validator, mock_engagement_checker):
        """When all checks fail, summary shows failures."""
        mock_config_validator.check_providers_yaml.return_value = _result("p", "fail", "F", severity="CRITICAL")
        mock_config_validator.check_api_keys.return_value = _result("a", "fail", "F", severity="CRITICAL")
        mock_engagement_checker.check_engagement_fresh.return_value = _result("e", "fail", "F", severity="CRITICAL")
        report = service.run_all_checks(Path("/tmp"))
        assert "failures" in report.summary.lower()


class TestRunFixes:
    """Verify run_fixes orchestration."""

    def test_runs_all_fixes(self, service, mock_git_checker, mock_engagement_checker):
        messages = service.run_fixes(Path("/tmp"))
        assert len(messages) > 0
        mock_engagement_checker.fix_missing_dir.assert_called_once()
        mock_engagement_checker.fix_plan_consistency.assert_called_once()
        mock_git_checker.fix_branch_match.assert_called_once()
        mock_git_checker.fix_git_state.assert_called_once()


class TestFormatReport:
    """Verify format_report output."""

    def test_output_contains_status(self, service):
        report = HealthReport(checks=[
            HealthCheck(
                name="test", description="Test",
                status="pass", message="Everything OK",
                severity="CRITICAL",
            ),
        ])
        report.summary = "1 passed"
        output = service.format_report(report)
        assert "Harness Health" in output
        assert "Everything OK" in output
        assert "PASS" in output

    def test_verbose_includes_info(self, service):
        report = HealthReport(checks=[
            HealthCheck(
                name="info-check", description="Info",
                status="pass", message="Info detail",
                severity="INFO",
            ),
        ])
        report.summary = "1 passed"

        quiet = service.format_report(report, verbose=False)
        assert "Info detail" not in quiet

        verbose = service.format_report(report, verbose=True)
        assert "Info detail" in verbose

    def test_fix_suggestion_shown_on_failure(self, service):
        report = HealthReport(checks=[
            HealthCheck(
                name="test", description="Test",
                status="fail", message="Broken",
                severity="CRITICAL", fix="harness init",
            ),
        ])
        report.summary = "1 failure"
        output = service.format_report(report)
        assert "Fix:" in output
        assert "harness init" in output

    def test_no_fix_when_passing(self, service):
        report = HealthReport(checks=[
            HealthCheck(
                name="test", description="Test",
                status="pass", message="OK",
                severity="CRITICAL", fix="harness init",
            ),
        ])
        report.summary = "1 passed"
        output = service.format_report(report, verbose=True)
        assert "✓" in output
        assert "Fix:" not in output

    def test_warn_fix_shown(self, service):
        report = HealthReport(checks=[
            HealthCheck(
                name="test", description="Test",
                status="warn", message="Warning",
                severity="WARN", fix="check config",
            ),
        ])
        report.summary = "1 warning"
        output = service.format_report(report)
        assert "⚠" in output
        assert "Fix:" in output

    def test_empty_report(self, service):
        report = HealthReport()
        output = service.format_report(report)
        assert "PASS" in output

    def test_severity_ordering(self, service):
        report = HealthReport(checks=[
            HealthCheck(name="a", description="", status="pass", message="AAA-INFO", severity="INFO"),
            HealthCheck(name="b", description="", status="pass", message="BBB-CRITICAL", severity="CRITICAL"),
            HealthCheck(name="c", description="", status="pass", message="CCC-WARN", severity="WARN"),
            HealthCheck(name="d", description="", status="pass", message="DDD-BRANCH", severity="BRANCH"),
        ])
        report.summary = "4 passed"
        output = service.format_report(report, verbose=True)
        # CRITICAL should come before BRANCH before WARN before INFO
        b_idx = output.index("BBB")
        d_idx = output.index("DDD")
        c_idx = output.index("CCC")
        a_idx = output.index("AAA")
        assert b_idx < d_idx < c_idx < a_idx


class TestFixEngagement:
    """Verify fix_engagement delegation."""

    def test_delegates_to_engagement_checker(self, service, mock_engagement_checker):
        messages = service.fix_engagement(Path("/tmp"), "test-eng")
        mock_engagement_checker.fix_engagement.assert_called_once_with(Path("/tmp"), "test-eng")
        assert messages == ["Engagement fixed"]

    def test_summary_includes_failures(self, service):
        """Report summary includes failure count when checks fail."""
        report = HealthReport(checks=[
            HealthCheck(name="fail", description="", status="fail",
                        message="Failed check", severity="CRITICAL"),
        ])
        report.summary = "1 failures"
        output = service.format_report(report)
        assert "1 failures" in output
        assert "FAIL" in output or "failures" in output
