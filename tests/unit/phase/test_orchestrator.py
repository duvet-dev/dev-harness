"""Tests for phase/orchestrator.py: PhaseOrchestrator.

Tests cover:
- Phase registration and retrieval
- enter_phase with unknown phase
- enter_phase lifecycle (enter → execute → complete → next)
- run_phase with success and failure
- Circuit breaker integration
- Phase state tracking
- Phase history
- Re-entry semantics (restart, resume)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from harness.phase.circuit_breaker import CircuitBreakerRegistry
from harness.phase.model import Phase, Step
from harness.phase.orchestrator import PhaseOrchestrator
from harness.phase.state_manager import PhaseStateManager
from harness.phase.strategy.base import PhaseResult
from harness.phase.strategy.runner import StrategyRunner


class TestPhaseOrchestrator:
    """PhaseOrchestrator tests."""

    @pytest.fixture
    def mock_runner(self) -> AsyncMock:
        """Create a mock StrategyRunner."""
        runner = AsyncMock(spec=StrategyRunner)
        runner.run = AsyncMock(
            return_value=PhaseResult(success=True)
        )
        return runner

    @pytest.fixture
    def orchestrator(self, mock_runner: AsyncMock) -> PhaseOrchestrator:
        """Create PhaseOrchestrator with mock runner."""
        return PhaseOrchestrator(
            strategy_runner=mock_runner,
            state_manager=PhaseStateManager(),
            circuit_breaker_registry=CircuitBreakerRegistry(),
        )

    def make_phase(self, steps: list[Step], name: str = "test-phase",
                   reentry: str | None = None) -> Phase:
        """Helper to create a Phase."""
        return Phase(
            name=name,
            lead_agent="lead",
            chat_agent="chat",
            steps=steps,
            reentry=reentry,
        )

    def test_register_phase(self, orchestrator: PhaseOrchestrator) -> None:
        """A phase can be registered."""
        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
            name="design",
        )
        orchestrator.register_phase(phase)
        assert "design" in orchestrator.list_registered_phases()

    def test_register_phases_multiple(
        self, orchestrator: PhaseOrchestrator
    ) -> None:
        """Multiple phases can be registered at once."""
        phases = [
            self.make_phase(steps=[Step(agents=["a"])], name="design"),
            self.make_phase(steps=[Step(agents=["b"])], name="build"),
            self.make_phase(steps=[Step(agents=["c"])], name="test"),
        ]
        orchestrator.register_phases(phases)
        assert len(orchestrator.list_registered_phases()) == 3

    def test_list_registered_phases_empty(
        self, orchestrator: PhaseOrchestrator
    ) -> None:
        """Empty orchestrator has no registered phases."""
        assert orchestrator.list_registered_phases() == []

    @pytest.mark.asyncio
    async def test_enter_phase_unknown(
        self, orchestrator: PhaseOrchestrator
    ) -> None:
        """Unknown phase returns error with workflow escalation."""
        result = await orchestrator.enter_phase(
            slug="test-slug",
            phase_name="nonexistent",
        )
        assert result.success is False
        assert result.error == "Unknown phase: 'nonexistent'"
        assert result.escalation == "workflow"
        assert result.phase_name == "nonexistent"

    @pytest.mark.asyncio
    async def test_enter_phase_success(
        self, orchestrator: PhaseOrchestrator, mock_runner: AsyncMock
    ) -> None:
        """Phase enters, executes, and completes successfully."""
        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
            name="design",
        )
        orchestrator.register_phase(phase)

        result = await orchestrator.enter_phase(
            slug="test-slug",
            phase_name="design",
        )

        assert result.success is True
        assert result.phase_name == "design"
        assert result.next_phase is None  # No re-entry on success
        mock_runner.run.assert_called_once_with(
            phase=phase, context=None
        )

    @pytest.mark.asyncio
    async def test_enter_phase_tracks_history(
        self, orchestrator: PhaseOrchestrator
    ) -> None:
        """Phase entry is recorded in history."""
        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
            name="design",
        )
        orchestrator.register_phase(phase)

        await orchestrator.enter_phase("slug", "design")
        assert orchestrator.get_phase_history() == ["design"]

        phase2 = self.make_phase(
            steps=[Step(agents=["tester"])],
            name="test",
        )
        orchestrator.register_phase(phase2)
        await orchestrator.enter_phase("slug", "test")
        assert orchestrator.get_phase_history() == ["design", "test"]

    @pytest.mark.asyncio
    async def test_enter_phase_sets_state(
        self, orchestrator: PhaseOrchestrator
    ) -> None:
        """Phase state is tracked through the lifecycle."""
        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
            name="design",
        )
        orchestrator.register_phase(phase)

        await orchestrator.enter_phase("test-slug", "design", mode="auto")

        status = await orchestrator.get_phase_status("design")
        assert status == "completed"

    @pytest.mark.asyncio
    async def test_enter_phase_failure_state(
        self, orchestrator: PhaseOrchestrator, mock_runner: AsyncMock
    ) -> None:
        """Failed phase is tracked with 'failed' state."""
        mock_runner.run.return_value = PhaseResult(
            success=False,
            error="Design review failed",
        )

        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
            name="design",
        )
        orchestrator.register_phase(phase)

        result = await orchestrator.enter_phase("slug", "design")

        assert result.success is False
        assert result.error == "Design review failed"

        status = await orchestrator.get_phase_status("design")
        assert status == "failed"

    @pytest.mark.asyncio
    async def test_run_phase_success(
        self, orchestrator: PhaseOrchestrator, mock_runner: AsyncMock
    ) -> None:
        """run_phase returns successful PhaseResult."""
        mock_runner.run.return_value = PhaseResult(
            success=True,
            step_results=[{"step_name": "step_0", "success": True}],
        )

        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
            name="design",
        )

        result = await orchestrator.run_phase(phase)

        assert result.success is True
        assert len(result.step_results) == 1

    @pytest.mark.asyncio
    async def test_run_phase_failure(
        self, orchestrator: PhaseOrchestrator, mock_runner: AsyncMock
    ) -> None:
        """run_phase returns failed PhaseResult on strategy failure."""
        mock_runner.run.return_value = PhaseResult(
            success=False,
            error="Steps failed",
            escalation="phase",
        )

        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
            name="design",
        )

        result = await orchestrator.run_phase(phase)

        assert result.success is False
        assert result.error == "Steps failed"
        assert result.escalation == "phase"

    @pytest.mark.asyncio
    async def test_run_phase_exception(
        self, orchestrator: PhaseOrchestrator, mock_runner: AsyncMock
    ) -> None:
        """Exception in strategy execution is caught."""
        mock_runner.run.side_effect = RuntimeError("Strategy crashed")

        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
            name="design",
        )

        result = await orchestrator.run_phase(phase)

        assert result.success is False
        assert "Unexpected orchestration error" in (result.error or "")

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(
        self, orchestrator: PhaseOrchestrator, mock_runner: AsyncMock
    ) -> None:
        """Circuit breaker records failures from failed steps."""
        mock_runner.run.return_value = PhaseResult(
            success=False,
            step_results=[
                {"step_name": "step_0", "success": False,
                 "error": "Failed"},
            ],
            escalation="step",
        )

        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
            name="design",
        )

        result = await orchestrator.run_phase(phase)

        assert result.success is False
        # Circuit breaker should have recorded the failure
        cb = orchestrator._circuit_breaker_registry.get(
            "design.step_0"
        )
        assert cb is not None
        assert cb.attempt_count == 1

    @pytest.mark.asyncio
    async def test_enter_phase_with_reentry_restart(
        self, orchestrator: PhaseOrchestrator, mock_runner: AsyncMock
    ) -> None:
        """Re-entry='restart' returns next_phase on failure."""
        mock_runner.run.return_value = PhaseResult(
            success=False,
            error="Need retry",
        )

        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
            name="design",
            reentry="restart",
        )
        orchestrator.register_phase(phase)

        result = await orchestrator.enter_phase("slug", "design")

        assert result.success is False
        assert result.next_phase == "design"  # Re-entry

    @pytest.mark.asyncio
    async def test_no_reentry_on_success(
        self, orchestrator: PhaseOrchestrator, mock_runner: AsyncMock
    ) -> None:
        """Successful phase has no next_phase."""
        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
            name="design",
            reentry="restart",
        )
        orchestrator.register_phase(phase)

        result = await orchestrator.enter_phase("slug", "design")

        assert result.success is True
        assert result.next_phase is None

    @pytest.mark.asyncio
    async def test_enter_phase_with_context(
        self, orchestrator: PhaseOrchestrator, mock_runner: AsyncMock
    ) -> None:
        """Context is passed through to strategy runner."""
        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
            name="design",
        )
        orchestrator.register_phase(phase)

        context = {"session": "s1"}
        # enter_phase passes context to run_phase internally
        await orchestrator.enter_phase("slug", "design")

        mock_runner.run.assert_called_once_with(
            phase=phase, context=None
        )

    def test_get_phase_history_initial(
        self, orchestrator: PhaseOrchestrator
    ) -> None:
        """Initial phase history is empty."""
        assert orchestrator.get_phase_history() == []

    @pytest.mark.asyncio
    async def test_enter_phase_mode_parameter(
        self, orchestrator: PhaseOrchestrator
    ) -> None:
        """Mode parameter is stored in phase state."""
        phase = self.make_phase(
            steps=[Step(agents=["architect"])],
            name="design",
        )
        orchestrator.register_phase(phase)

        await orchestrator.enter_phase("slug", "design", mode="manual")

        mode = orchestrator._state_manager.get_state("design", "mode")
        assert mode == "manual"
