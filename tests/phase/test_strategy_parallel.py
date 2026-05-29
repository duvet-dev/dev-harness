"""Tests for phase/strategy/parallel.py: ParallelPhaseStrategy.

Tests cover:
- Parallel batch execution
- Mixed parallel/sequential step batching
- Failure handling in parallel batches
- Empty phase
- Single step dispatch
- Batch grouping logic
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from harness.artifact.repository import Artifact
from harness.artifact.types import ArtifactType
from harness.phase.dispatcher import StepDispatcher, StepResult
from harness.phase.model import Phase, Step
from harness.phase.strategy.parallel import ParallelPhaseStrategy


class TestParallelPhaseStrategy:
    """ParallelPhaseStrategy tests."""

    @pytest.fixture
    def mock_dispatcher(self) -> AsyncMock:
        """Create a mock StepDispatcher."""
        dispatcher = AsyncMock(spec=StepDispatcher)
        dispatcher.dispatch = AsyncMock()
        return dispatcher

    def make_phase(self, steps: list[Step], name: str = "test-phase") -> Phase:
        """Helper to create a Phase with given steps."""
        return Phase(
            name=name,
            lead_agent="lead",
            chat_agent="chat",
            steps=steps,
        )

    @pytest.mark.asyncio
    async def test_execute_empty_phase(self, mock_dispatcher: AsyncMock) -> None:
        """Empty phase returns success with no step results."""
        strategy = ParallelPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(steps=[])

        result = await strategy.execute(phase)

        assert result.success is True
        assert result.step_results == []
        mock_dispatcher.dispatch.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_sequential_step(
        self, mock_dispatcher: AsyncMock
    ) -> None:
        """Single non-parallel step is dispatched once."""
        mock_dispatcher.dispatch.return_value = StepResult(
            success=True,
            artifacts=[
                Artifact(type=ArtifactType.SUMMARY, content="OK",
                         path="step.md"),
            ],
        )

        strategy = ParallelPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(
            steps=[Step(agents=["architect"], parallel=False)],
        )

        result = await strategy.execute(phase)

        assert result.success is True
        assert len(result.step_results) == 1
        mock_dispatcher.dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_single_parallel_step(
        self, mock_dispatcher: AsyncMock
    ) -> None:
        """Single parallel step is dispatched."""
        mock_dispatcher.dispatch.return_value = StepResult(
            success=True,
            artifacts=[
                Artifact(type=ArtifactType.SUMMARY, content="OK",
                         path="step.md"),
            ],
        )

        strategy = ParallelPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(
            steps=[Step(agents=["architect", "critic"], parallel=True)],
        )

        result = await strategy.execute(phase)

        assert result.success is True
        assert len(result.step_results) == 1
        mock_dispatcher.dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_parallel_batch_all_succeed(
        self, mock_dispatcher: AsyncMock
    ) -> None:
        """Multiple parallel steps all succeed."""
        mock_dispatcher.dispatch.return_value = StepResult(
            success=True,
            artifacts=[Artifact(type=ArtifactType.SUMMARY, content="OK",
                                path="step.md")],
        )

        strategy = ParallelPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(
            steps=[
                Step(agents=["architect"], parallel=True),
                Step(agents=["critic"], parallel=True),
                Step(agents=["security"], parallel=True),
            ],
        )

        result = await strategy.execute(phase)

        assert result.success is True
        assert len(result.step_results) == 3

    @pytest.mark.asyncio
    async def test_parallel_batch_one_fails(
        self, mock_dispatcher: AsyncMock
    ) -> None:
        """One parallel step failing causes overall failure."""
        dispatch_results = [
            StepResult(success=True, artifacts=[
                Artifact(type=ArtifactType.SUMMARY, content="OK",
                         path="step_0.md"),
            ]),
            StepResult(success=False, error="Critical failure"),
            StepResult(success=True, artifacts=[
                Artifact(type=ArtifactType.SUMMARY, content="OK",
                         path="step_2.md"),
            ]),
        ]

        async def side_effect(*args, **kwargs):
            return dispatch_results.pop(0)

        mock_dispatcher.dispatch = AsyncMock(side_effect=side_effect)

        strategy = ParallelPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(
            steps=[
                Step(agents=["a"], parallel=True),
                Step(agents=["b"], parallel=True),
                Step(agents=["c"], parallel=True),
            ],
        )

        result = await strategy.execute(phase)

        assert result.success is False
        assert result.partial is True
        assert "Critical failure" in (result.error or "")

    @pytest.mark.asyncio
    async def test_mixed_sequential_and_parallel(
        self, mock_dispatcher: AsyncMock
    ) -> None:
        """Mixed sequential and parallel steps are handled."""
        mock_dispatcher.dispatch.return_value = StepResult(
            success=True,
            artifacts=[Artifact(type=ArtifactType.SUMMARY, content="OK",
                                path="step.md")],
        )

        strategy = ParallelPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(
            steps=[
                Step(agents=["planning"]),  # sequential
                Step(agents=["architect", "critic"], parallel=True),
                Step(agents=["security", "compliance"], parallel=True),
                Step(agents=["tester"]),  # sequential
            ],
        )

        result = await strategy.execute(phase)

        assert result.success is True
        assert len(result.step_results) == 4

    def test_batch_steps_all_sequential(self) -> None:
        """All sequential steps each become their own batch."""
        strategy = ParallelPhaseStrategy(
            dispatcher=AsyncMock(spec=StepDispatcher),
        )
        steps = [
            Step(agents=["a"]),
            Step(agents=["b"]),
            Step(agents=["c"]),
        ]
        batches = strategy._batch_steps(steps)
        assert len(batches) == 3
        for batch in batches:
            assert len(batch) == 1

    def test_batch_steps_all_parallel(self) -> None:
        """All parallel steps become a single batch."""
        strategy = ParallelPhaseStrategy(
            dispatcher=AsyncMock(spec=StepDispatcher),
        )
        steps = [
            Step(agents=["a"], parallel=True),
            Step(agents=["b"], parallel=True),
            Step(agents=["c"], parallel=True),
        ]
        batches = strategy._batch_steps(steps)
        assert len(batches) == 1
        assert len(batches[0]) == 3

    def test_batch_steps_mixed(self) -> None:
        """Mixed steps produce correct batches."""
        strategy = ParallelPhaseStrategy(
            dispatcher=AsyncMock(spec=StepDispatcher),
        )
        steps = [
            Step(agents=["a"]),  # sequential batch 1
            Step(agents=["b"], parallel=True),  # parallel batch 2
            Step(agents=["c"], parallel=True),  # parallel batch 2
            Step(agents=["d"]),  # sequential batch 3
            Step(agents=["e"], parallel=True),  # parallel batch 4
            Step(agents=["f"]),  # sequential batch 5
        ]
        batches = strategy._batch_steps(steps)
        assert len(batches) == 5
        assert len(batches[0]) == 1  # [a] sequential
        assert len(batches[1]) == 2  # [b, c] parallel
        assert len(batches[2]) == 1  # [d] sequential
        assert len(batches[3]) == 1  # [e] parallel (single)
        assert len(batches[4]) == 1  # [f] sequential

    def test_batch_steps_empty(self) -> None:
        """Empty steps produce empty batches."""
        strategy = ParallelPhaseStrategy(
            dispatcher=AsyncMock(spec=StepDispatcher),
        )
        assert strategy._batch_steps([]) == []

    @pytest.mark.asyncio
    async def test_dispatch_exception_in_parallel_batch(
        self, mock_dispatcher: AsyncMock
    ) -> None:
        """Exception in parallel batch is caught and reported."""
        mock_dispatcher.dispatch.side_effect = RuntimeError(
            "Parallel dispatch failed"
        )

        strategy = ParallelPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(
            steps=[
                Step(agents=["a"], parallel=True),
                Step(agents=["b"], parallel=True),
            ],
        )

        result = await strategy.execute(phase)

        assert result.success is False
