"""Tests for workflow/orchestrator.py: WorkflowOrchestrator.

Tests cover:
- Workflow registration and listing
- select_workflow with various session types
- select_workflow with engagement override
- select_workflow with unknown session type (falls back)
- enter_workflow lifecycle
- advance_workflow through phase sequence
- advance_workflow at end of workflow (completion)
- Error handling: unknown workflow, no phases, not active
- has_active_workflow
- get_workflow_status / get_state
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from harness.domain.engagement.model import Engagement
from harness.errors import UnknownWorkflowError
from harness.phase.orchestrator import PhaseOrchestrator, PhaseOrchestratorResult
from harness.workflow.model import (
    Workflow,
    WorkflowResult,
    WorkflowState,
    WorkflowStatus,
)
from harness.workflow.orchestrator import (
    DEFAULT_WORKFLOWS,
    SESSION_TYPE_MAP,
    WorkflowOrchestrator,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_phase_orchestrator() -> MagicMock:
    """Create a mock PhaseOrchestrator that returns success."""
    orchestrator = MagicMock(spec=PhaseOrchestrator)

    async def _enter_phase(slug, phase_name, mode="auto"):
        return PhaseOrchestratorResult(
            success=True,
            phase_name=phase_name,
            next_phase=None,
        )

    orchestrator.enter_phase = AsyncMock(side_effect=_enter_phase)
    return orchestrator


@pytest.fixture
def mock_failing_phase_orchestrator() -> MagicMock:
    """Create a mock PhaseOrchestrator that returns failure."""
    orchestrator = MagicMock(spec=PhaseOrchestrator)

    async def _enter_phase(slug, phase_name, mode="auto"):
        return PhaseOrchestratorResult(
            success=False,
            phase_name=phase_name,
            error=f"Phase '{phase_name}' failed",
            escalation="workflow",
        )

    orchestrator.enter_phase = AsyncMock(side_effect=_enter_phase)
    return orchestrator


@pytest.fixture
def orchestrator(mock_phase_orchestrator) -> WorkflowOrchestrator:
    """Create a WorkflowOrchestrator with default workflows."""
    wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)
    wf_orch.register_workflows(DEFAULT_WORKFLOWS)
    return wf_orch


# ── Registration Tests ──────────────────────────────────────────────


class TestWorkflowOrchestratorRegistration:
    """Workflow registration tests."""

    def test_register_workflow(self) -> None:
        wf_orch = WorkflowOrchestrator(
            MagicMock(spec=PhaseOrchestrator)
        )
        wf = Workflow(name="custom", phases=["a", "b"])
        wf_orch.register_workflow(wf)

        assert wf_orch.get_workflow("custom") is wf

    def test_register_workflows_dict(self) -> None:
        wf_orch = WorkflowOrchestrator(
            MagicMock(spec=PhaseOrchestrator)
        )
        workflows = {
            "a": Workflow(name="a", phases=["p1"]),
            "b": Workflow(name="b", phases=["p1", "p2"]),
        }
        wf_orch.register_workflows(workflows)
        assert wf_orch.get_workflow("a") is not None
        assert wf_orch.get_workflow("b") is not None

    def test_get_workflow_not_found(self) -> None:
        wf_orch = WorkflowOrchestrator(
            MagicMock(spec=PhaseOrchestrator)
        )
        assert wf_orch.get_workflow("nonexistent") is None

    def test_list_workflows(self, orchestrator: WorkflowOrchestrator) -> None:
        workflow_names = orchestrator.list_workflows()
        assert "standard" in workflow_names
        assert "quick-fix" in workflow_names
        assert "refactoring" in workflow_names
        assert "get-well" in workflow_names
        assert "inspect" in workflow_names
        assert workflow_names == sorted(workflow_names)


# ── Workflow Selection Tests ────────────────────────────────────────


class TestWorkflowSelection:
    """select_workflow tests."""

    def test_select_standard_for_greenfield(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        wf_name = orchestrator.select_workflow("greenfield")
        assert wf_name == "standard"

    def test_select_quick_fix(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        wf_name = orchestrator.select_workflow("quick-fix")
        assert wf_name == "quick-fix"

    def test_select_refactoring(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        wf_name = orchestrator.select_workflow("refactoring")
        assert wf_name == "refactoring"

    def test_select_get_well(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        wf_name = orchestrator.select_workflow("get-well")
        assert wf_name == "get-well"

    def test_select_inspect(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        wf_name = orchestrator.select_workflow("audit")
        assert wf_name == "inspect"

    def test_select_unknown_session_type_falls_back_to_standard(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        wf_name = orchestrator.select_workflow("unknown-type")
        assert wf_name == "standard"

    def test_select_with_engagement_workflow_override(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        engagement = Engagement(
            slug="test-eng",
            workflow_name="quick-fix",
        )
        wf_name = orchestrator.select_workflow(
            "greenfield", engagement=engagement
        )
        assert wf_name == "quick-fix"

    def test_select_with_engagement_empty_workflow(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        engagement = Engagement(
            slug="test-eng",
            workflow_name="",
        )
        wf_name = orchestrator.select_workflow(
            "greenfield", engagement=engagement
        )
        assert wf_name == "standard"

    def test_select_with_engagement_none(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        wf_name = orchestrator.select_workflow(
            "greenfield", engagement=None
        )
        assert wf_name == "standard"

    def test_select_unregistered_mapped_falls_to_standard(
        self, orchestrator: WorkflowOrchestrator
    ) -> None:
        # Temporarily remove 'standard' from registered workflows
        # to test we still handle fallback gracefully
        orchestrator = WorkflowOrchestrator(
            MagicMock(spec=PhaseOrchestrator)
        )
        wf = Workflow(name="standard", phases=["a"])
        orchestrator.register_workflow(wf)
        wf_name = orchestrator.select_workflow("unknown-type")
        assert wf_name == "standard"

    def test_select_throws_if_standard_not_registered(
        self,
    ) -> None:
        wf_orch = WorkflowOrchestrator(
            MagicMock(spec=PhaseOrchestrator)
        )
        # Register a non-standard workflow
        wf_orch.register_workflow(
            Workflow(name="custom", phases=["a"])
        )
        with pytest.raises(UnknownWorkflowError):
            wf_orch.select_workflow("greenfield")

    def test_session_type_map_coverage(self) -> None:
        """Verify all well-known session types map correctly."""
        expected = {
            "greenfield": "standard",
            "brownfield": "brownfield",
            "quick-fix": "quick-fix",
            "refactoring": "refactoring",
            "get-well": "get-well",
            "audit": "inspect",
            "inspect": "inspect",
            "review": "inspect",
        }
        for session_type, expected_wf in expected.items():
            assert SESSION_TYPE_MAP[session_type] == expected_wf


# ── Enter Workflow Tests ────────────────────────────────────────────


class TestEnterWorkflow:
    """enter_workflow tests."""

    async def test_enter_workflow_starts_first_phase(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)
        wf_orch.register_workflows(DEFAULT_WORKFLOWS)

        result = await wf_orch.enter_workflow(
            slug="test-eng",
            workflow_name="standard",
            mode="auto",
        )

        assert result.success
        assert result.slug == "test-eng"
        assert result.workflow_name == "standard"
        assert result.status == WorkflowStatus.ACTIVE
        # First phase should be completed after successful run
        assert "discover" in result.completed_phases
        assert result.current_phase is None

        # Verify PhaseOrchestrator was called correctly
        mock_phase_orchestrator.enter_phase.assert_called_once_with(
            slug="test-eng",
            phase_name="discover",
            mode="auto",
        )

    async def test_enter_workflow_unknown_workflow(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)

        result = await wf_orch.enter_workflow(
            slug="test", workflow_name="nonexistent"
        )

        assert not result.success
        assert result.error is not None
        assert "Unknown workflow" in result.error
        assert result.escalation == "user"

    async def test_enter_workflow_no_phases(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)
        wf_orch.register_workflow(
            Workflow(name="empty", phases=[])
        )

        result = await wf_orch.enter_workflow(
            slug="test", workflow_name="empty"
        )

        assert not result.success
        assert "no phases" in result.error
        assert result.escalation == "user"

    async def test_enter_workflow_with_failing_phase(
        self, mock_failing_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(
            mock_failing_phase_orchestrator
        )
        wf_orch.register_workflows(DEFAULT_WORKFLOWS)

        result = await wf_orch.enter_workflow(
            slug="test-eng", workflow_name="standard"
        )

        assert not result.success
        assert result.status == WorkflowStatus.FAILED
        assert "failed" in (result.error or "")

    async def test_enter_workflow_custom_mode(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)
        wf_orch.register_workflows(DEFAULT_WORKFLOWS)

        result = await wf_orch.enter_workflow(
            slug="test-eng",
            workflow_name="standard",
            mode="manual",
        )

        assert result.success
        assert result.mode == "manual"
        mock_phase_orchestrator.enter_phase.assert_called_with(
            slug="test-eng",
            phase_name="discover",
            mode="manual",
        )

    async def test_enter_workflow_tracks_state(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)
        wf_orch.register_workflows(DEFAULT_WORKFLOWS)

        await wf_orch.enter_workflow(
            slug="test-eng", workflow_name="standard"
        )

        state = wf_orch.get_state("test-eng")
        assert state is not None
        assert state.workflow_name == "standard"
        assert state.status == WorkflowStatus.ACTIVE

    async def test_enter_workflow_quick_fix_phase(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)
        wf_orch.register_workflows(DEFAULT_WORKFLOWS)

        result = await wf_orch.enter_workflow(
            slug="test-fix",
            workflow_name="quick-fix",
        )

        assert result.success
        mock_phase_orchestrator.enter_phase.assert_called_with(
            slug="test-fix",
            phase_name="fix",
            mode="auto",
        )


# ── Advance Workflow Tests ──────────────────────────────────────────


class TestAdvanceWorkflow:
    """advance_workflow tests."""

    async def test_advance_to_next_phase(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)
        wf_orch.register_workflow(
            Workflow(
                name="simple",
                phases=["phase_a", "phase_b"],
            )
        )

        # Enter -> runs phase_a
        await wf_orch.enter_workflow(
            slug="test", workflow_name="simple"
        )

        # Advance -> runs phase_b
        result = await wf_orch.advance_workflow("test")

        assert result.success
        assert result.current_phase is None
        assert len(result.completed_phases) == 2
        assert "phase_b" in result.completed_phases

        # Verify both phases were dispatched
        calls = mock_phase_orchestrator.enter_phase.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs["phase_name"] == "phase_a"
        assert calls[1].kwargs["phase_name"] == "phase_b"

    async def test_advance_workflow_completion(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)
        wf_orch.register_workflow(
            Workflow(name="single", phases=["only_one"])
        )

        await wf_orch.enter_workflow(
            slug="test", workflow_name="single"
        )
        result = await wf_orch.advance_workflow("test")

        assert result.success
        assert result.status == WorkflowStatus.COMPLETED
        assert result.current_phase is None
        assert result.completed_phases == ["only_one"]

    async def test_advance_no_pending_completes(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)
        wf_orch.register_workflow(
            Workflow(name="simple", phases=["a"])
        )

        await wf_orch.enter_workflow(
            slug="test", workflow_name="simple"
        )
        result1 = await wf_orch.advance_workflow("test")
        assert result1.status == WorkflowStatus.COMPLETED

        # Second advance on already-completed workflow
        result2 = await wf_orch.advance_workflow("test")
        assert result2.success  # still reports completed
        assert result2.status == WorkflowStatus.COMPLETED

    async def test_advance_unknown_slug(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)

        result = await wf_orch.advance_workflow("nonexistent")

        assert not result.success
        assert "No active workflow" in result.error

    async def test_has_active_workflow(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)
        wf_orch.register_workflow(
            Workflow(name="test", phases=["a", "b"])
        )

        assert not wf_orch.has_active_workflow("test-eng")

        await wf_orch.enter_workflow(
            slug="test-eng", workflow_name="test"
        )
        # After enter, first phase (a) completed, second phase (b) pending
        # State should be ACTIVE
        assert wf_orch.has_active_workflow("test-eng")

    async def test_advance_with_failing_phase(
        self, mock_failing_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(
            mock_failing_phase_orchestrator
        )
        wf_orch.register_workflow(
            Workflow(name="test", phases=["a", "b"])
        )

        await wf_orch.enter_workflow(
            slug="test", workflow_name="test"
        )
        result = await wf_orch.advance_workflow("test")

        assert not result.success
        assert result.status == WorkflowStatus.FAILED

    async def test_get_workflow_status(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)
        wf_orch.register_workflow(
            Workflow(name="test", phases=["a"])
        )

        status = await wf_orch.get_workflow_status("no-exist")
        assert status is None

        await wf_orch.enter_workflow(
            slug="test-eng", workflow_name="test"
        )
        status = await wf_orch.get_workflow_status("test-eng")
        assert status is not None
        assert isinstance(status, WorkflowState)
        assert status.workflow_name == "test"

    async def test_get_state_sync(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)
        wf_orch.register_workflow(
            Workflow(name="test", phases=["a"])
        )

        state = wf_orch.get_state("no-exist")
        assert state is None

        await wf_orch.enter_workflow(
            slug="test-eng", workflow_name="test"
        )
        state = wf_orch.get_state("test-eng")
        assert state is not None
        assert state.workflow_name == "test"

    async def test_advance_workflow_pending_phases_empty_with_current_phase(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        """Coverage: orchestrator.py lines 372-374.

        When advance_workflow is called with current_phase set
        but no pending phases remaining, it should mark the
        workflow as COMPLETED.

        This happens after reset_to_phase on the last completed
        phase — current_phase is set but pending_phases is empty.
        """
        wf_orch = WorkflowOrchestrator(mock_phase_orchestrator)
        wf_orch.register_workflow(
            Workflow(name="two_phase", phases=["a", "b"])
        )

        # Enter and advance to complete both phases
        await wf_orch.enter_workflow(
            slug="test", workflow_name="two_phase"
        )
        await wf_orch.advance_workflow("test")

        # State should be COMPLETED with no current phase
        state = wf_orch.get_state("test")
        assert state.status == WorkflowStatus.COMPLETED
        assert state.current_phase is None

        # Reset to last completed phase — sets current_phase="b"
        # with no pending phases remaining
        state.reset_to_phase("b")
        assert state.current_phase == "b"
        assert not state.pending_phases

        # advance_workflow should hit the second not-pending check
        # (line 372) and mark as COMPLETED
        result = await wf_orch.advance_workflow("test")
        assert result.success
        assert result.status == WorkflowStatus.COMPLETED
        assert result.current_phase is None

    async def test_advance_with_failing_phase_and_escalation(
        self, mock_phase_orchestrator: MagicMock
    ) -> None:
        """Coverage: orchestrator.py lines 409-415.

        When advance_workflow dispatches a phase that fails with
        an escalation value, the escalation logging block must
        be exercised.

        This requires the first phase (entered via enter_workflow)
        to succeed, then the second phase (from advance_workflow)
        to fail with an escalation value.
        """
        call_count = 0

        async def _enter(slug, phase_name, mode="auto"):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return PhaseOrchestratorResult(
                    success=True,
                    phase_name=phase_name,
                )
            return PhaseOrchestratorResult(
                success=False,
                phase_name=phase_name,
                error=f"Phase '{phase_name}' failed",
                escalation="phase",
            )

        orchestrator_mock = MagicMock(spec=PhaseOrchestrator)
        orchestrator_mock.enter_phase = AsyncMock(
            side_effect=_enter
        )

        wf_orch = WorkflowOrchestrator(orchestrator_mock)
        wf_orch.register_workflow(
            Workflow(name="test", phases=["a", "b"])
        )

        # Enter — runs phase_a (succeeds)
        await wf_orch.enter_workflow(
            slug="test", workflow_name="test"
        )

        # Advance — runs phase_b (fails with escalation="phase")
        result = await wf_orch.advance_workflow("test")

        assert not result.success
        assert result.status == WorkflowStatus.FAILED
        state = wf_orch.get_state("test")
        assert "b" in state.failed_phases


    async def test_advance_with_failing_phase(
        self, mock_failing_phase_orchestrator: MagicMock
    ) -> None:
        """Test that advance_workflow handles phase failure with escalation."""
        wf_orch = WorkflowOrchestrator(mock_failing_phase_orchestrator)
        wf_orch.register_workflows(DEFAULT_WORKFLOWS)

        await wf_orch.enter_workflow(
            slug="test-eng", workflow_name="standard",
        )
        result = await wf_orch.advance_workflow("test-eng")

        assert not result.success
        assert result.status == WorkflowStatus.FAILED
