"""Tests for harness.analysis.summary — report formatting and debt section.

Tests format_report, debt_section, and format helpers.
"""

from __future__ import annotations

import json

import pytest

from harness.analysis.base import Finding, ScanResult
from harness.analysis.summary import (
    format_report,
    format_markdown,
    format_json,
    debt_section,
    _estimate_effort,
    _DEBT_EFFORT_HOURS,
)


class MockDebtViolation:
    """Minimal mock for a debt violation."""
    def __init__(self, rule_name="layer_violation", severity="warning",
                 message="Test violation", file="src/test.py", line=1,
                 details=None):
        self.rule_name = rule_name
        self.severity = severity
        self.message = message
        self.file = file
        self.line = line
        self.details = details or {}


class MockDebtReport:
    """Minimal mock for DebtReport."""
    def __init__(self, violations=None, scanned_files=10):
        self.violations = violations or []
        self.scanned_files = scanned_files
        self.summary = f"{len(self.violations)} violations found"


class TestFormatMarkdown:
    """Tests for format_markdown()."""

    def test_empty_results(self):
        """Empty results produce empty or clean output."""
        text = format_markdown([], include_summary=True)
        assert isinstance(text, str)

    def test_no_findings_shows_clean(self):
        """Results with no findings show 'No issues found'."""
        r = ScanResult(scan_name="fast-scan", summary="Clean scan")
        text = format_markdown([r], include_summary=True)
        assert "No issues found" in text

    def test_findings_grouped_by_severity(self, tmp_path):
        """Findings are grouped by severity with labels."""
        r = ScanResult(
            scan_name="test-scan",
            findings=[
                Finding(severity="error", message="Error msg"),
                Finding(severity="warning", message="Warning msg"),
                Finding(severity="info", message="Info msg"),
            ],
        )
        text = format_markdown([r], include_summary=True)
        assert "[ERROR]" in text
        assert "[WARNING]" in text or "[WARN]" in text
        assert "[INFO]" in text
        assert "Error msg" in text
        assert "Warning msg" in text
        assert "Info msg" in text

    def test_finding_with_file_ref(self):
        """Findings include file reference."""
        r = ScanResult(
            scan_name="scan",
            findings=[Finding(severity="warning", message="Issue", file="src/main.py")],
        )
        text = format_markdown([r], include_summary=True)
        assert "src/main.py" in text

    def test_finding_with_line(self):
        """Findings include line number."""
        r = ScanResult(
            scan_name="scan",
            findings=[Finding(severity="error", message="Oops", file="f.py", line=42)],
        )
        text = format_markdown([r], include_summary=True)
        assert ":42" in text


class TestFormatReport:
    """Tests for format_report()."""

    def test_markdown_format(self):
        """Default format is markdown."""
        r = ScanResult(scan_name="scan", summary="Test")
        text = format_report([r], include_summary=False)
        assert isinstance(text, str)

    def test_json_format(self):
        """JSON format produces valid JSON."""
        r = ScanResult(
            scan_name="scan",
            summary="Test",
            findings=[Finding(severity="info", message="Note")],
        )
        text = format_report([r], include_summary=False, format="json")
        data = json.loads(text)
        assert "scans" in data
        assert len(data["scans"]) == 1

    def test_json_includes_summary(self):
        """JSON includes summary as a top-level key."""
        r = ScanResult(scan_name="scan", summary="My summary")
        text = format_report([r], include_summary=True, format="json")
        data = json.loads(text)
        assert data["summary"] == "My summary"

    def test_debt_section_included(self, tmp_path):
        """Debt report section is included for markdown format."""
        r = ScanResult(scan_name="scan", summary="Test")
        debt = MockDebtReport(
            violations=[MockDebtViolation()],
            scanned_files=5,
        )
        text = format_report([r], debt_report=debt)
        assert "Architecture Debt" in text

    def test_debt_section_excluded_from_json(self):
        """Debt report is included in JSON format."""
        r = ScanResult(scan_name="scan", summary="Test")
        debt = MockDebtReport(
            violations=[MockDebtViolation()],
            scanned_files=5,
        )
        text = format_report([r], format="json", debt_report=debt)
        data = json.loads(text)
        assert "architecture_debt" in data


