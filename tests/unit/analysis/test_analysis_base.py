"""Tests for harness.analysis.base — shared types for analysis results.

Tests Finding validation, ScanResult properties and merge behaviour.
"""

from __future__ import annotations

import pytest

from harness.analysis.base import Finding, ScanResult, VALID_SEVERITIES, VALID_CATEGORIES


class TestFinding:
    """Tests for the Finding dataclass."""

    def test_default_values(self):
        """Finding creates with sensible defaults."""
        f = Finding()
        assert f.severity == "info"
        assert f.category == "structure"
        assert f.message == ""
        assert f.file == ""
        assert f.line is None
        assert f.details is None

    def test_valid_severities(self):
        """All valid severities are accepted."""
        for sev in VALID_SEVERITIES:
            f = Finding(severity=sev)
            assert f.severity == sev

    def test_valid_categories(self):
        """All valid categories are accepted."""
        for cat in VALID_CATEGORIES:
            f = Finding(category=cat)
            assert f.category == cat

    def test_invalid_severity_raises(self):
        """Invalid severity raises ValueError."""
        with pytest.raises(ValueError, match="Invalid severity"):
            Finding(severity="critical")

    def test_invalid_category_raises(self):
        """Invalid category raises ValueError."""
        with pytest.raises(ValueError, match="Invalid category"):
            Finding(category="invalid_category")

    def test_all_fields(self):
        """Finding stores all fields correctly."""
        f = Finding(
            severity="error",
            category="dead_code",
            message="Found dead code",
            file="src/main.py",
            line=42,
            details={"module": "main"},
        )
        assert f.severity == "error"
        assert f.category == "dead_code"
        assert f.message == "Found dead code"
        assert f.file == "src/main.py"
        assert f.line == 42
        assert f.details == {"module": "main"}


class TestScanResult:
    """Tests for the ScanResult dataclass."""

    def test_default_values(self):
        """ScanResult creates with sensible defaults."""
        r = ScanResult()
        assert r.scan_name == ""
        assert r.findings == []
        assert r.metrics == {}
        assert r.summary == ""

    def test_error_count(self):
        """error_count returns count of error-severity findings."""
        r = ScanResult(findings=[
            Finding(severity="error"),
            Finding(severity="error"),
            Finding(severity="warning"),
        ])
        assert r.error_count == 2

    def test_warning_count(self):
        """warning_count returns count of warning-severity findings."""
        r = ScanResult(findings=[
            Finding(severity="warning"),
            Finding(severity="warning"),
            Finding(severity="info"),
        ])
        assert r.warning_count == 2

    def test_info_count(self):
        """info_count returns count of info-severity findings."""
        r = ScanResult(findings=[
            Finding(severity="info"),
            Finding(severity="info"),
            Finding(severity="error"),
        ])
        assert r.info_count == 2

    def test_empty_counts_zero(self):
        """Counts are zero when there are no findings."""
        r = ScanResult()
        assert r.error_count == 0
        assert r.warning_count == 0
        assert r.info_count == 0

    def test_merge(self):
        """merge() combines two scan results."""
        r1 = ScanResult(
            scan_name="scan1",
            findings=[Finding(severity="info", message="a")],
            metrics={"m1": 1},
        )
        r2 = ScanResult(
            scan_name="scan2",
            findings=[Finding(severity="warning", message="b")],
            metrics={"m2": 2},
        )
        merged = r1.merge(r2)

        # r1 is mutated in-place
        assert len(merged.findings) == 2
        assert merged.findings[0].message == "a"
        assert merged.findings[1].message == "b"
        assert merged.metrics == {"m1": 1, "m2": 2}
        # r2 metrics overwrite r1 metrics on key collision


class TestConstants:
    """Tests for module-level constants."""

    def test_valid_severities_has_expected(self):
        assert "info" in VALID_SEVERITIES
        assert "warning" in VALID_SEVERITIES
        assert "error" in VALID_SEVERITIES

    def test_valid_categories_has_expected(self):
        essential = {"structure", "coverage", "dead_code", "architecture", "code_quality"}
        assert essential.issubset(set(VALID_CATEGORIES))
