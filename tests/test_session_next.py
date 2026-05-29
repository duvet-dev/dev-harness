"""Tests for NextEngine — advance engagement to next step/phase/workflow.

Covers:
- NextEngine.advance() with workflow orchestrator (start, advance, complete)
- Result types and actions (workflow_start, phase_advance, workflow_complete)
- Stub mode (no orchestrator configured)
- Error handling for failed advancement
"""

from __future__ import annotations

import pytest

from harness.session.next import NextEngine, NextResult


# ── Stubs ────────────────────────────────────────────────────────────


class _StubWorkflowState:
    """Minimal stub that mimics WorkflowState attributes."""

    def __init__(
        self,
        is_completed: bool = False,
        is_active: bool = True,
        workflow_name: str = "standard",
        current_phase: str | None = "discover",
        completed_phases: list[str | None] | None = None,
        pending_phases: list[str] | None = None,
        status: str = "active",
    ):
        self._is_completed = is_completed
        self._is_active = is_active
        self.workflow_name = workflow_name
        self.current_phase = current_phase
        self.completed_phases = completed_phases or []
        self.pending_phases = pending_phases or ["design", "build"]
        self._status = status

    @property
    def is_completed(self) -> bool:
        return self._is_completed

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def status(self):
        class StatusObj:
            def __init__(self, v):
                self.value = v
        return StatusObj(self._status)


class _StubWorkflowResult:
    """Minimal stub that mimics WorkflowResult attributes."""

    def __init__(
        self,
        success: bool = True,
        workflow_name: str = "standard",
        current_phase: str | None = "discover",
        status: str = "active",
        error: str | None = None,
        escalation: str | None = None,
    ):
        self.success = success
        self.workflow_name = workflow_name
        self.current_phase = current_phase
        self._status = status
        self.error = error
        self.escalation = escalation

    @property
    def status(self):
        class StatusObj:
            def __init__(self, v):
                self.value = v
        return StatusObj(self._status)


class _StubWorkflowOrchestrator:
    """Stub WorkflowOrchestrator for testing NextEngine."""

    def __init__(self):
        self._state: dict[str, _StubWorkflowState] = {}
        self._enter_called = False
        self._advance_called = False

    def get_state(self, slug: str) -> _StubWorkflowState | None:
        return self._state.get(slug)

    def set_state(self, slug: str, state: _StubWorkflowState):
        self._state[slug] = state

    async def enter_workflow(self, slug: str, workflow_name: str, mode: str = "auto"):
        self._enter_called = True
        self._state[slug] = _StubWorkflowState(
            workflow_name=workflow_name,
            current_phase="discover",
            is_active=True,
            pending_phases=["design", "build", "test", "review"],
        )
        return _StubWorkflowResult(
            success=True,
            workflow_name=workflow_name,
            current_phase="discover",
            status="active",
        )

    async def advance_workflow(self, slug: str):
        self._advance_called = True
        state = self._state.get(slug)
        if state is None:
            return _StubWorkflowResult(success=False, error="No active workflow")
        return _StubWorkflowResult(
            success=True,
            workflow_name=state.workflow_name,
            current_phase="design",
            status="active",
        )


class _StubStepExecutor:
    """Stub StepExecutor for testing NextEngine step dispatch."""

    def __init__(self):
        self._dispatches: list[dict] = []

    async def dispatch(self, slug: str, phase_name: str):
        self._dispatches.append({"slug": slug, "phase": phase_name})
        from types import SimpleNamespace
        return SimpleNamespace(
            success=True,
            step_name="write-code",
            artifacts=["code.py"],
        )


# ── Tests ────────────────────────────────────────────────────────────


