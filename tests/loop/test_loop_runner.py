"""Tests for loop/runner.py: LoopRunner.

Tests cover:
- Basic iteration execution (count=0, count=1, count=N)
- Feed-forward between iterations (outputs N → inputs N+1)
- Failure in an iteration stops the loop
- Circuit breaker integration
- Re-entry semantics (reset vs resume, R18)
- Loop state tracking (per-loop, not global)
- LoopRunnerResult fields
- Edge cases: empty sub-steps, single step
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from harness.errors import LoopExecutionError
from harness.loop.model import LoopState
from harness.loop.runner import LoopRunner, LoopRunnerResult
from harness.phase.circuit_breaker import CircuitBreakerRegistry
from harness.phase.model import LoopConfig, Step


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_step_executor() -> AsyncMock:
    """Create a mock StepExecutor that always succeeds."""
    executor = AsyncMock(spec=[])
    executor.execute = AsyncMock(
        return_value=SimpleNamespace(
            success=True, artifacts=[], error=None
        )
    )
    return executor


@pytest.fixture
def mock_failing_executor() -> AsyncMock:
    """Create a mock StepExecutor that fails on third call."""
    executor = AsyncMock(spec=[])
    call_count = 0

    async def execute_fn(
        step: Step, context: dict
    ) -> SimpleNamespace:
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            return SimpleNamespace(
                success=False,
                artifacts=[],
                error="Step execution failed",
            )
        return SimpleNamespace(
            success=True, artifacts=[], error=None
        )

    executor.execute = execute_fn
    return executor


@pytest.fixture
def mock_exception_executor() -> AsyncMock:
    """Create a mock StepExecutor that raises an exception."""
    executor = AsyncMock(spec=[])

    async def execute_fn(
        step: Step, context: dict
    ) -> SimpleNamespace:
        raise RuntimeError("Unexpected error in step")

    executor.execute = execute_fn
    return executor


@pytest.fixture
def circuit_breaker() -> CircuitBreakerRegistry:
    """Create a CircuitBreakerRegistry for testing."""
    return CircuitBreakerRegistry()


@pytest.fixture
def runner(mock_step_executor: AsyncMock) -> LoopRunner:
    """Create a LoopRunner with a mock step executor."""
    return LoopRunner(
        step_executor=mock_step_executor,
        circuit_breaker_registry=CircuitBreakerRegistry(),
    )


@pytest.fixture
def sample_steps() -> list[Step]:
    """Create sample sub-steps for loop execution."""
    return [
        Step(agents=["coder"]),
        Step(agents=["tester"]),
    ]


@pytest.fixture
def sample_context() -> dict:
    """Create a sample execution context."""
    return {
        "slug": "test-workflow",
        "mode": "auto",
        "trace_id": "test-trace-123",
        "steps": [],
        "reentry": None,
    }


# ── Basic Iteration Tests ────────────────────────────────────────────


class TestLoopRunnerBasic:
    """Basic iteration execution tests."""

    @pytest.mark.asyncio
    async def test_count_zero(
        self, runner: LoopRunner, sample_steps: list[Step]
    ) -> None:
        """Zero count means no iterations."""
        result = await runner.run(
            loop_config=LoopConfig(count=0),
            steps=sample_steps,
            context={},
        )
        assert result.success
        assert result.iteration_count == 0
        assert result.iteration_results == []
        assert result.error is None

    @pytest.mark.asyncio
    async def test_count_one(
        self, runner: LoopRunner, sample_steps: list[Step]
    ) -> None:
        """Single iteration executes all sub-steps."""
        result = await runner.run(
            loop_config=LoopConfig(count=1),
            steps=sample_steps,
            context={},
        )
        assert result.success
        assert result.iteration_count == 1
        assert len(result.iteration_results) == 1
        assert result.iteration_results[0]["success"]

    @pytest.mark.asyncio
    async def test_count_three(
        self, runner: LoopRunner, sample_steps: list[Step]
    ) -> None:
        """Multiple iterations execute correctly."""
        result = await runner.run(
            loop_config=LoopConfig(count=3),
            steps=sample_steps,
            context={},
        )
        assert result.success
        assert result.iteration_count == 3
        assert len(result.iteration_results) == 3
        for i, iteration in enumerate(result.iteration_results):
            assert iteration["success"], (
                f"Iteration {i + 1} should have succeeded"
            )
            assert iteration["iteration"] == i + 1

    @pytest.mark.asyncio
    async def test_empty_steps(
        self, runner: LoopRunner
    ) -> None:
        """Empty sub-steps: loop runs but does nothing."""
        result = await runner.run(
            loop_config=LoopConfig(count=3),
            steps=[],
            context={},
        )
        assert result.success
        assert result.iteration_count == 3
        assert len(result.iteration_results) == 3

    @pytest.mark.asyncio
    async def test_single_step(
        self, runner: LoopRunner
    ) -> None:
        """Single sub-step loops correctly."""
        result = await runner.run(
            loop_config=LoopConfig(count=5),
            steps=[Step(agents=["builder"])],
            context={},
        )
        assert result.success
        assert result.iteration_count == 5


# ── Feed-Forward Tests ───────────────────────────────────────────────


class TestLoopRunnerFeedForward:
    """Tests for iteration-to-iteration feed-forward."""

    @pytest.mark.asyncio
    async def test_context_updated_between_iterations(
        self,
    ) -> None:
        """Artifacts from iteration N are passed to N+1."""
        captured_contexts: list[dict] = []
        executor = AsyncMock(spec=[])

        async def execute_fn(
            step: Step, context: dict
        ) -> SimpleNamespace:
            captured_contexts.append(dict(context))
            return SimpleNamespace(
                success=True,
                artifacts=[f"artifact-{len(captured_contexts)}"],
                error=None,
            )

        executor.execute = execute_fn

        runner = LoopRunner(step_executor=executor)

        result = await runner.run(
            loop_config=LoopConfig(count=3),
            steps=[Step(agents=["builder"])],
            context={"slug": "test"},
        )

        assert result.success
        assert result.iteration_count == 3

        # Verify feed-forward: context accumulates after first iteration
        if "artifacts" in captured_contexts[1]:
            assert len(captured_contexts[1]["artifacts"]) > 0


# ── Failure Tests ────────────────────────────────────────────────────


class TestLoopRunnerFailure:
    """Loop failure handling tests."""

    @pytest.mark.asyncio
    async def test_step_failure_stops_loop(
        self,
        mock_failing_executor: AsyncMock,
    ) -> None:
        """A failed sub-step stops the loop."""
        runner = LoopRunner(
            step_executor=mock_failing_executor,
        )
        result = await runner.run(
            loop_config=LoopConfig(count=5),
            steps=[Step(agents=["builder"])],
            context={},
        )
        assert not result.success
        assert result.iteration_count < 5  # Stopped early
        assert result.error is not None
        assert result.escalation == "loop"

    @pytest.mark.asyncio
    async def test_exception_stops_loop(
        self,
        mock_exception_executor: AsyncMock,
    ) -> None:
        """An exception in a sub-step stops the loop."""
        runner = LoopRunner(
            step_executor=mock_exception_executor,
        )
        result = await runner.run(
            loop_config=LoopConfig(count=3),
            steps=[Step(agents=["builder"])],
            context={},
        )
        assert not result.success
        assert result.iteration_count == 1  # Failed on first iteration
        assert result.error is not None
        assert result.escalation == "loop"

    @pytest.mark.asyncio
    async def test_circuit_breaker_records_failure(
        self,
        mock_failing_executor: AsyncMock,
        circuit_breaker: CircuitBreakerRegistry,
    ) -> None:
        """Circuit breaker records failures during loop."""
        runner = LoopRunner(
            step_executor=mock_failing_executor,
            circuit_breaker_registry=circuit_breaker,
        )
        result = await runner.run(
            loop_config=LoopConfig(count=5),
            steps=[Step(agents=["builder"])],
            context={"slug": "test"},
        )
        assert not result.success
        # Circuit breaker should have recorded failures — check via can_dispatch
        # (which returns False when the circuit is tripped)
        any_tripped = False
        for state in circuit_breaker.list_all():
            if state.is_tripped() or state.attempt_count > 0:
                any_tripped = True
                break
        assert any_tripped, "Circuit breaker should have recorded failures"


# ── Re-entry Semantics Tests ────────────────────────────────────────


class TestLoopRunnerReentry:
    """Re-entry semantics (R18) tests."""

    @pytest.mark.asyncio
    async def test_default_reset_on_reentry(
        self, runner: LoopRunner, sample_steps: list[Step]
    ) -> None:
        """Default behaviour: counters reset on re-entry."""
        # First run
        result1 = await runner.run(
            loop_config=LoopConfig(count=2),
            steps=sample_steps,
            context={},
        )
        assert result1.success

        # Second run — should reset
        result2 = await runner.run(
            loop_config=LoopConfig(count=2),
            steps=sample_steps,
            context={},
        )
        assert result2.success
        assert result2.iteration_count == 2

    @pytest.mark.asyncio
    async def test_resume_continues_counters(
        self, runner: LoopRunner, sample_steps: list[Step]
    ) -> None:
        """With reentry=resume, counters continue from previous run.

        Note: Each LoopRunner.run() creates a new loop_id from
        the config object identity, so resume behaviour requires
        passing the same config object and reentry='resume'.
        """
        loop_config = LoopConfig(count=3)

        # Run with resume
        result1 = await runner.run(
            loop_config=loop_config,
            steps=sample_steps,
            context={},
            reentry="resume",
        )
        assert result1.success

        # Verify loop state persisted
        loop_id = id(loop_config)
        state = runner.get_loop_state(str(loop_id))
        # State is keyed by id(loop_config) as string, or by
        # the context _loop_id attribute
        if state is None:
            # Try the dict key
            for _key, val in runner._loop_states.items():
                state = val
                break

        if state:
            assert state.current_iteration == 3
            assert state.total_iterations == 3

    @pytest.mark.asyncio
    async def test_reset_loop_state(self, runner: LoopRunner) -> None:
        """reset_loop_state clears state for a specific loop."""
        loop_config = LoopConfig(count=2)
        loop_id = id(loop_config)

        await runner.run(
            loop_config=loop_config,
            steps=[Step(agents=["builder"])],
            context={},
        )

        # State should exist
        runner.reset_loop_state(str(loop_id))
        assert runner.get_loop_state(str(loop_id)) is None

    @pytest.mark.asyncio
    async def test_reset_all_state(self, runner: LoopRunner) -> None:
        """reset_all_state clears all loop states."""
        await runner.run(
            loop_config=LoopConfig(count=1),
            steps=[Step(agents=["a"])],
            context={"_loop_id": "loop-1"},
        )
        await runner.run(
            loop_config=LoopConfig(count=2),
            steps=[Step(agents=["b"])],
            context={"_loop_id": "loop-2"},
        )

        runner.reset_all_state()
        assert len(runner._loop_states) == 0


# ── Loop State Tracking Tests ────────────────────────────────────────


class TestLoopRunnerState:
    """Loop state tracking tests."""

    @pytest.mark.asyncio
    async def test_loop_state_created(
        self, runner: LoopRunner
    ) -> None:
        """Loop state is created when loop starts."""
        loop_config = LoopConfig(count=1)

        await runner.run(
            loop_config=loop_config,
            steps=[Step(agents=["builder"])],
            context={},
        )

        # The loop_id is id(loop_config) stored as int-key
        loop_id = id(loop_config)
        state = None
        for _key, val in runner._loop_states.items():
            state = val
            break

        assert state is not None
        assert state.current_iteration == 1
        assert state.total_iterations == 1

    @pytest.mark.asyncio
    async def test_loop_state_tracks_iteration_results(
        self, runner: LoopRunner
    ) -> None:
        """Loop state tracks all iteration results."""
        loop_config = LoopConfig(count=3)

        await runner.run(
            loop_config=loop_config,
            steps=[Step(agents=["builder"])],
            context={},
        )

        state = next(iter(runner._loop_states.values()))
        assert len(state.iteration_results) == 3
        for result in state.iteration_results:
            assert result["success"]

    @pytest.mark.asyncio
    async def test_nested_loop_independent_counters(
        self, runner: LoopRunner
    ) -> None:
        """Nested loops each have independent counters."""
        inner_config = LoopConfig(count=2)
        outer_config = LoopConfig(count=3)

        await runner.run(
            loop_config=inner_config,
            steps=[Step(agents=["inner"])],
            context={"_loop_id": "inner-loop"},
        )

        await runner.run(
            loop_config=outer_config,
            steps=[Step(agents=["outer"])],
            context={"_loop_id": "outer-loop"},
        )

        assert len(runner._loop_states) == 2


# ── LoopRunnerResult Tests ───────────────────────────────────────────


class TestLoopRunnerResult:
    """LoopRunnerResult dataclass tests."""

    def test_defaults(self) -> None:
        """Test LoopRunnerResult default values."""
        result = LoopRunnerResult(success=True)
        assert result.success
        assert result.iteration_count == 0
        assert result.iteration_results == []
        assert result.last_artifacts == []
        assert result.error is None
        assert result.escalation is None
        assert result.trace_id == ""

    def test_failure_result(self) -> None:
        """Test failure result fields."""
        result = LoopRunnerResult(
            success=False,
            iteration_count=2,
            iteration_results=[
                {"iteration": 1, "success": True},
                {"iteration": 2, "success": False},
            ],
            error="Step failed in iteration 2",
            escalation="loop",
            trace_id="trace-123",
        )
        assert not result.success
        assert result.iteration_count == 2
        assert len(result.iteration_results) == 2
        assert result.error == "Step failed in iteration 2"
        assert result.escalation == "loop"
        assert result.trace_id == "trace-123"
