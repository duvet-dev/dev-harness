"""Verification pass — post-refactoring integrity checks.

Runs after all refactoring waves to verify:
1. Boundary test integrity — hashes unchanged (no unauthorised modifications)
2. Full test suite — all tests pass (no regression)
3. Architecture compliance — scan for remaining debt
4. Summary report — what changed, what was preserved, remaining debt
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from harness.paths import get_boundaries_path
from harness.refactor.boundary_tests import verify_boundary_test_integrity
from harness.refactor.debt import DebtDetector, DebtReport

# ── Data model ─────────────────────────────────────────────────────────────


@dataclass
class BoundaryTestCheck:
    """Result of checking one boundary test file.

    Attributes:
        path: Path to the boundary test file.
        passed: True if the hash matches (no unauthorised modification).
        message: Description of the result.
    """

    path: Path
    passed: bool = True
    message: str = ""


@dataclass
class TestSuiteResult:
    """Result of running the full test suite.

    Attributes:
        passed: True if all tests passed.
        exit_code: Exit code from the test runner.
        output: Raw output from the test runner.
        tests_run: Number of tests that ran.
        failures: Number of test failures.
        errors: Number of test errors.
    """

    passed: bool = True
    exit_code: int = 0
    output: str = ""
    tests_run: int = 0
    failures: int = 0
    errors: int = 0


@dataclass
class SummaryEntry:
    """A single change entry for the summary report.

    Attributes:
        description: What changed or was preserved.
        status: ``changed``, ``preserved``, ``new``, ``removed``.
        detail: Optional additional information.
    """

    description: str
    status: str = "changed"
    detail: str = ""


@dataclass
class RefactoringVerificationResult:
    """Complete verification pass result.

    Attributes:
        boundary_checks: Results of boundary test integrity checks.
        test_suite: Result of running the full test suite.
        debt_before: Debt report from before refactoring (if available).
        debt_after: Debt report from after refactoring.
        summary: Human-readable summary of the verification.
        passed: True if all critical checks passed.
    """

    boundary_checks: list[BoundaryTestCheck] = field(default_factory=list)
    test_suite: Optional[TestSuiteResult] = None
    debt_before: Optional[DebtReport] = None
    debt_after: Optional[DebtReport] = None
    summary: str = ""
    passed: bool = True

    @property
    def boundary_tests_passed(self) -> bool:
        return all(c.passed for c in self.boundary_checks)

    @property
    def debt_delta(self) -> int:
        """Change in total violations (after - before).
        Negative = improvement (debt reduced).
        """
        if self.debt_before is None or self.debt_after is None:
            return 0
        return len(self.debt_after.violations) - len(self.debt_before.violations)


# ── Verification runner ────────────────────────────────────────────────────


class VerificationRunner:
    """Runs the verification pass after refactoring.

    Usage::

        runner = VerificationRunner(project_root)
        result = runner.run()
        if result.passed:
            print("Verification passed!")
        else:
            print(result.summary)
    """

    def __init__(
        self,
        project_root: Path,
        *,
        run_tests: bool = True,
        debt_detector: Optional[DebtDetector] = None,
        debt_before: Optional[DebtReport] = None,
    ) -> None:
        self._root = project_root
        self._run_tests = run_tests
        self._debt_detector = debt_detector or DebtDetector()
        self._debt_before = debt_before

    def run(self) -> RefactoringVerificationResult:
        """Run the full verification pass."""
        result = RefactoringVerificationResult()

        # 1. Boundary test integrity
        result.boundary_checks = self._check_boundaries()

        # 2. Full test suite
        if self._run_tests:
            result.test_suite = self._run_test_suite()

        # 3. Architecture compliance
        result.debt_before = self._debt_before
        result.debt_after = self._debt_detector.scan(self._root)

        # 4. Build summary
        result.passed = self._compute_passed(result)
        result.summary = self._build_summary(result)

        return result

    # ── Boundary checks ─────────────────────────────────────────────────

    def _check_boundaries(self) -> list[BoundaryTestCheck]:
        """Check all registered boundary tests for integrity."""
        checks: list[BoundaryTestCheck] = []

        boundaries_yaml = get_boundaries_path(self._root)
        if not boundaries_yaml.is_file():
            return checks

        import yaml

        with open(boundaries_yaml) as f:
            data = yaml.safe_load(f) or {}

        for entry in data.get("boundaries", []):
            test_path_str = entry.get("test_path", "")
            if not test_path_str:
                continue
            test_path = self._root / test_path_str

            if not test_path.is_file():
                checks.append(
                    BoundaryTestCheck(
                        path=test_path,
                        passed=False,
                        message=f"Boundary test file missing: {test_path}",
                    )
                )
                continue

            passed, message = verify_boundary_test_integrity(test_path)
            checks.append(
                BoundaryTestCheck(
                    path=test_path,
                    passed=passed,
                    message=message,
                )
            )

        return checks

    # ── Test suite ──────────────────────────────────────────────────────

    def _run_test_suite(self) -> TestSuiteResult:
        """Run pytest on the project root."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-x", "-q"],
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=300,
            )

            output = result.stdout + "\n" + result.stderr
            passed = result.returncode == 0

            # Parse test counts from pytest output
            tests_run = 0
            failures = 0
            errors = 0

            # Match pattern like "3 passed, 1 failed"
            import re

            match = re.search(
                r"(\d+)\s+passed.*?(\d+)\s+failed", output
            ) or re.search(r"(\d+)\s+passed", output)
            if match:
                tests_run = int(match.group(1))
            fail_match = re.search(r"(\d+)\s+failed", output)
            if fail_match:
                failures = int(fail_match.group(1))
            error_match = re.search(r"(\d+)\s+error", output)
            if error_match:
                errors = int(error_match.group(1))

            return TestSuiteResult(
                passed=passed,
                exit_code=result.returncode,
                output=output[-2000:],  # Last 2K chars
                tests_run=tests_run,
                failures=failures,
                errors=errors,
            )

        except subprocess.TimeoutExpired:
            return TestSuiteResult(
                passed=False,
                exit_code=-1,
                output="Test suite timed out after 300 seconds.",
            )
        except FileNotFoundError:
            return TestSuiteResult(
                passed=False,
                exit_code=-1,
                output="pytest not found in the project environment.",
            )

    # ── Results ─────────────────────────────────────────────────────────

    def _compute_passed(
        self, result: RefactoringVerificationResult
    ) -> bool:
        """All critical checks must pass."""
        if not result.boundary_tests_passed:
            return False
        if result.test_suite is not None and not result.test_suite.passed:
            return False
        return True

    def _build_summary(
        self, result: RefactoringVerificationResult
    ) -> str:
        """Build a human-readable summary."""
        lines: list[str] = [
            "## Refactoring Verification Summary",
            "",
        ]

        # Boundary tests
        bt_pass = sum(1 for c in result.boundary_checks if c.passed)
        bt_total = len(result.boundary_checks)
        if bt_total > 0:
            lines.append(
                f"**Boundary tests:** {bt_pass}/{bt_total} integrity checks passed"
            )
            for c in result.boundary_checks:
                if c.passed:
                    lines.append(f"  ✅ {c.path.name}")
                else:
                    lines.append(f"  ❌ {c.path.name} — {c.message}")
        else:
            lines.append("**Boundary tests:** No registered boundary tests found.")
        lines.append("")

        # Test suite
        if result.test_suite is not None:
            ts = result.test_suite
            lines.append(
                f"**Test suite:** "
                f"{'✅ Passed' if ts.passed else '❌ Failed'} "
                f"({ts.tests_run} tests, {ts.failures} failures, "
                f"{ts.errors} errors)"
            )
            if not ts.passed:
                lines.append("")
                lines.append("```")
                lines.append(ts.output[-500:])
                lines.append("```")
            lines.append("")

        # Debt delta
        if result.debt_after is not None:
            after_count = len(result.debt_after.violations)
            if result.debt_before is not None:
                before_count = len(result.debt_before.violations)
                delta = after_count - before_count
                if delta < 0:
                    lines.append(
                        f"**Architecture debt:** "
                        f"{before_count} → {after_count} "
                        f"({abs(delta)} resolved) 📉"
                    )
                elif delta > 0:
                    lines.append(
                        f"**Architecture debt:** "
                        f"{before_count} → {after_count} "
                        f"({delta} new) 📈"
                    )
                else:
                    lines.append(
                        f"**Architecture debt:** "
                        f"{after_count} violation(s) (unchanged)"
                    )
            else:
                lines.append(
                    f"**Architecture debt:** "
                    f"{after_count} violation(s) detected"
                )
            lines.append("")

        # Overall
        lines.append(
            f"**Overall: {'✅ PASSED' if result.passed else '❌ FAILED'}"
        )

        return "\n".join(lines)
