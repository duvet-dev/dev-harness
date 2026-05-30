"""Tests for command value objects.

Covers PhaseName validation and enum types.
"""

from __future__ import annotations

import pytest

from harness.command.values import (
    AbortMode,
    AutoMode,
    BranchStrategy,
    EngStatus,
    PhaseName,
    ReviewDecision,
    SessionType,
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


class TestEnums:
    """Tests for command enum types."""

    def test_session_type_values(self):
        assert SessionType.GREENFIELD.value == "greenfield"
        assert SessionType.BROWNFIELD.value == "brownfield"
        assert SessionType.REFACTORING.value == "refactoring"
        assert SessionType.GET_WELL.value == "get-well"

    def test_auto_mode_values(self):
        assert AutoMode.AUTO.value == "auto"
        assert AutoMode.MANUAL.value == "manual"
        assert AutoMode.SUPERVISED.value == "supervised"

    def test_eng_status_values(self):
        assert EngStatus.CREATED.value == "created"
        assert EngStatus.IN_PROGRESS.value == "in_progress"
        assert EngStatus.COMPLETED.value == "completed"
        assert EngStatus.ABORTED.value == "aborted"

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
