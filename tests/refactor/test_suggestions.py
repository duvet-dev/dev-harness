"""Tests for harness.refactor.suggestions."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.refactor.suggestions import (
    DebtSuggestionEngine,
    RefactoringSuggestion,
    generate_suggestions,
)
from harness.refactor.debt import DebtReport, DebtViolation


class TestRefactoringSuggestion:
    def test_defaults(self):
        s = RefactoringSuggestion(title="Test")
        assert s.priority == "medium"
        assert s.effort_hours == 1.0
        assert s.affected_files == []


class TestDebtSuggestionEngine:
    def test_generate_empty_report(self):
        engine = DebtSuggestionEngine()
        report = DebtReport()
        suggestions = engine.generate(report)
        assert suggestions == []

    def test_generate_domain_infrastructure_leak(self):
        engine = DebtSuggestionEngine()
        report = DebtReport(
            violations=[
                DebtViolation(
                    rule_name="domain_infrastructure_leak",
                    severity="error",
                    message="Domain file imports sqlalchemy",
                    file="domain/model.py",
                    line=5,
                )
            ]
        )
        suggestions = engine.generate(report)
        assert len(suggestions) == 1
        assert suggestions[0].priority == "high"
        assert suggestions[0].pattern == "extract-adapter"

    def test_generate_missing_adapter(self):
        engine = DebtSuggestionEngine()
        report = DebtReport(
            violations=[
                DebtViolation(
                    rule_name="missing_adapter",
                    severity="warning",
                    message="Direct use of requests",
                    file="app/service.py",
                    line=10,
                )
            ]
        )
        suggestions = engine.generate(report)
        assert len(suggestions) == 1
        assert suggestions[0].pattern == "wrap-dependency"
        assert suggestions[0].priority == "medium"

    def test_generate_direct_db_access(self):
        engine = DebtSuggestionEngine()
        report = DebtReport(
            violations=[
                DebtViolation(
                    rule_name="direct_db_access",
                    severity="error",
                    message="Direct db access",
                    file="app/repo.py",
                    line=20,
                )
            ]
        )
        suggestions = engine.generate(report)
        assert len(suggestions) == 1
        assert suggestions[0].pattern == "introduce-repository"

    def test_generate_framework_coupling(self):
        engine = DebtSuggestionEngine()
        report = DebtReport(
            violations=[
                DebtViolation(
                    rule_name="framework_coupling_in_domain",
                    severity="warning",
                    message="Domain imports flask",
                    file="domain/web.py",
                    line=3,
                )
            ]
        )
        suggestions = engine.generate(report)
        assert len(suggestions) == 1
        assert suggestions[0].pattern == "move-to-layer"

    def test_generate_circular_dependency(self):
        engine = DebtSuggestionEngine()
        report = DebtReport(
            violations=[
                DebtViolation(
                    rule_name="circular_dependency",
                    severity="error",
                    message="Circular dep",
                    file="mod/a.py",
                )
            ]
        )
        suggestions = engine.generate(report)
        assert len(suggestions) == 1
        assert suggestions[0].pattern == "introduce-interface"

    def test_generate_layer_violation(self):
        engine = DebtSuggestionEngine()
        report = DebtReport(
            violations=[
                DebtViolation(
                    rule_name="layer_violation",
                    severity="warning",
                    message="Layer violation",
                    file="app/violation.py",
                )
            ]
        )
        suggestions = engine.generate(report)
        assert len(suggestions) == 1
        assert suggestions[0].pattern == "move-to-layer"

    def test_generic_unknown_rule(self):
        engine = DebtSuggestionEngine()
        report = DebtReport(
            violations=[
                DebtViolation(
                    rule_name="custom_rule",
                    severity="info",
                    message="Something custom",
                    file="custom.py",
                )
            ]
        )
        suggestions = engine.generate(report)
        assert len(suggestions) == 1
        assert suggestions[0].pattern == "manual-review"

    def test_groups_by_rule_name(self):
        engine = DebtSuggestionEngine()
        report = DebtReport(
            violations=[
                DebtViolation(rule_name="domain_infrastructure_leak", file="a.py"),
                DebtViolation(rule_name="domain_infrastructure_leak", file="b.py"),
                DebtViolation(rule_name="missing_adapter", file="c.py"),
            ]
        )
        suggestions = engine.generate(report)
        assert len(suggestions) == 2

    def test_sorts_by_priority(self):
        engine = DebtSuggestionEngine()
        report = DebtReport(
            violations=[
                DebtViolation(rule_name="missing_adapter", file="a.py"),        # medium
                DebtViolation(rule_name="domain_infrastructure_leak", file="b.py"),  # high
            ]
        )
        suggestions = engine.generate(report)
        assert suggestions[0].priority == "high"
        assert suggestions[1].priority == "medium"

    def test_to_markdown_empty(self):
        engine = DebtSuggestionEngine()
        md = engine.to_markdown([])
        assert "No refactoring suggested" in md

    def test_to_markdown_with_suggestions(self):
        engine = DebtSuggestionEngine()
        suggestions = [
            RefactoringSuggestion(
                title="Fix leak",
                description="Description here",
                affected_files=["a.py"],
                priority="high",
                effort_hours=4.0,
                pattern="extract-adapter",
            )
        ]
        md = engine.to_markdown(suggestions)
        assert "HIGH" in md
        assert "Fix leak" in md
        assert "4.0h" in md or "4h" in md
        assert "extract-adapter" in md

    def test_to_markdown_effort_minutes(self):
        engine = DebtSuggestionEngine()
        suggestions = [
            RefactoringSuggestion(
                title="Small fix",
                effort_hours=0.5,
                rule_name="test",
                pattern="fix",
            )
        ]
        md = engine.to_markdown(suggestions)
        assert "min" in md

    def test_affected_files_deduplication(self):
        engine = DebtSuggestionEngine()
        report = DebtReport(
            violations=[
                DebtViolation(rule_name="domain_infrastructure_leak", file="a.py", line=1),
                DebtViolation(rule_name="domain_infrastructure_leak", file="a.py", line=10),
            ]
        )
        suggestions = engine.generate(report)
        assert len(suggestions[0].affected_files) == 2


class TestGenerateSuggestions:
    def test_skips_when_config_gate_closed(self, tmp_path):
        with patch("harness.refactor.suggestions.allow_refactoring_suggestions", return_value=False):
            result = generate_suggestions(tmp_path)
            assert result == []

    def test_generates_when_gate_open(self, tmp_path):
        with patch("harness.refactor.suggestions.allow_refactoring_suggestions", return_value=True):
            with patch("harness.refactor.suggestions.DebtDetector") as MockDetector:
                mock_detector = MagicMock()
                mock_detector.scan.return_value = DebtReport(violations=[
                    DebtViolation(rule_name="missing_adapter", file="a.py")
                ])
                MockDetector.return_value = mock_detector
                result = generate_suggestions(tmp_path, skip_config_check=False)
                assert len(result) == 1

    def test_accepts_pre_scanned_report(self, tmp_path):
        report = DebtReport(violations=[
            DebtViolation(rule_name="domain_infrastructure_leak", file="d.py")
        ])
        with patch("harness.refactor.suggestions.allow_refactoring_suggestions", return_value=True):
            result = generate_suggestions(tmp_path, debt_report=report)
            assert len(result) == 1

    def test_skip_config_check(self, tmp_path):
        result = generate_suggestions(tmp_path, skip_config_check=True)
        # Should not call allow_refactoring_suggestions
        assert isinstance(result, list)
