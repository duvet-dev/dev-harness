"""Tests for workflow/model.py: Workflow, WorkflowState, WorkflowResult.

Tests cover:
- Workflow dataclass (basic + existing tests)
- WorkflowState: creation, properties, phase lifecycle
- WorkflowState: progress, reset, from_workflow factory
- WorkflowResult dataclass
"""

from __future__ import annotations

import pytest

from harness.workflow.model import (
    Workflow,
    WorkflowResult,
    WorkflowState,
    WorkflowStatus,
)


class TestWorkflow:
    """Workflow dataclass tests."""

    def test_minimal_workflow(self) -> None:
        wf = Workflow(name="standard")
        assert wf.name == "standard"
        assert wf.phases == []

    def test_with_phases(self) -> None:
        wf = Workflow(
            name="standard",
            phases=["design", "build", "review", "test", "validate"],
        )
        assert wf.name == "standard"
        assert len(wf.phases) == 5
        assert wf.phases[0] == "design"
        assert wf.phases[-1] == "validate"

    def test_empty_name(self) -> None:
        wf = Workflow(name="")
        assert wf.name == ""

    def test_single_phase(self) -> None:
        wf = Workflow(name="quick-fix", phases=["fix"])
        assert len(wf.phases) == 1

    def test_immutability_of_default_factory(self) -> None:
        """Each workflow should have its own phases list."""
        wf1 = Workflow(name="a")
        wf2 = Workflow(name="b")
        wf1.phases.append("design")
        assert wf2.phases == []


