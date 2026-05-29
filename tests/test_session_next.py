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


# ── Additional gap-coverage tests ────────────────────────────────────


class _FailingEnterOrchestrator:
    """Orchestrator stub that fails on enter_workflow."""

    def get_state(self, slug: str) -> None:
        return None

    async def enter_workflow(self, slug: str, workflow_name: str, mode: str = "auto"):
        return _StubWorkflowResult(
            success=False,
            error="Enter failed",
            escalation="workflow",
        )

    async def advance_workflow(self, slug: str):
        return _StubWorkflowResult(success=True)


class _FailingAdvanceOrchestrator:
    """Orchestrator stub that fails on advance_workflow."""

    def __init__(self):
        self._state = _StubWorkflowState(
            is_active=True,
            workflow_name="standard",
            current_phase="discover",
        )

    def get_state(self, slug: str):
        return self._state

    async def enter_workflow(self, slug: str, workflow_name: str, mode: str = "auto"):
        return _StubWorkflowResult(success=True)

    async def advance_workflow(self, slug: str):
        return _StubWorkflowResult(
            success=False,
            error="Advance failed",
            escalation="workflow",
        )


class _CompletingAdvanceOrchestrator:
    """Orchestrator stub whose advance_workflow returns completed."""

    def __init__(self):
        self._state = _StubWorkflowState(
            is_active=True,
            workflow_name="standard",
            current_phase="discover",
        )

    def get_state(self, slug: str):
        return self._state

    async def enter_workflow(self, slug: str, workflow_name: str, mode: str = "auto"):
        return _StubWorkflowResult(success=True)

    async def advance_workflow(self, slug: str):
        return _StubWorkflowResult(
            success=True,
            workflow_name="standard",
            status="completed",
        )


class _FailingStepExecutor:
    """Step executor stub that raises on dispatch."""

    async def dispatch(self, slug: str, phase_name: str):
        raise ValueError("Step dispatch crashed!")


class _SlugTrackerStepExecutor(_StubStepExecutor):
    """Step executor stub that records the last slug."""

    def __init__(self):
        super().__init__()
        self.last_slug = None
        self.last_phase = None

    async def dispatch(self, slug: str, phase_name: str):
        self.last_slug = slug
        self.last_phase = phase_name
        return await super().dispatch(slug, phase_name)


class TestNextEngineCoverage:
    """Edge-case coverage for NextEngine (uncorking 12 missed lines)."""

    # ── Line 134: enter_workflow failure path ────────────────────────

    @pytest.mark.asyncio
    async def test_advance_enter_workflow_fails(self):
        """enter_workflow returns success=False → reports error."""
        engine = NextEngine(workflow_orchestrator=_FailingEnterOrchestrator())
        result = await engine.advance("fail-enter")

        assert result.success is False
        assert result.action == "error"
        assert result.slug == "fail-enter"
        assert "Enter failed" in result.error
        assert result.escalation == "workflow"

    # ── Line 181: advance_workflow failure path ──────────────────────

    @pytest.mark.asyncio
    async def test_advance_advance_workflow_fails(self):
        """advance_workflow returns success=False → reports error."""
        engine = NextEngine(workflow_orchestrator=_FailingAdvanceOrchestrator())
        result = await engine.advance("fail-advance")

        assert result.success is False
        assert result.action == "error"
        assert "Advance failed" in result.error
        assert result.escalation == "workflow"

    # ── Line 192: advance_workflow returns completed ─────────────────

    @pytest.mark.asyncio
    async def test_advance_workflow_completes_on_advance(self):
        """advance_workflow returns status=completed → workflow_complete."""
        engine = NextEngine(
            workflow_orchestrator=_CompletingAdvanceOrchestrator()
        )
        result = await engine.advance("complete-on-advance")

        assert result.success is True
        assert result.action == "workflow_complete"
        assert result.workflow_name == "standard"

    # ── Lines 211-233: step execution path (non-active state) ───────

    @pytest.mark.asyncio
    async def test_advance_step_execution_on_non_active_state(self):
        """Non-completed, non-active state with step executor → dispatches step."""
        from types import SimpleNamespace

        # State: not completed, not active, but has a current_phase
        state = _StubWorkflowState(
            is_completed=False,
            is_active=False,
            workflow_name="standard",
            current_phase="design",
            completed_phases=["discover"],
            pending_phases=["build"],
        )

        orchestrator = _StubWorkflowOrchestrator()
        orchestrator.set_state("non-active-step", state)

        tracker = _SlugTrackerStepExecutor()
        engine = NextEngine(
            workflow_orchestrator=orchestrator,
            step_executor=tracker,
        )

        result = await engine.advance("non-active-step")

        assert result.success is True
        assert result.action == "step_executed"
        assert result.workflow_name == "standard"
        assert result.phase_name == "design"
        assert result.step_name == "write-code"
        assert "code.py" in result.artifacts_produced
        assert tracker.last_slug == "non-active-step"
        assert tracker.last_phase == "design"

    # ── Lines 234-238: step dispatch raises exception ────────────────

    @pytest.mark.asyncio
    async def test_advance_step_execution_raises_exception(self):
        """Step dispatch raises → logs warning, falls through to fallback."""
        state = _StubWorkflowState(
            is_completed=False,
            is_active=False,
            workflow_name="standard",
            current_phase="design",
        )

        orchestrator = _StubWorkflowOrchestrator()
        orchestrator.set_state("fail-step", state)

        engine = NextEngine(
            workflow_orchestrator=orchestrator,
            step_executor=_FailingStepExecutor(),
        )

        result = await engine.advance("fail-step")

        # Falls through to fallback return at line 242
        assert result.success is True
        assert result.action == "phase_advance"
        assert result.workflow_name == "standard"
        assert result.phase_name == "design"

    # ── Line 242: fallback when no step executor and non-active state ─

    @pytest.mark.asyncio
    async def test_advance_fallback_non_active_no_executor(self):
        """Non-completed, non-active state, no step executor → fallback."""
        state = _StubWorkflowState(
            is_completed=False,
            is_active=False,
            workflow_name="standard",
            current_phase=None,
        )

        orchestrator = _StubWorkflowOrchestrator()
        orchestrator.set_state("fallback", state)

        engine = NextEngine(workflow_orchestrator=orchestrator)
        result = await engine.advance("fallback")

        assert result.success is True
        assert result.action == "phase_advance"
        assert result.workflow_name == "standard"


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
