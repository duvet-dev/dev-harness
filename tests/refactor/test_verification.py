"""Tests for harness.refactor.verification."""

from pathlib import Path
from unittest.mock import MagicMock, patch
from subprocess import TimeoutExpired

import pytest

from harness.refactor.verification import (
    BoundaryTestCheck,
    RefactoringVerificationResult,
    SummaryEntry,
    TestSuiteResult,
    VerificationRunner,
)


class TestBoundaryTestCheck:
    def test_defaults(self):
        btc = BoundaryTestCheck(path=Path("test.py"))
        assert btc.passed is True
        assert btc.message == ""


class TestTestSuiteResult:
    def test_defaults(self):
        ts = TestSuiteResult()
        assert ts.passed is True
        assert ts.exit_code == 0
        assert ts.output == ""

    def test_with_failure(self):
        ts = TestSuiteResult(passed=False, exit_code=1, failures=2)
        assert ts.passed is False
        assert ts.failures == 2


class TestSummaryEntry:
    def test_defaults(self):
        se = SummaryEntry(description="test")
        assert se.status == "changed"
        assert se.detail == ""


class TestRefactoringVerificationResult:
    def test_defaults(self):
        rvr = RefactoringVerificationResult()
        assert rvr.boundary_tests_passed is True
        assert rvr.debt_delta == 0
        assert rvr.passed is True

    def test_boundary_tests_passed_all_ok(self):
        rvr = RefactoringVerificationResult(
            boundary_checks=[
                BoundaryTestCheck(path=Path("a.py"), passed=True),
                BoundaryTestCheck(path=Path("b.py"), passed=True),
            ]
        )
        assert rvr.boundary_tests_passed is True

    def test_boundary_tests_passed_one_fails(self):
        rvr = RefactoringVerificationResult(
            boundary_checks=[
                BoundaryTestCheck(path=Path("a.py"), passed=True),
                BoundaryTestCheck(path=Path("b.py"), passed=False),
            ]
        )
        assert rvr.boundary_tests_passed is False

    def test_debt_delta_improvement(self):
        from harness.refactor.debt import DebtReport, DebtViolation
        rvr = RefactoringVerificationResult(
            debt_before=DebtReport(violations=[DebtViolation(rule_name="a"), DebtViolation(rule_name="b")]),
            debt_after=DebtReport(violations=[DebtViolation(rule_name="a")]),
        )
        assert rvr.debt_delta == -1

    def test_debt_delta_worsened(self):
        from harness.refactor.debt import DebtReport, DebtViolation
        rvr = RefactoringVerificationResult(
            debt_before=DebtReport(violations=[DebtViolation(rule_name="a")]),
            debt_after=DebtReport(violations=[DebtViolation(rule_name="a"), DebtViolation(rule_name="b")]),
        )
        assert rvr.debt_delta == 1


class TestVerificationRunner:
    def test_run_empty_project(self, tmp_path):
        runner = VerificationRunner(tmp_path, run_tests=False)
        result = runner.run()
        assert result.passed is True
        assert result.boundary_checks == []

    def test_check_boundaries_no_yaml(self, tmp_path):
        runner = VerificationRunner(tmp_path, run_tests=False)
        checks = runner._check_boundaries()
        assert checks == []

    def test_check_boundaries_with_yaml_missing_test(self, tmp_path):
        boundaries_yaml = tmp_path / ".harness" / "boundaries.yaml"
        boundaries_yaml.parent.mkdir(parents=True)
        import yaml
        boundaries_yaml.write_text(yaml.dump({
            "boundaries": [{"name": "test", "test_path": "tests/boundaries/test_missing.py"}]
        }))
        runner = VerificationRunner(tmp_path, run_tests=False)
        with patch("harness.refactor.verification.verify_boundary_test_integrity") as mock_verify:
            mock_verify.return_value = (True, "OK")
            checks = runner._check_boundaries()
            assert len(checks) == 1
            assert checks[0].passed is False
            assert "missing" in checks[0].message

    def test_run_test_suite_success(self, tmp_path):
        runner = VerificationRunner(tmp_path, run_tests=True)
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "3 passed"
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            result = runner._run_test_suite()
            assert result.passed is True
            assert result.tests_run == 3

    def test_run_test_suite_failure(self, tmp_path):
        runner = VerificationRunner(tmp_path, run_tests=True)
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = "2 passed, 1 failed in 0.5s"
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            result = runner._run_test_suite()
            assert result.passed is False
            assert result.failures == 1

    def test_run_test_suite_timeout(self, tmp_path):
        runner = VerificationRunner(tmp_path, run_tests=True)
        with patch("harness.refactor.verification.subprocess.run", side_effect=TimeoutExpired(cmd="pytest", timeout=30)) as mock_run:
            result = runner._run_test_suite()
            assert result.passed is False
            assert "timed out" in result.output

    def test_run_test_suite_not_found(self, tmp_path):
        runner = VerificationRunner(tmp_path, run_tests=True)
        with patch("harness.refactor.verification.subprocess.run", side_effect=FileNotFoundError):
            result = runner._run_test_suite()
            assert result.passed is False
            assert "not found" in result.output

    def test_compute_passed_all_ok(self):
        runner = VerificationRunner(Path("."), run_tests=False)
        result = RefactoringVerificationResult()
        result.boundary_checks = [BoundaryTestCheck(path=Path("a.py"), passed=True)]
        result.test_suite = TestSuiteResult(passed=True, tests_run=5)
        assert runner._compute_passed(result) is True

    def test_compute_passed_boundary_fails(self):
        runner = VerificationRunner(Path("."), run_tests=False)
        result = RefactoringVerificationResult()
        result.boundary_checks = [BoundaryTestCheck(path=Path("a.py"), passed=False)]
        result.test_suite = TestSuiteResult(passed=True)
        assert runner._compute_passed(result) is False

    def test_compute_passed_test_fails(self):
        runner = VerificationRunner(Path("."), run_tests=False)
        result = RefactoringVerificationResult()
        result.boundary_checks = [BoundaryTestCheck(path=Path("a.py"), passed=True)]
        result.test_suite = TestSuiteResult(passed=False)
        assert runner._compute_passed(result) is False

    def test_build_summary_no_boundaries(self, tmp_path):
        runner = VerificationRunner(tmp_path, run_tests=False)
        result = RefactoringVerificationResult()
        summary = runner._build_summary(result)
        assert "No registered boundary tests" in summary

    def test_build_summary_with_checks(self, tmp_path):
        runner = VerificationRunner(tmp_path, run_tests=False)
        result = RefactoringVerificationResult(
            boundary_checks=[
                BoundaryTestCheck(path=tmp_path / "a.py", passed=True),
            ],
            test_suite=TestSuiteResult(passed=True, tests_run=3),
        )
        summary = runner._build_summary(result)
        assert "1/1" in summary
        assert "PASSED" in summary

    def test_build_summary_debt_delta(self, tmp_path):
        from harness.refactor.debt import DebtReport, DebtViolation
        runner = VerificationRunner(tmp_path, run_tests=False)
        result = RefactoringVerificationResult(
            debt_before=DebtReport(violations=[DebtViolation(rule_name="a")]),
            debt_after=DebtReport(violations=[]),
        )
        summary = runner._build_summary(result)
        assert "resolved" in summary
