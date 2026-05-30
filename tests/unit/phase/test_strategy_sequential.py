"""Tests for phase/strategy/sequential.py: SequentialPhaseStrategy.

Tests cover:
- Sequential execution of steps
- Artifact accumulation across steps
- Failure handling (step fails → phase fails)
- Empty phase (no steps)
- Context building with accumulated artifacts
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from harness.artifact.repository import Artifact
from harness.artifact.types import ArtifactType
from harness.phase.dispatcher import StepDispatcher, StepResult
from harness.phase.model import LoopConfig, Phase, Step
from harness.phase.strategy.sequential import SequentialPhaseStrategy


class TestSequentialPhaseStrategy:
    """SequentialPhaseStrategy tests."""

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
        strategy = SequentialPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(steps=[])

        result = await strategy.execute(phase)

        assert result.success is True
        assert result.step_results == []
        assert result.error is None
        mock_dispatcher.dispatch.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_single_step_success(
        self, mock_dispatcher: AsyncMock
    ) -> None:
        """Single step executing successfully."""
        mock_dispatcher.dispatch.return_value = StepResult(
            success=True,
            artifacts=[
                Artifact(type=ArtifactType.SUMMARY, content="Output 1",
                         path="step_0.md"),
            ],
        )

        strategy = SequentialPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(
            steps=[
                Step(agents=["architect"], action="Design review"),
            ],
        )

        result = await strategy.execute(phase)

        assert result.success is True
        assert len(result.step_results) == 1
        assert result.step_results[0]["success"] is True
        assert result.step_results[0]["step_name"] == "step_0"
        assert len(result.step_results[0]["artifacts"]) == 1
        mock_dispatcher.dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_multiple_steps_sequential(
        self, mock_dispatcher: AsyncMock
    ) -> None:
        """Steps are executed in order."""
        mock_dispatcher.dispatch = AsyncMock(
            side_effect=[
                StepResult(
                    success=True,
                    artifacts=[Artifact(type=ArtifactType.SUMMARY,
                                        content=f"Output {i}",
                                        path=f"step_{i}.md")],
                )
                for i in range(3)
            ],
        )

        strategy = SequentialPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(
            steps=[
                Step(agents=["architect"]),
                Step(agents=["tester"]),
                Step(agents=["coder"]),
            ],
        )

        result = await strategy.execute(phase)

        assert result.success is True
        assert len(result.step_results) == 3
        assert result.step_results[0]["step_name"] == "step_0"
        assert result.step_results[1]["step_name"] == "step_1"
        assert result.step_results[2]["step_name"] == "step_2"
        assert mock_dispatcher.dispatch.call_count == 3

    @pytest.mark.asyncio
    async def test_step_failure_stops_execution(
        self, mock_dispatcher: AsyncMock
    ) -> None:
        """Step failure stops execution and returns failure."""
        mock_dispatcher.dispatch = AsyncMock(
            side_effect=[
                StepResult(
                    success=True,
                    artifacts=[Artifact(type=ArtifactType.SUMMARY,
                                        content="Step 0", path="step_0.md")],
                ),
                StepResult(
                    success=False,
                    error="Agent timeout",
                ),
            ],
        )

        strategy = SequentialPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(
            steps=[
                Step(agents=["architect"]),
                Step(agents=["tester"]),
                Step(agents=["coder"]),
            ],
        )

        result = await strategy.execute(phase)

        assert result.success is False
        assert result.error == "Agent timeout"
        assert result.partial is True
        assert len(result.step_results) == 2
        # Third step should not have been dispatched
        assert mock_dispatcher.dispatch.call_count == 2

    @pytest.mark.asyncio
    async def test_step_failure_no_prior_success(
        self, mock_dispatcher: AsyncMock
    ) -> None:
        """Failure on first step — no partial flag."""
        mock_dispatcher.dispatch.return_value = StepResult(
            success=False,
            error="First step failed",
        )

        strategy = SequentialPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
        )

        result = await strategy.execute(phase)

        assert result.success is False
        assert result.partial is False
        assert len(result.step_results) == 1

    @pytest.mark.asyncio
    async def test_artifact_accumulation(
        self, mock_dispatcher: AsyncMock
    ) -> None:
        """Artifacts from earlier steps are accumulated in context."""
        artifacts_step0 = [
            Artifact(type=ArtifactType.PLANNING_DOC, content="Plan",
                     path="plan.md"),
        ]
        artifacts_step1 = [
            Artifact(type=ArtifactType.IMPLEMENTATION, content="Code",
                     path="code.md"),
        ]

        mock_dispatcher.dispatch = AsyncMock(
            side_effect=[
                StepResult(success=True, artifacts=artifacts_step0),
                StepResult(success=True, artifacts=artifacts_step1),
            ],
        )

        strategy = SequentialPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(
            steps=[
                Step(agents=["architect"]),
                Step(agents=["coder"]),
            ],
        )

        result = await strategy.execute(phase)

        assert result.success is True
        assert len(result.step_results) == 2

        # Check that context was built with accumulated artifacts
        # for the second dispatch call
        second_call_args = mock_dispatcher.dispatch.call_args_list[1]
        context_arg = second_call_args.kwargs.get("context", {})
        assert "accumulated_artifacts" in context_arg
        assert len(context_arg["accumulated_artifacts"]) == 1

    @pytest.mark.asyncio
    async def test_dispatch_exception_handling(
        self, mock_dispatcher: AsyncMock
    ) -> None:
        """Exception from dispatcher is caught and returned as failure."""
        mock_dispatcher.dispatch.side_effect = RuntimeError(
            "Dispatch connection lost"
        )

        strategy = SequentialPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
        )

        result = await strategy.execute(phase)

        assert result.success is False
        assert "Dispatch connection lost" in (result.error or "")
        assert result.escalation == "phase"

    @pytest.mark.asyncio
    async def test_step_display_name(self, mock_dispatcher: AsyncMock) -> None:
        """Step display names are correctly generated."""
        mock_dispatcher.dispatch.return_value = StepResult(success=True)

        strategy = SequentialPhaseStrategy(dispatcher=mock_dispatcher)
        phase = self.make_phase(
            steps=[
                Step(agents=["a"]),
                Step(agents=["b"]),
                Step(team="my-team"),
                Step(loop=LoopConfig(count=2)),
            ],
        )

        result = await strategy.execute(phase)

        assert result.success is True
        assert result.step_results[0]["step_name"] == "step_0"
        assert result.step_results[1]["step_name"] == "step_1"
        assert result.step_results[2]["step_name"] == "step_2"
        assert result.step_results[3]["step_name"] == "step_3"