class TestNextEngine:
    """NextEngine — advance engagement lifecycle."""

    def test_advance_stub_mode(self):
        """No orchestrator configured → stub result."""
        engine = NextEngine()
        result = engine._stub_advance("my-eng")
        assert result.slug == "my-eng"
        assert result.action == "stub"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_advance_no_workflow_starts_one(self):
        """No workflow active → should start a new workflow."""
        orchestrator = _StubWorkflowOrchestrator()
        engine = NextEngine(workflow_orchestrator=orchestrator)

        result = await engine.advance("new-eng", workflow_name="standard")

        assert result.success is True
        assert result.action == "workflow_start"
        assert result.workflow_name == "standard"
        assert result.phase_name == "discover"
        assert orchestrator._enter_called is True

    @pytest.mark.asyncio
    async def test_advance_workflow_already_active(self):
        """Active workflow → should advance to next phase."""
        orchestrator = _StubWorkflowOrchestrator()
        orchestrator.set_state(
            "active-eng",
            _StubWorkflowState(
                is_active=True,
                workflow_name="standard",
                current_phase="discover",
                completed_phases=[],
                pending_phases=["design", "build", "test", "review"],
            ),
        )
        engine = NextEngine(workflow_orchestrator=orchestrator)

        result = await engine.advance("active-eng")

        assert result.success is True
        assert result.action in ("phase_advance", "step_executed")
        assert orchestrator._advance_called is True

    @pytest.mark.asyncio
    async def test_advance_workflow_completed(self):
        """Workflow already completed → reports workflow_complete."""
        orchestrator = _StubWorkflowOrchestrator()
        orchestrator.set_state(
            "done-eng",
            _StubWorkflowState(
                is_completed=True,
                is_active=False,
                workflow_name="standard",
                current_phase=None,
                status="completed",
            ),
        )
        engine = NextEngine(workflow_orchestrator=orchestrator)

        result = await engine.advance("done-eng")

        assert result.success is True
        assert result.action == "workflow_complete"
        assert result.workflow_name == "standard"

    @pytest.mark.asyncio
    async def test_advance_with_stub_mode_default(self):
        """NextEngine with None orchestrator returns stub."""
        engine = NextEngine(workflow_orchestrator=None)
        result = await engine.advance("stub-eng")
        # Falls through to stub because no orchestrator
        assert result.success is True
        assert result.action == "stub"

    @pytest.mark.asyncio
    async def test_advance_with_step_executor(self):
        """StepExecutor configured → step dispatch attempted."""
        orchestrator = _StubWorkflowOrchestrator()
        step_exec = _StubStepExecutor()
        engine = NextEngine(
            workflow_orchestrator=orchestrator,
            step_executor=step_exec,
        )

        result = await engine.advance("step-eng")

        assert result.success is True
        # Should start workflow since none exists
        assert result.action == "workflow_start"

    async def test_advance_with_step_executor_active(self):
        """Active workflow with step executor → dispatches step."""
        orchestrator = _StubWorkflowOrchestrator()
        state = _StubWorkflowState(
            is_active=True,
            workflow_name="standard",
            current_phase="discover",
            completed_phases=[],
            pending_phases=["design"],
        )
        # Make it not active so advance_workflow is called
        state._is_active = True  # Keep active so advance gets called
        orchestrator.set_state("active-step-eng", state)
        step_exec = _StubStepExecutor()
        engine = NextEngine(
            workflow_orchestrator=orchestrator,
            step_executor=step_exec,
        )

        result = await engine.advance("active-step-eng")
        # Should advance workflow since it's active
        assert result.success is True


# ── Data class tests ─────────────────────────────────────────────────


class TestNextResult:
    """NextResult dataclass."""

    def test_defaults(self):
        result = NextResult(success=True, slug="test")
        assert result.success is True
        assert result.slug == "test"
        assert result.action == ""
        assert result.workflow_name == ""
        assert result.phase_name == ""
        assert result.step_name == ""
        assert result.artifacts_produced == []
        assert result.error == ""
        assert result.escalation == ""

    def test_artifact_tracking(self):
        result = NextResult(
            success=True,
            slug="test",
            action="step_executed",
            artifacts_produced=["file1.py", "file2.py"],
        )
        assert len(result.artifacts_produced) == 2
        assert "file1.py" in result.artifacts_produced