class TestWorkflowState:
    """WorkflowState tests."""

    def test_minimal_state(self) -> None:
        state = WorkflowState(workflow_name="standard")
        assert state.workflow_name == "standard"
        assert state.status == WorkflowStatus.PENDING
        assert state.current_phase is None
        assert state.pending_phases == []
        assert state.completed_phases == []
        assert state.failed_phases == []
        assert state.mode == "auto"

    def test_state_with_phases(self) -> None:
        state = WorkflowState(
            workflow_name="standard",
            slug="test-eng",
            pending_phases=["discover", "design", "build"],
        )
        assert state.slug == "test-eng"
        assert state.pending_phases == ["discover", "design", "build"]
        assert state.status == WorkflowStatus.PENDING

    def test_mark_phase_started(self) -> None:
        state = WorkflowState(
            workflow_name="standard",
            slug="test",
            pending_phases=["discover", "design", "build"],
        )
        state.mark_phase_started("discover")
        assert state.current_phase == "discover"
        assert state.status == WorkflowStatus.ACTIVE
        assert "discover" not in state.pending_phases

    def test_mark_phase_started_raises_if_active(self) -> None:
        state = WorkflowState(
            workflow_name="standard",
            slug="test",
            pending_phases=["discover", "design"],
        )
        state.mark_phase_started("discover")
        with pytest.raises(ValueError, match="still active"):
            state.mark_phase_started("design")

    def test_mark_phase_completed(self) -> None:
        state = WorkflowState(
            workflow_name="standard",
            slug="test",
            pending_phases=["discover", "design"],
        )
        state.mark_phase_started("discover")
        state.mark_phase_completed("discover")
        assert state.current_phase is None
        assert "discover" in state.completed_phases
        assert state.status == WorkflowStatus.ACTIVE

    def test_mark_phase_completed_all_done(self) -> None:
        state = WorkflowState(
            workflow_name="standard",
            slug="test",
            pending_phases=["discover"],
        )
        state.mark_phase_started("discover")
        state.mark_phase_completed("discover")
        assert state.status == WorkflowStatus.COMPLETED
        assert state.completed_phases == ["discover"]

    def test_mark_phase_completed_not_current(self) -> None:
        state = WorkflowState(
            workflow_name="standard",
            slug="test",
            pending_phases=["discover", "design"],
        )
        state.mark_phase_started("discover")
        with pytest.raises(ValueError, match="not the current phase"):
            state.mark_phase_completed("design")

    def test_mark_phase_failed(self) -> None:
        state = WorkflowState(
            workflow_name="standard",
            slug="test",
            pending_phases=["discover", "design"],
        )
        state.mark_phase_started("discover")
        state.mark_phase_failed("discover")
        assert state.status == WorkflowStatus.FAILED
        assert "discover" in state.failed_phases
        assert state.current_phase is None

    def test_full_lifecycle(self) -> None:
        """Multiple phases: start → complete → start → complete → done."""
        state = WorkflowState(
            workflow_name="standard",
            slug="test",
            pending_phases=["a", "b", "c"],
        )

        state.mark_phase_started("a")
        assert state.current_phase == "a"
        assert state.status == WorkflowStatus.ACTIVE

        state.mark_phase_completed("a")
        assert state.completed_phases == ["a"]

        state.mark_phase_started("b")
        state.mark_phase_completed("b")
        assert state.completed_phases == ["a", "b"]

        state.mark_phase_started("c")
        state.mark_phase_completed("c")
        assert state.status == WorkflowStatus.COMPLETED
        assert state.completed_phases == ["a", "b", "c"]

    def test_is_active_property(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            pending_phases=["a"],
        )
        assert not state.is_active
        state.mark_phase_started("a")
        assert state.is_active
        state.mark_phase_completed("a")
        assert not state.is_active

    def test_is_completed_property(self) -> None:
        state = WorkflowState(
            workflow_name="test", pending_phases=["a"]
        )
        state.mark_phase_started("a")
        assert not state.is_completed
        state.mark_phase_completed("a")
        assert state.is_completed

    def test_is_failed_property(self) -> None:
        state = WorkflowState(
            workflow_name="test", pending_phases=["a"]
        )
        state.mark_phase_started("a")
        assert not state.is_failed
        state.mark_phase_failed("a")
        assert state.is_failed

    def test_progress_zero(self) -> None:
        state = WorkflowState(workflow_name="test")
        assert state.progress == 0.0

    def test_progress_no_phases(self) -> None:
        state = WorkflowState(workflow_name="test")
        assert state.progress == 0.0

    def test_progress_partial(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            pending_phases=["a", "b", "c"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")
        assert state.progress == pytest.approx(1.0 / 3.0)

    def test_progress_half(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            pending_phases=["a", "b"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")
        assert state.progress == 0.5

    def test_progress_full(self) -> None:
        state = WorkflowState(
            workflow_name="test", pending_phases=["a"]
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")
        assert state.progress == 1.0

    def test_all_phases_returns_ordered(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            pending_phases=["a", "b", "c"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")
        state.mark_phase_started("b")
        state.mark_phase_completed("b")
        state.mark_phase_started("c")

        phases = state.all_phases
        assert phases == ["a", "b", "c"]

    def test_reset_to_phase_completed(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            pending_phases=["a", "b", "c"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")
        state.mark_phase_started("b")
        state.mark_phase_completed("b")

        state.reset_to_phase("a")
        assert state.current_phase == "a"
        assert state.status == WorkflowStatus.ACTIVE
        assert "a" not in state.completed_phases
        assert "b" in state.pending_phases

    def test_reset_to_phase_pending(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            pending_phases=["a", "b", "c"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")

        state.reset_to_phase("b")
        assert state.current_phase == "b"
        assert "b" not in state.pending_phases
        assert "c" in state.pending_phases

    def test_reset_to_phase_not_found(self) -> None:
        state = WorkflowState(
            workflow_name="test", pending_phases=["a"]
        )
        with pytest.raises(ValueError, match="not found"):
            state.reset_to_phase("unknown")

    def test_from_workflow_factory(self) -> None:
        wf = Workflow(
            name="standard",
            phases=["discover", "design", "build"],
        )
        state = WorkflowState.from_workflow(
            workflow=wf, slug="test-eng", mode="manual"
        )
        assert state.workflow_name == "standard"
        assert state.slug == "test-eng"
        assert state.pending_phases == ["discover", "design", "build"]
        assert state.mode == "manual"
        assert state.status == WorkflowStatus.PENDING

    def test_from_workflow_empty(self) -> None:
        wf = Workflow(name="empty")
        state = WorkflowState.from_workflow(workflow=wf)
        assert state.pending_phases == []

    def test_metadata_passthrough(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            metadata={"optional_phases": ["review"]},
        )
        assert state.metadata["optional_phases"] == ["review"]

    def test_mode_default_auto(self) -> None:
        state = WorkflowState(workflow_name="test")
        assert state.mode == "auto"


class TestWorkflowResult:
    """WorkflowResult dataclass tests."""

    def test_minimal_result(self) -> None:
        result = WorkflowResult(success=True)
        assert result.success
        assert result.workflow_name == ""
        assert result.slug == ""
        assert result.error is None
        assert result.escalation is None
        assert result.mode == "auto"

    def test_failed_result(self) -> None:
        result = WorkflowResult(
            success=False,
            workflow_name="test",
            error="Something went wrong",
            escalation="user",
        )
        assert not result.success
        assert result.error == "Something went wrong"
        assert result.escalation == "user"

    def test_with_phase_tracking(self) -> None:
        result = WorkflowResult(
            success=True,
            workflow_name="standard",
            slug="eng-1",
            current_phase="build",
            completed_phases=["discover", "design"],
            pending_phases=["review", "test", "validate"],
            status=WorkflowStatus.ACTIVE,
        )
        assert result.current_phase == "build"
        assert result.completed_phases == ["discover", "design"]
        assert result.pending_phases == [
            "review", "test", "validate",
        ]
        assert result.status == WorkflowStatus.ACTIVE
