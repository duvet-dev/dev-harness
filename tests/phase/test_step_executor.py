"""Tests for phase/step_executor.py: StepExecutor.

Tests cover:
- Agent step dispatch via StepDispatcher
- Loop step dispatch via LoopRunner
- Phase step dispatch via PhaseOrchestrator
- Error handling for each step type
- StepResult dataclass
- Unknown step type fallback
- Exception propagation (LoopExecutionError, PhaseExecutionError)
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from harness.errors import LoopExecutionError, PhaseExecutionError
from harness.phase.model import LoopConfig, Step
from harness.phase.step_executor import StepExecutor, StepResult
from harness.phase.step_executor import _LoopContext


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_step_dispatcher() -> AsyncMock:
    """Create a mock StepDispatcher."""
    dispatcher = AsyncMock(spec=[])
    dispatcher.dispatch = AsyncMock(
        return_value=SimpleNamespace(
            success=True,
            artifacts=[],
            error=None,
            escalation=None,
        )
    )
    return dispatcher


@pytest.fixture
def mock_loop_runner() -> AsyncMock:
    """Create a mock LoopRunner."""
    runner = AsyncMock(spec=[])
    runner.run = AsyncMock(
        return_value=SimpleNamespace(
            success=True,
            iteration_count=1,
            iteration_results=[],
            last_artifacts=[],
            error=None,
            escalation=None,
        )
    )
    return runner


@pytest.fixture
def mock_phase_orchestrator() -> AsyncMock:
    """Create a mock PhaseOrchestrator."""
    orchestrator = AsyncMock(spec=[])
    orchestrator.enter_phase = AsyncMock(
        return_value=SimpleNamespace(
            success=True,
            phase_result=None,
            phase_name="test-phase",
            next_phase=None,
            error=None,
            escalation=None,
        )
    )
    return orchestrator


@pytest.fixture
def executor(
    mock_step_dispatcher: AsyncMock,
    mock_loop_runner: AsyncMock,
    mock_phase_orchestrator: AsyncMock,
) -> StepExecutor:
    """Create a StepExecutor with all mocked dependencies."""
    return StepExecutor(
        step_dispatcher=mock_step_dispatcher,
        loop_runner=mock_loop_runner,
        phase_orchestrator=mock_phase_orchestrator,
    )


@pytest.fixture
def context() -> dict:
    """Create a sample execution context."""
    return {
        "slug": "test-workflow",
        "mode": "auto",
        "trace_id": "test-trace-456",
        "steps": [],
    }


# ── Step Dispatch Tests ──────────────────────────────────────────────


class TestStepExecutorDispatch:
    """Step dispatch routing tests."""

    @pytest.mark.asyncio
    async def test_agent_step_dispatch(
        self,
        executor: StepExecutor,
        mock_step_dispatcher: AsyncMock,
        context: dict,
    ) -> None:
        """Agent steps are dispatched via StepDispatcher."""
        step = Step(agents=["architect"])
        result = await executor.execute(step, context)

        assert result.success
        assert result.step_type == "agent"
        mock_step_dispatcher.dispatch.assert_called_once_with(
            step, context
        )

    @pytest.mark.asyncio
    async def test_team_step_dispatch(
        self,
        executor: StepExecutor,
        mock_step_dispatcher: AsyncMock,
        context: dict,
    ) -> None:
        """Team steps are dispatched via StepDispatcher."""
        step = Step(team="architecture")
        result = await executor.execute(step, context)

        assert result.success
        assert result.step_type == "team"
        mock_step_dispatcher.dispatch.assert_called_once_with(
            step, context
        )

    @pytest.mark.asyncio
    async def test_loop_step_dispatch(
        self,
        executor: StepExecutor,
        mock_loop_runner: AsyncMock,
    ) -> None:
        """Loop steps are dispatched via LoopRunner."""
        context_with_steps = {
            "slug": "test",
            "mode": "auto",
            "trace_id": "t1",
            "steps": [Step(agents=["builder"])],
        }
        step = Step(loop=LoopConfig(count=3))
        result = await executor.execute(step, context_with_steps)

        assert result.success
        assert result.step_type == "loop"
        mock_loop_runner.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_phase_step_dispatch(
        self,
        executor: StepExecutor,
        mock_phase_orchestrator: AsyncMock,
        context: dict,
    ) -> None:
        """Phase steps are dispatched via PhaseOrchestrator."""
        step = Step(phase="design")
        result = await executor.execute(step, context)

        assert result.success
        assert result.step_type == "phase"
        mock_phase_orchestrator.enter_phase.assert_called_once_with(
            slug="test-workflow",
            phase_name="design",
            mode="auto",
        )


# ── Error Handling Tests ─────────────────────────────────────────────


class TestStepExecutorErrors:
    """Step executor error handling tests."""

    @pytest.mark.asyncio
    async def test_agent_dispatch_error(
        self, context: dict
    ) -> None:
        """Agent dispatch errors are caught and reported."""
        failing_dispatcher = AsyncMock(spec=[])
        failing_dispatcher.dispatch = AsyncMock(
            side_effect=RuntimeError("Dispatch failed")
        )

        executor = StepExecutor(
            step_dispatcher=failing_dispatcher,
        )

        step = Step(agents=["architect"])
        result = await executor.execute(step, context)

        assert not result.success
        assert "Dispatch failed" in (result.error or "")
        assert result.step_type == "agent"
        assert result.escalation == "phase"

    @pytest.mark.asyncio
    async def test_loop_execution_error(
        self, context: dict
    ) -> None:
        """LoopExecutionError is propagated directly."""
        failing_loop = AsyncMock(spec=[])
        failing_loop.run = AsyncMock(
            return_value=SimpleNamespace(
                success=False,
                iteration_count=0,
                iteration_results=[],
                last_artifacts=[],
                error="Loop failed",
                escalation="loop",
            )
        )

        executor = StepExecutor(
            loop_runner=failing_loop,
        )

        step = Step(loop=LoopConfig(count=1))
        context_with_steps = dict(context)
        context_with_steps["steps"] = [Step(agents=["builder"])]

        with pytest.raises(LoopExecutionError) as excinfo:
            await executor.execute(step, context_with_steps)

        assert "Loop failed" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_phase_execution_error(
        self, context: dict
    ) -> None:
        """PhaseExecutionError is propagated directly."""
        failing_orchestrator = AsyncMock(spec=[])
        failing_orchestrator.enter_phase = AsyncMock(
            return_value=SimpleNamespace(
                success=False,
                phase_result=None,
                phase_name="unknown",
                next_phase=None,
                error="Phase not found",
                escalation="workflow",
            )
        )

        executor = StepExecutor(
            phase_orchestrator=failing_orchestrator,
        )

        step = Step(phase="unknown-phase")

        with pytest.raises(PhaseExecutionError) as excinfo:
            await executor.execute(step, context)

        assert "Phase not found" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_loop_runner_exception(
        self, context: dict
    ) -> None:
        """Exceptions from LoopRunner are wrapped in LoopExecutionError."""
        broken_loop = AsyncMock(spec=[])
        broken_loop.run = AsyncMock(
            side_effect=RuntimeError("Internal loop error")
        )

        executor = StepExecutor(
            loop_runner=broken_loop,
        )

        step = Step(loop=LoopConfig(count=1))

        with pytest.raises(LoopExecutionError) as excinfo:
            await executor.execute(step, context)

        assert "Internal loop error" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_phase_orchestrator_exception(
        self, context: dict
    ) -> None:
        """Exceptions from PhaseOrchestrator are wrapped in
        PhaseExecutionError."""
        broken_orch = AsyncMock(spec=[])
        broken_orch.enter_phase = AsyncMock(
            side_effect=RuntimeError("Orchestrator error")
        )

        executor = StepExecutor(
            phase_orchestrator=broken_orch,
        )

        step = Step(phase="design")

        with pytest.raises(PhaseExecutionError) as excinfo:
            await executor.execute(step, context)

        assert "Orchestrator error" in str(excinfo.value)


# ── StepResult Tests ─────────────────────────────────────────────────


class TestStepResult:
    """StepResult dataclass tests."""

    def test_defaults(self) -> None:
        """Test StepResult default values."""
        result = StepResult(success=True)
        assert result.success
        assert result.artifacts == []
        assert result.error is None
        assert result.step_type == "unknown"
        assert result.escalation is None
        assert result.trace_id == ""

    def test_failure_result(self) -> None:
        """Test failure result fields."""
        result = StepResult(
            success=False,
            error="Something went wrong",
            step_type="agent",
            escalation="phase",
            trace_id="trace-789",
        )
        assert not result.success
        assert result.error == "Something went wrong"
        assert result.step_type == "agent"
        assert result.escalation == "phase"
        assert result.trace_id == "trace-789"


# ── Edge Case Tests ──────────────────────────────────────────────────


class TestStepExecutorEdgeCases:
    """Step executor edge case tests."""

    @pytest.mark.asyncio
    async def test_unknown_step_type_handled(
        self, context: dict
    ) -> None:
        """An unknown step type (no type fields set) returns error.

        Note: This shouldn't happen in practice due to
        Step.__post_init__, but the executor handles it gracefully.
        """
        executor = StepExecutor()

        # Create a step that bypasses __post_init__
        step = object.__new__(Step)
        step.agents = None
        step.team = None
        step.loop = None
        step.phase = None

        result = await executor.execute(step, context)
        assert not result.success
        assert "Unknown step type" in (result.error or "")

    @pytest.mark.asyncio
    async def test_none_context(self, executor: StepExecutor) -> None:
        """StepExecutor handles None context gracefully."""
        step = Step(agents=["architect"])
        result = await executor.execute(step, None)
        assert result.success

    @pytest.mark.asyncio
    async def test_loop_without_steps(
        self,
        executor: StepExecutor,
        mock_loop_runner: AsyncMock,
    ) -> None:
        """Loop step with no sub-steps is handled."""
        context_no_steps = {
            "slug": "test",
            "mode": "auto",
            "trace_id": "t1",
            "steps": [],
        }
        step = Step(loop=LoopConfig(count=1))
        result = await executor.execute(step, context_no_steps)

        assert result.success
        assert result.step_type == "loop"
        mock_loop_runner.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatcher_error_path(
        self, context: dict
    ) -> None:
        """Dispatcher error is surfaced through StepExecutor."""
        failing_dispatcher = AsyncMock(spec=[])
        failing_dispatcher.dispatch = AsyncMock(
            return_value=SimpleNamespace(
                success=False,
                artifacts=[],
                error="Dispatcher error",
                escalation=None,
            )
        )
        executor = StepExecutor(
            step_dispatcher=failing_dispatcher,
        )

        step = Step(agents=["architect"])
        result = await executor.execute(step, context)
        assert not result.success
        assert result.error == "Dispatcher error"


# ── Coverage Gap Tests ──────────────────────────────────────────


class TestStepExecutorCoverage:
    """Coverage gap tests for uncovered branches in StepExecutor.

    These tests exercise stub methods, object-context paths, and
    defensive guards not reached by existing tests.

    The built-in stub methods (_stub_dispatcher, _stub_loop_runner,
    _stub_phase_orchestrator) replace their respective dependencies
    when None is passed to __init__. However, the dispatch methods
    call .dispatch(), .run(), and .enter_phase() respectively on
    these objects, while the stubs are themselves callables (async
    methods) — so they can't be reached through execute(). We
    test them by calling them directly.
    """

    @pytest.mark.asyncio
    async def test_stub_dispatcher_call(
        self, context: dict
    ) -> None:
        """_stub_dispatcher returns a valid result.

        Exercises lines 318-320.
        """
        executor = StepExecutor()
        step = Step(agents=["architect"])
        result = await executor._stub_dispatcher(step, context)
        assert result.success
        assert result.error is None

    @pytest.mark.asyncio
    async def test_stub_loop_runner_call(
        self, context: dict
    ) -> None:
        """_stub_loop_runner returns a valid result.

        Exercises lines 331-333.
        """
        executor = StepExecutor()
        step = Step(loop=LoopConfig(count=1))
        result = await executor._stub_loop_runner(
            loop_config=step.loop,
            steps=[],
            context=context,
        )
        assert result.success
        assert result.error is None

    @pytest.mark.asyncio
    async def test_stub_phase_orchestrator_call(
        self, context: dict
    ) -> None:
        """_stub_phase_orchestrator returns a valid result.

        Exercises lines 346-348.
        """
        executor = StepExecutor()
        result = await executor._stub_phase_orchestrator(
            slug="test",
            phase_name="design",
            mode="auto",
        )
        assert result.success
        assert result.error is None
        assert result.phase_name == "design"

    @pytest.mark.asyncio
    async def test_get_context_attr_with_object_context(
        self,
    ) -> None:
        """_get_context_attr object path.

        Exercises line 257: return getattr(context, attr, default).
        """
        executor = StepExecutor()
        ctx = SimpleNamespace(trace_id="obj-trace")
        result = executor._get_context_attr(ctx, "trace_id", "")
        assert result == "obj-trace"

    @pytest.mark.asyncio
    async def test_get_context_attr_with_none_context(
        self,
    ) -> None:
        """_get_context_attr handles None context.

        Exercises lines 253-254: if context is None: return default.
        """
        executor = StepExecutor()
        result = executor._get_context_attr(None, "trace_id", "fallback")
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_loop_step_none_loop_config_guard(
        self, context: dict
    ) -> None:
        """The step.loop is None guard returns an error result.

        Exercises line 200: the loop-None check in
        _dispatch_loop_step. Called directly since execute()
        routes away when step.loop is falsy.
        """
        executor = StepExecutor()
        step = object.__new__(Step)
        step.agents = None
        step.team = None
        step.loop = None
        step.phase = None

        result = await executor._dispatch_loop_step(step, context)
        assert not result.success
        assert "no loop configuration" in (result.error or "")
        assert result.step_type == "loop"

    @pytest.mark.asyncio
    async def test_get_context_attr_none_phase_default(
        self,
    ) -> None:
        """_get_context_attr used within phase dispatch with None."""
        executor = StepExecutor()
        result = executor._get_context_attr(None, "slug", "fallback")
        assert result == "fallback"


# ── LoopContext Tests ────────────────────────────────────────────────


class TestLoopContext:
    """Tests for the internal _LoopContext adapter class."""

    def test_from_context_none(self) -> None:
        """from_context(None) returns a default _LoopContext.

        Exercises line 378.
        """
        lc = _LoopContext.from_context(None)
        assert lc.slug == ""
        assert lc.mode == "auto"
        assert lc.trace_id == ""
        assert lc.steps == []
        assert lc.reentry is None

    def test_from_context_object(self) -> None:
        """from_context(object) reads attributes.

        Exercises lines 388-393.
        """
        ctx = SimpleNamespace(
            slug="my-slug",
            mode="manual",
            trace_id="my-trace",
            steps=["a", "b"],
            reentry="loop-1",
        )
        lc = _LoopContext.from_context(ctx)
        assert lc.slug == "my-slug"
        assert lc.mode == "manual"
        assert lc.trace_id == "my-trace"
        assert lc.steps == ["a", "b"]
        assert lc.reentry == "loop-1"

    def test_from_context_dict(self) -> None:
        """from_context(dict) reads via .get()."""
        ctx = {
            "slug": "dict-slug",
            "mode": "strict",
            "trace_id": "dict-trace",
            "steps": ["x"],
            "reentry": "loop-2",
        }
        lc = _LoopContext.from_context(ctx)
        assert lc.slug == "dict-slug"
        assert lc.mode == "strict"
        assert lc.trace_id == "dict-trace"
        assert lc.steps == ["x"]
        assert lc.reentry == "loop-2"

    def test_setdefault_missing_key(self) -> None:
        """setdefault adds a key that doesn't exist.

        Exercises lines 397-398. Must use a key that __init__
        does NOT already set (all known fields are pre-set).
        """
        lc = _LoopContext()
        lc.setdefault("custom_field", "custom_value")
        assert lc.custom_field == "custom_value"  # type: ignore[attr-defined]

    def test_setdefault_existing_key(self) -> None:
        """setdefault does nothing when key already exists."""
        lc = _LoopContext()
        lc.slug = "original"
        lc.setdefault("slug", "new")
        assert lc.slug == "original"

    def test_setdefault_custom_key(self) -> None:
        """setdefault works with custom attribute names."""
        lc = _LoopContext()
        lc.setdefault("custom_field", "custom_value")
        assert lc.custom_field == "custom_value"  # type: ignore[attr-defined]
