"""Tests for HealthDisplay — format health check for user display.

Covers:
- HealthDisplay.format() with passing HealthReport
- HealthDisplay.format() with warnings
- Severity classification
- Action items for common warning types
- Engagement summary display
- Edge cases (empty warnings, missing fields)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pytest

from harness.session.health_display import HealthDisplay


# ── Test data classes ────────────────────────────────────────────────


@dataclass
class _TestWarning:
    """Minimal HealthWarning-like class for testing."""

    type: str
    message: str


@dataclass
class _TestEngagement:
    """Minimal Engagement-like class for testing."""

    status: str = "active"
    current_phase: str | None = "design"
    last_active: datetime | None = None


@dataclass
class _TestHealthReport:
    """Minimal HealthReport-like class for testing."""

    all_ok: bool = True
    warnings: list = field(default_factory=list)
    slug: str = "test-eng"
    engagement: _TestEngagement | None = None


# ── Tests ────────────────────────────────────────────────────────────


class TestHealthDisplay:
    """HealthDisplay — format health check results."""

    def test_format_all_ok(self):
        """All checks pass → shows success message."""
        display = HealthDisplay()
        report = _TestHealthReport(
            all_ok=True,
            slug="test-eng",
        )

        output = display.format(report)

        assert "test-eng" in output
        assert "✓" in output
        assert "All checks passed" in output
        assert "Warning" not in output
        assert "FAIL" not in output

    def test_format_with_warnings(self):
        """Warnings present → shows each warning with severity and action."""
        display = HealthDisplay()
        report = _TestHealthReport(
            all_ok=False,
            slug="warn-eng",
            warnings=[
                _TestWarning(
                    type="dirty_repo",
                    message="Working tree has 3 uncommitted changes",
                ),
                _TestWarning(
                    type="branch_mismatch",
                    message="Expected 'feature-x', found 'main'",
                ),
            ],
        )

        output = display.format(report)

        assert "warn-eng" in output
        assert "✗" in output  # Fail icon for 2 warnings
        assert "2 warning(s)" in output
        assert "dirty_repo" in output
        assert "branch_mismatch" in output
        assert "WARN" in output
        assert "Commit or stash" in output  # Action item for dirty_repo
        assert "Switch to the correct" in output  # Action item for branch_mismatch

    def test_format_corrupt_state(self):
        """Severe warning type → classified as FAIL."""
        display = HealthDisplay()
        report = _TestHealthReport(
            all_ok=False,
            slug="corrupt-eng",
            warnings=[
                _TestWarning(
                    type="corrupt_state",
                    message="Engagement state file is corrupt",
                ),
            ],
        )

        output = display.format(report)

        assert "FAIL" in output
        assert "corrupt_state" in output
        assert "Check the engagement JSON" in output

    def test_format_with_engagement_summary(self):
        """Engagement details included when provided."""
        display = HealthDisplay()
        report = _TestHealthReport(
            all_ok=True,
            slug="sum-eng",
            engagement=_TestEngagement(
                status="active",
                current_phase="build",
                last_active=datetime(2026, 5, 29, 12, 0, 0),
            ),
        )

        output = display.format(report)

        assert "Status:" in output
        assert "active" in output
        assert "Phase:" in output
        assert "build" in output
        assert "Last active:" in output

    def test_format_no_warnings_empty_list(self):
        """Empty warnings list → behaves like all_ok."""
        display = HealthDisplay()
        report = _TestHealthReport(
            all_ok=True,
            slug="no-warn",
            warnings=[],
        )

        output = display.format(report)

        assert "All checks passed" in output
        assert "Warning" not in output

    def test_format_missing_optional_fields(self):
        """Missing optional fields → no crash, graceful handling."""
        display = HealthDisplay()
        report = _TestHealthReport(
            all_ok=True,
            slug="partial",
            engagement=None,
        )

        output = display.format(report)

        assert "Health Report" in output
        assert "partial" in output

    def test_format_empty_report(self):
        """Report with no warnings and no engagement → clean output."""
        display = HealthDisplay()
        report = _TestHealthReport(
            all_ok=True,
            slug="",
            warnings=[],
            engagement=None,
        )

        output = display.format(report)

        assert "Health Report" in output
        assert "All checks passed" in output

    def test_action_items_by_type(self):
        """Each warning type has appropriate action item."""
        display = HealthDisplay()

        tests = [
            ("dirty_repo", "Commit or stash"),
            ("branch_mismatch", "Switch to the correct"),
            ("branch_missing", "Create the target branch"),
            ("corrupt_state", "recreate the engagement"),
            ("stale_engagement", "pausing or aborting"),
            ("unknown_type", "Investigate:"),
        ]

        for wtype, expected in tests:
            action = display._action_item(wtype, f"Test {wtype}")
            assert expected in action, f"Action for '{wtype}' should contain '{expected}'"

    def test_severity_classification(self):
        """Warning types classified into correct severity."""
        display = HealthDisplay()

        assert display._classify_severity("corrupt_state") == "fail"
        assert display._classify_severity("engagement_not_found") == "fail"
        assert display._classify_severity("branch_mismatch") == "warn"
        assert display._classify_severity("dirty_repo") == "warn"
        assert display._classify_severity("no_git_repo") == "info"
        assert display._classify_severity("unknown_type") == "warn"

    def test_footer_present(self):
        """Output contains footer with action suggestions."""
        display = HealthDisplay()
        report = _TestHealthReport(all_ok=True, slug="ft-eng")

        output = display.format(report)

        assert "/status" in output
        assert "/abort" in output
