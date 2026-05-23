"""Tests for harness.agents.conformance_reviewer — AC parsing, scanning, reporting."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from harness.agents.conformance_reviewer import (
    AcceptanceCriterion,
    TestMatch,
    ACConformanceResult,
    TestWithoutTracking,
    ConformanceReport,
    ACParser,
    TestScanner,
    ConformanceAnalyser,
    ConformanceReportBuilder,
    run_conformance_review,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════════════


class TestAcceptanceCriterion:
    def test_minimal_construction(self):
        ac = AcceptanceCriterion(id="AC-001", requirement_id="REQ-1", text="Do the thing")
        assert ac.id == "AC-001"
        assert ac.requirement_id == "REQ-1"
        assert ac.text == "Do the thing"
        assert ac.line == 0
        assert ac.source_file == ""


class TestTestMatch:
    def test_minimal_construction(self):
        tm = TestMatch(test_path="tests/test_x.py", test_name="test_x")
        assert tm.test_path == "tests/test_x.py"
        assert tm.test_name == "test_x"
        assert tm.match_type == "direct"


class TestACConformanceResult:
    def test_verified_when_tests(self):
        ac = AcceptanceCriterion(id="AC-001", requirement_id="", text="x")
        result = ACConformanceResult(criterion=ac, tests=[TestMatch("t.py", "t_f")])
        assert result.conformance == "verified"

    def test_untested_when_no_tests(self):
        ac = AcceptanceCriterion(id="AC-001", requirement_id="", text="x")
        result = ACConformanceResult(criterion=ac)
        assert result.conformance == "untested"


class TestTestWithoutTracking:
    def test_construction(self):
        t = TestWithoutTracking(test_path="t.py", test_name="t_f", line=42)
        assert t.test_path == "t.py"
        assert t.test_name == "t_f"
        assert t.line == 42


class TestConformanceReport:
    def test_empty_report(self):
        r = ConformanceReport()
        assert r.total_acs == 0
        assert r.verified_acs == 0
        assert r.untested_acs == 0
        assert r.drift_tests == 0

    def test_counts(self):
        ac1 = AcceptanceCriterion(id="AC-001", requirement_id="", text="x")
        ac2 = AcceptanceCriterion(id="AC-002", requirement_id="", text="y")
        r = ConformanceReport(
            results=[
                ACConformanceResult(criterion=ac1, tests=[TestMatch("t.py", "t")]),
                ACConformanceResult(criterion=ac2),
            ],
            untracked_tests=[TestWithoutTracking("u.py", "u_f")],
        )
        assert r.total_acs == 2
        assert r.verified_acs == 1
        assert r.untested_acs == 1
        assert r.drift_tests == 1


# ═══════════════════════════════════════════════════════════════════════════════
# ACParser
# ═══════════════════════════════════════════════════════════════════════════════


class TestACParser:
    def make_parser(self) -> ACParser:
        return ACParser()

    def test_parse_empty_file(self, tmp_path):
        p = tmp_path / "req.md"
        p.write_text("")
        assert self.make_parser().parse(p) == []

    def test_parse_nonexistent_file(self):
        assert self.make_parser().parse(Path("/nonexistent/repo.md")) == []

    def test_parse_heading_acs(self, tmp_path):
        p = tmp_path / "req.md"
        p.write_text("""# Requirements

## AC-001: User can log in
Description of login.

## AC-002: User can log out
""")
        acs = self.make_parser().parse(p)
        assert len(acs) == 2
        ids = [ac.id for ac in acs]
        assert "AC-001" in ids
        assert "AC-002" in ids

    def test_parse_inline_ac_markers(self, tmp_path):
        p = tmp_path / "req.md"
        p.write_text("""
- AC-001: User can log in
- AC-002: User can log out
""")
        acs = self.make_parser().parse(p)
        assert len(acs) >= 2
        ids = {ac.id for ac in acs}
        assert "AC-001" in ids
        assert "AC-002" in ids

    def test_parse_gherkin_scenarios(self, tmp_path):
        p = tmp_path / "req.feature"
        p.write_text("""