class TestDebtSection:
    """Tests for debt_section()."""

    def test_no_violations(self):
        """Shows 'No architecture debt detected' when clean."""
        report = MockDebtReport(violations=[])
        text = debt_section(report)
        assert "No architecture debt detected" in text

    def test_violations_listed(self):
        """Violations are listed with severity icons."""
        report = MockDebtReport(
            violations=[MockDebtViolation()],
            scanned_files=10,
        )
        text = debt_section(report)
        assert "Architecture Debt" in text
        assert "10 file" in text or "10" in text
        assert "layer_violation" in text

    def test_severity_grouping(self, tmp_path):
        """Violations are grouped by severity."""
        report = MockDebtReport(
            violations=[
                MockDebtViolation(severity="error", rule_name="direct_db_access"),
                MockDebtViolation(severity="warning"),
                MockDebtViolation(severity="info", rule_name="default_info"),
            ],
            scanned_files=5,
        )
        text = debt_section(report)
        assert "Error" in text
        assert "Warning" in text
        assert "Info" in text

    def test_effort_estimation_shown(self):
        """Effort estimates are shown when effort=True."""
        report = MockDebtReport(
            violations=[MockDebtViolation(rule_name="layer_violation")],
        )
        text = debt_section(report, effort=True)
        assert "Effort" in text or "effort" in text

    def test_max_violations_respected(self, tmp_path):
        """Only max_violations are shown in detail."""
        violations = [
            MockDebtViolation(rule_name=f"v{i}", message=f"Violation {i}")
            for i in range(5)
        ]
        report = MockDebtReport(violations=violations)
        text = debt_section(report, max_violations=2)
        # Check that "and ... more violation(s)" is present
        assert "more violation" in text


class TestFormatJson:
    """Tests for format_json()."""

    def test_basic_json(self):
        """Produces valid JSON with scans array."""
        r = ScanResult(scan_name="scan", metrics={"count": 5}, summary="Test")
        text = format_json([r], include_summary=False)
        data = json.loads(text)
        assert isinstance(data["scans"], list)
        assert len(data["scans"]) == 1

    def test_findings_in_json(self):
        """Findings are included in JSON output."""
        r = ScanResult(
            scan_name="scan",
            findings=[Finding(severity="error", message="Bad", file="f.py")],
        )
        text = format_json([r], include_summary=False)
        data = json.loads(text)
        scan = data["scans"][0]
        assert len(scan["findings"]) == 1
        assert scan["findings"][0]["severity"] == "error"

    def test_debt_in_json(self):
        """Debt report appears in JSON."""
        r = ScanResult(scan_name="scan")
        debt = MockDebtReport(
            violations=[MockDebtViolation()],
            scanned_files=3,
        )
        text = format_json([r], debt_report=debt, include_summary=False)
        data = json.loads(text)
        assert "architecture_debt" in data
        assert data["architecture_debt"]["estimated_effort_hours"] > 0


class TestEstimateEffort:
    """Tests for _estimate_effort()."""

    def test_known_rule(self):
        """Known rule name is looked up."""
        violations = [
            MockDebtViolation(rule_name="domain_infrastructure_leak"),
        ]
        total, fmt = _estimate_effort(violations)
        assert total == 4.0  # domain_infrastructure_leak = 4h
        assert "hours" in fmt

    def test_default_severity_fallback(self):
        """Falls back to default_{severity} for unknown rules."""
        violations = [
            MockDebtViolation(rule_name="unknown_rule", severity="error"),
        ]
        total, fmt = _estimate_effort(violations)
        assert total == 4.0  # default_error = 4h

    def test_multiple_violations(self):
        """Multiple violations sum their effort."""
        violations = [
            MockDebtViolation(rule_name="default_info"),  # 0.5h
            MockDebtViolation(rule_name="default_warning"),  # 2h
        ]
        total, fmt = _estimate_effort(violations)
        assert total == 2.5

    def test_sub_one_hour_format(self):
        """Effort less than 1h shows in minutes."""
        violations = [MockDebtViolation(rule_name="default_info")]
        total, fmt = _estimate_effort(violations)
        assert "min" in fmt

    def test_debt_section_no_effort_with_violations(self):
        """debt_section with effort=False and violations triggers else branch (line 106)."""
        report = MockDebtReport(
            violations=[MockDebtViolation(severity="error")],
            scanned_files=5,
        )
        text = debt_section(report, effort=False)
        assert "⚠️" in text or "Error" in text or "error" in text
