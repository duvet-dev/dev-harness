"""Tests for domain enum types.

Covers PhaseName validation and all domain enums.
"""

from __future__ import annotations

import pytest

from harness.command.values import (
    AbortMode,
    AutoMode,
    BranchStrategy,
    PhaseName,
    ReviewDecision,
    SessionType,
)
from harness.domain.enums import (
    BackendStatus,
    FeedbackStatus,
    HealthSeverity,
    Severity,
    SnapshotStatus,
    StepStatus,
    StepType,
)


class TestPhaseName:
    """Tests for PhaseName value object."""

    def test_valid_phases(self):
        phases = ["requirements", "design", "implementation", "testing", "review", "deployment", "assessment-triage"]
        for p in phases:
            pn = PhaseName(p)
            assert str(pn) == p

    def test_invalid_phase_raises(self):
        with pytest.raises(ValueError, match="Invalid phase"):
            PhaseName("nonexistent")

    def test_repr(self):
        pn = PhaseName("design")
        assert repr(pn) == "PhaseName('design')"

    def test_equality(self):
        assert PhaseName("design") == PhaseName("design")
        assert PhaseName("design") != PhaseName("testing")

    def test_hashable(self):
        s = {PhaseName("design"), PhaseName("testing")}
        assert len(s) == 2

    def test_equality_non_phase(self):
        assert PhaseName("design").__eq__("design") is NotImplemented


class TestSessionEnums:
    """Tests for session-related enums."""

    def test_session_type_values(self):
        assert SessionType.GREENFIELD.value == "greenfield"
        assert SessionType.BROWNFIELD.value == "brownfield"
        assert SessionType.REFACTORING.value == "refactoring"
        assert SessionType.GET_WELL.value == "get-well"

    def test_auto_mode_values(self):
        assert AutoMode.AUTO.value == "auto"
        assert AutoMode.MANUAL.value == "manual"
        assert AutoMode.SUPERVISED.value == "supervised"

    def test_review_decision_values(self):
        assert ReviewDecision.APPROVED.value == "approved"
        assert ReviewDecision.REJECTED.value == "rejected"
        assert ReviewDecision.REQUEST_CHANGES.value == "request_changes"

    def test_abort_mode_values(self):
        assert AbortMode.GRACEFUL.value == "graceful"
        assert AbortMode.HARD.value == "hard"

    def test_branch_strategy_values(self):
        assert BranchStrategy.KEEP.value == "keep"
        assert BranchStrategy.RENAME.value == "rename"
        assert BranchStrategy.DELETE.value == "delete"


class TestBackendEnums:
    """Tests for backend execution enums."""

    def test_backend_status_values(self):
        assert BackendStatus.SUCCESS.value == "success"
        assert BackendStatus.FAILURE.value == "failure"
        assert BackendStatus.TIMEOUT.value == "timeout"
        assert BackendStatus.SKIPPED.value == "skipped"
        assert BackendStatus.PARTIAL.value == "partial"

    def test_step_status_values(self):
        assert StepStatus.SUCCESS.value == "success"
        assert StepStatus.FAILURE.value == "failure"
        assert StepStatus.SKIPPED.value == "skipped"

    def test_step_type_values(self):
        assert StepType.PRODUCE.value == "produce"
        assert StepType.CRITIQUE.value == "critique"
        assert StepType.GATE.value == "gate"
        assert StepType.CONSULT.value == "consult"


class TestFeedbackEnums:
    """Tests for feedback-related enums."""

    def test_feedback_status_values(self):
        assert FeedbackStatus.OPEN.value == "open"
        assert FeedbackStatus.RESOLVED.value == "resolved"
        assert FeedbackStatus.SUPERSEDED.value == "superseded"


class TestAnalysisEnums:
    """Tests for analysis-related enums."""

    def test_severity_values(self):
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.ERROR.value == "error"

    def test_snapshot_status_values(self):
        assert SnapshotStatus.PLANNING.value == "planning"
        assert SnapshotStatus.IN_PROGRESS.value == "in_progress"
        assert SnapshotStatus.COMPLETE.value == "complete"
        assert SnapshotStatus.BLOCKED.value == "blocked"

    def test_health_severity_values(self):
        assert HealthSeverity.CRITICAL.value == "CRITICAL"
        assert HealthSeverity.BRANCH.value == "BRANCH"
        assert HealthSeverity.WARN.value == "WARN"
        assert HealthSeverity.INFO.value == "INFO"