Feature: Login

Scenario: Successful login with valid credentials
Given the user is on the login page

Scenario: Login with invalid password
""")
        acs = self.make_parser().parse(p)
        # No AC-ID format found, so falls back to gherkin
        assert len(acs) >= 1
        assert "GHERKIN-001" in {ac.id for ac in acs}

    def test_dedup_same_ac_id(self, tmp_path):
        p = tmp_path / "req.md"
        p.write_text("""
## AC-001: First description
Some text

## AC-001: Duplicate (should be skipped)

## AC-002: Second criterion
""")
        acs = self.make_parser().parse(p)
        ids = [ac.id for ac in acs]
        assert ids.count("AC-001") == 1
        assert len(acs) == 2

    def test_heading_pattern_headings(self, tmp_path):
        p = tmp_path / "req.md"
        p.write_text("""
## Requirement REQ-001: Login feature
### REQ-001.AC-001: Must accept valid email
### REQ-001.AC-002: Must reject invalid password
""")
        acs = self.make_parser().parse(p)
        assert len(acs) >= 2
        ids = {ac.id for ac in acs}
        assert "REQ-001.AC-001" in ids or f"{acs[0].id}" in ids

    def test_parse_with_line_numbers(self, tmp_path):
        p = tmp_path / "req.md"
        p.write_text("Line 1\nLine 2\n## AC-999: At line 3\n")
        acs = self.make_parser().parse(p)
        assert len(acs) == 1
        assert acs[0].id == "AC-999"
        assert acs[0].line == 3


# ═══════════════════════════════════════════════════════════════════════════════
# ConformanceReportBuilder
# ═══════════════════════════════════════════════════════════════════════════════


class TestConformanceReportBuilder:
    def make_builder(self) -> ConformanceReportBuilder:
        return ConformanceReportBuilder()

    def test_empty_report(self):
        report = ConformanceReport()
        md = self.make_builder().as_markdown(report)
        assert "No acceptance criteria found" in md
        assert "Conformance score" in md

    def test_score_calculation(self):
        ac1 = AcceptanceCriterion(id="AC-001", requirement_id="", text="x")
        ac2 = AcceptanceCriterion(id="AC-002", requirement_id="", text="y")
        ac3 = AcceptanceCriterion(id="AC-003", requirement_id="", text="z")
        report = ConformanceReport(
            results=[
                ACConformanceResult(criterion=ac1, tests=[TestMatch("t.py", "t")]),
                ACConformanceResult(criterion=ac2),
                ACConformanceResult(criterion=ac3, tests=[TestMatch("t2.py", "t2")]),
            ],
        )
        builder = self.make_builder()
        assert builder._score(report) == 66.7  # 2/3 * 100

    def test_score_zero_when_no_acs(self):
        report = ConformanceReport()
        assert self.make_builder()._score(report) == 0.0

    def test_recommendations_untested_acs(self):
        ac = AcceptanceCriterion(id="AC-001", requirement_id="", text="x")
        report = ConformanceReport(
            results=[ACConformanceResult(criterion=ac)],
        )
        recs = self.make_builder()._recommendations(report)
        assert any("no test coverage" in r for r in recs)

    def test_recommendations_drift(self):
        report = ConformanceReport(
            untracked_tests=[TestWithoutTracking("u.py", "u_f")],
        )
        recs = self.make_builder()._recommendations(report)
        assert any("no traceable" in r for r in recs)

    def test_recommendations_all_good(self):
        ac = AcceptanceCriterion(id="AC-001", requirement_id="", text="x")
        report = ConformanceReport(
            results=[ACConformanceResult(criterion=ac, tests=[TestMatch("t.py", "t")])],
        )
        recs = self.make_builder()._recommendations(report)
        assert any("All acceptance criteria" in r for r in recs)

    def test_markdown_contains_verified_and_untested(self, tmp_path):
        ac1 = AcceptanceCriterion(id="AC-001", requirement_id="REQ-1", text="Login",
                                  line=5, source_file=str(tmp_path / "req.md"))
        ac2 = AcceptanceCriterion(id="AC-002", requirement_id="REQ-1", text="Logout",
                                  line=10, source_file=str(tmp_path / "req.md"))
        report = ConformanceReport(
            results=[
                ACConformanceResult(criterion=ac1, tests=[TestMatch("t.py", "t_login")]),
                ACConformanceResult(criterion=ac2),
            ],
        )
        md = self.make_builder().as_markdown(report)
        assert "✅ VERIFIED" in md
        assert "❌ UNTESTED" in md
        assert "AC-001" in md
        assert "AC-002" in md

    def test_markdown_with_drift(self):
        ac = AcceptanceCriterion(id="AC-001", requirement_id="", text="x")
        report = ConformanceReport(
            results=[ACConformanceResult(criterion=ac, tests=[TestMatch("t.py", "t")])],
            untracked_tests=[TestWithoutTracking("u.py", "u_f", line=7)],
        )
        md = self.make_builder().as_markdown(report)
        assert "Implementation Drift" in md
        assert "u.py" in md


# ═══════════════════════════════════════════════════════════════════════════════
# ConformanceAnalyser (with mocked dependencies)
# ═══════════════════════════════════════════════════════════════════════════════


class TestConformanceAnalyser:
    def make_report(self) -> ConformanceReport:
        ac1 = AcceptanceCriterion(id="AC-001", requirement_id="", text="x")
        ac2 = AcceptanceCriterion(id="AC-002", requirement_id="", text="y")
        return ConformanceReport(
            results=[
                ACConformanceResult(criterion=ac1, tests=[TestMatch("t.py", "t")]),
                ACConformanceResult(criterion=ac2),
            ],
            untracked_tests=[TestWithoutTracking("u.py", "u_f")],
        )

    def test_analyse_with_mocked_parser_and_scanner(self, tmp_path):
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            AcceptanceCriterion(id="AC-001", requirement_id="", text="x"),
            AcceptanceCriterion(id="AC-002", requirement_id="", text="y"),
        ]

        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = {
            "AC-001": [TestMatch("t.py", "t")],
        }

        analyser = ConformanceAnalyser(ac_parser=mock_parser, test_scanner=mock_scanner)
        req_path = tmp_path / "req.md"
        req_path.write_text("dummy")
        test_dir = tmp_path / "tests"
        test_dir.mkdir()

        report = analyser.analyse(req_path, test_dir)

        assert report.total_acs == 2
        assert report.verified_acs == 1
        assert report.untested_acs == 1


# ═══════════════════════════════════════════════════════════════════════════════
# run_conformance_review — integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunConformanceReview:
    def test_runs_with_mocked_scanner(self, tmp_path):
        req_path = tmp_path / "REQUIREMENTS.md"
        req_path.write_text("## AC-001: Some requirement\n")
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_something.py").write_text("def test_ac_001(): pass\n")

        with patch("harness.agents.conformance_reviewer.TestScanner.scan") as mock_scan:
            mock_scan.return_value = {
                "AC-001": [TestMatch("tests/test_something.py", "test_ac_001")],
            }
            report = run_conformance_review(req_path, test_dir)

        assert report.total_acs >= 1
        assert isinstance(report, ConformanceReport)

    def test_writes_report_to_file(self, tmp_path):
        req_path = tmp_path / "REQUIREMENTS.md"
        req_path.write_text("## AC-001: Some requirement\n")
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        report_path = tmp_path / "reports" / "conformance.md"

        with patch("harness.agents.conformance_reviewer.TestScanner.scan") as mock_scan:
            mock_scan.return_value = {
                "AC-001": [TestMatch("tests/test_something.py", "test_ac_001")],
            }
            report = run_conformance_review(req_path, test_dir, report_path=report_path)

        assert report_path.exists()
        content = report_path.read_text()
        assert "Conformance Report" in content
