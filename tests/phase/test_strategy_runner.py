"""Tests for phase/strategy/runner.py: StrategyRunner.

Tests cover:
- Sequential strategy selection by default
- Parallel strategy selection when steps have parallel flag
- Fallback to sequential when parallel not available
- Error handling during strategy execution
- Empty phase handling
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from harness.phase.model import Phase, Step
from harness.phase.strategy.base import PhaseResult, PhaseStrategyError
from harness.phase.strategy.parallel import ParallelPhaseStrategy
from harness.phase.strategy.runner import StrategyRunner
from harness.phase.strategy.sequential import SequentialPhaseStrategy


class TestStrategyRunner:
    """StrategyRunner tests."""

    @pytest.fixture
    def sequential(self) -> AsyncMock:
        """Create a mock sequential strategy."""
        mock = AsyncMock(spec=SequentialPhaseStrategy)
        mock.execute = AsyncMock(
            return_value=PhaseResult(success=True)
        )
        return mock

    @pytest.fixture
    def parallel(self) -> AsyncMock:
        """Create a mock parallel strategy."""
        mock = AsyncMock(spec=ParallelPhaseStrategy)
        mock.execute = AsyncMock(
            return_value=PhaseResult(success=True)
        )
        return mock

    def make_phase(self, steps: list[Step], name: str = "test-phase") -> Phase:
        """Helper to create a Phase."""
        return Phase(
            name=name,
            lead_agent="lead",
            chat_agent="chat",
            steps=steps,
        )

    @pytest.mark.asyncio
    async def test_sequential_selected_by_default(
        self, sequential: AsyncMock, parallel: AsyncMock
    ) -> None:
        """Sequential strategy is used for non-parallel steps."""
        runner = StrategyRunner(
            sequential=sequential,
            parallel=parallel,
        )
        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
        )

        await runner.run(phase)

        sequential.execute.assert_called_once_with(
            phase=phase, context=None
        )
        parallel.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_parallel_selected_when_parallel(
        self, sequential: AsyncMock, parallel: AsyncMock
    ) -> None:
        """Parallel strategy is used when steps have parallel flag."""
        runner = StrategyRunner(
            sequential=sequential,
            parallel=parallel,
        )
        phase = self.make_phase(
            steps=[
                Step(agents=["architect", "critic"], parallel=True),
            ],
        )

        await runner.run(phase)

        parallel.execute.assert_called_once_with(
            phase=phase, context=None
        )
        sequential.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_to_sequential_when_no_parallel(
        self, sequential: AsyncMock
    ) -> None:
        """Falls back to sequential when parallel strategy is None."""
        runner = StrategyRunner(
            sequential=sequential,
            parallel=None,
        )
        phase = self.make_phase(
            steps=[
                Step(agents=["architect", "critic"], parallel=True),
            ],
        )

        await runner.run(phase)

        sequential.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execution_error_returns_failure_with_escalation(
        self, sequential: AsyncMock
    ) -> None:
        """Strategy execution error returns failure with workflow escalation."""
        sequential.execute.side_effect = RuntimeError(
            "Strategy crashed"
        )

        runner = StrategyRunner(
            sequential=sequential,
        )
        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
        )

        result = await runner.run(phase)

        assert result.success is False
        assert "Strategy crashed" in (result.error or "")
        assert result.escalation == "workflow"

    @pytest.mark.asyncio
    async def test_phase_strategy_error_propagates(
        self, sequential: AsyncMock
    ) -> None:
        """PhaseStrategyError is propagated (not caught)."""
        sequential.execute.side_effect = PhaseStrategyError(
            "Invalid configuration"
        )

        runner = StrategyRunner(
            sequential=sequential,
        )
        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
        )

        with pytest.raises(PhaseStrategyError):
            await runner.run(phase)

    @pytest.mark.asyncio
    async def test_sequential_strategy_returned(
        self, sequential: AsyncMock, parallel: AsyncMock
    ) -> None:
        """Runner returns the PhaseResult from the strategy."""
        expected_result = PhaseResult(
            success=True,
            step_results=[{"step_name": "step_0", "success": True}],
        )
        sequential.execute.return_value = expected_result

        runner = StrategyRunner(
            sequential=sequential,
            parallel=parallel,
        )
        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
        )

        result = await runner.run(phase)

        assert result is expected_result
        assert result.success is True

    @pytest.mark.asyncio
    async def test_context_passed_to_strategy(
        self, sequential: AsyncMock, parallel: AsyncMock
    ) -> None:
        """Context is forwarded to the strategy."""
        runner = StrategyRunner(
            sequential=sequential,
            parallel=parallel,
        )
        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
        )

        test_context = {"user": "test-user", "session": "s1"}
        await runner.run(phase, context=test_context)

        sequential.execute.assert_called_once_with(
            phase=phase, context=test_context
        )
