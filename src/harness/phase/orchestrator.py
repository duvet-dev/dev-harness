"""PhaseOrchestrator — phase lifecycle management — V7 §5.4.

Manages entering/exiting phases, selecting the right strategy, and
the phase lifecycle (enter → execute → complete → determine next).

Coordinates with StrategyRunner to execute phase steps and with
CircuitBreakerRegistry for iteration failure handling (V7 §5.8).

See V7 §5.4 for full specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.phase.circuit_breaker import CircuitBreakerRegistry
from harness.phase.model import Phase
from harness.phase.state_manager import PhaseStateManager
from harness.phase.strategy.base import PhaseResult, PhaseStrategyError
from harness.phase.strategy.runner import StrategyRunner
from harness.tracing import TraceLogger

logger = TraceLogger("harness.phase.orchestrator")


@dataclass
class PhaseOrchestratorResult:
    """Result of orchestrating a phase.

    Attributes:
        success: True if the phase completed successfully.
        phase_result: The PhaseResult from strategy execution.
        phase_name: Name of the phase that was executed.
        next_phase: Name of the next phase to execute, if any.
            Determined by the orchestrator based on phase lifecycle.
        error: Error message if orchestration failed.
        escalation: Escalation target if phase failed
            ("loop", "phase", "workflow", or None).
        trace_id: Trace ID for structured logging.
    """

    success: bool
    phase_result: PhaseResult | None = None
    phase_name: str = ""
    next_phase: str | None = None
    error: str | None = None
    escalation: str | None = None
    trace_id: str = ""


class PhaseOrchestrator:
    """Orchestrates phase lifecycle from enter to completion.

    Manages:
    - Entering a phase (enter → execute → complete → next)
    - Strategy selection via StrategyRunner
    - Step failure handling with escalation chain
    - Phase state tracking via PhaseStateManager

    Usage::

        orchestrator = PhaseOrchestrator(
            strategy_runner=StrategyRunner(...),
            state_manager=PhaseStateManager(),
        )
        result = await orchestrator.enter_phase(
            "my-workflow.sprint-1",
            "design",
            mode="auto",
        )
    """

    def __init__(
        self,
        strategy_runner: StrategyRunner,
        state_manager: PhaseStateManager | None = None,
        circuit_breaker_registry: CircuitBreakerRegistry | None = None,
    ) -> None:
        """Initialise the PhaseOrchestrator.

        Args:
            strategy_runner: StrategyRunner for dispatching phase
                steps via the appropriate strategy.
            state_manager: Optional PhaseStateManager for tracking
                phase state. Created with defaults if not provided.
            circuit_breaker_registry: Optional registry for per-step
                circuit breakers. Created with defaults if not
                provided.
        """
        self._strategy_runner = strategy_runner
        self._state_manager = state_manager or PhaseStateManager()
        self._circuit_breaker_registry = (
            circuit_breaker_registry or CircuitBreakerRegistry()
        )
        self._phases: dict[str, Phase] = {}
        self._phase_history: list[str] = []

    def register_phase(self, phase: Phase) -> None:
        """Register a phase definition with the orchestrator.

        Phases must be registered before they can be entered or
        run.

        Args:
            phase: The Phase definition to register.
        """
        self._phases[phase.name] = phase
        logger.debug(
            "PhaseOrchestrator — phase registered",
            extra={"phase": phase.name},
        )

    def register_phases(self, phases: list[Phase]) -> None:
        """Register multiple phase definitions at once.

        Args:
            phases: List of Phase definitions to register.
        """
        for phase in phases:
            self.register_phase(phase)

    async def enter_phase(
        self,
        slug: str,
        phase_name: str,
        mode: str = "auto",
    ) -> PhaseOrchestratorResult:
        """Enter a named phase and execute it.

        The phase lifecycle: enter → execute → complete →
        determine next.

        Args:
            slug: Workflow slug for traceability
                (e.g. "my-workflow.sprint-1").
            phase_name: Name of the phase to enter (must be
                registered).
            mode: Execution mode ("auto" or "manual"). Defaults
                to "auto".

        Returns:
            PhaseOrchestratorResult with execution status and
            next phase suggestion.

        Raises:
            ValueError: If the phase is not registered.
        """
        phase = self._phases.get(phase_name)
        if phase is None:
            logger.error(
                "PhaseOrchestrator — unknown phase",
                extra={
                    "slug": slug,
                    "phase_name": phase_name,
                },
            )
            return PhaseOrchestratorResult(
                success=False,
                error=f"Unknown phase: '{phase_name}'",
                phase_name=phase_name,
                escalation="workflow",
            )

        logger.info(
            "PhaseOrchestrator — entering phase",
            extra={
                "slug": slug,
                "phase_name": phase_name,
                "mode": mode,
                "steps": len(phase.steps),
            },
        )

        # Record phase entry in history
        self._phase_history.append(phase_name)

        # Set phase state: entering
        self._state_manager.set_state(
            phase_name, "status", "entering"
        )
        self._state_manager.set_state(
            phase_name, "mode", mode
        )
        self._state_manager.set_state(
            phase_name, "slug", slug
        )

        # Execute the phase
        result = await self.run_phase(phase)

        # Update phase state based on result
        status = "completed" if result.success else "failed"
        self._state_manager.set_state(
            phase_name, "status", status
        )
        self._state_manager.set_state(
            phase_name, "result", result
        )

        # Determine next phase based on re-entry semantics and result
        next_phase = self._determine_next_phase(phase, result)

        logger.info(
            "PhaseOrchestrator — phase complete",
            extra={
                "phase_name": phase_name,
                "success": result.success,
                "next_phase": next_phase,
                "status": status,
            },
        )

        return PhaseOrchestratorResult(
            success=result.success,
            phase_result=result,
            phase_name=phase_name,
            next_phase=next_phase,
            error=result.error,
            escalation=result.escalation,
        )

    async def run_phase(
        self,
        phase: Phase,
        context: Any | None = None,
    ) -> PhaseResult:
        """Execute all steps in a phase via the StrategyRunner.

        Wraps strategy execution with circuit breaker checks and
        error handling.

        Args:
            phase: The Phase definition to execute.
            context: Optional execution context.

        Returns:
            PhaseResult with execution status and step results.
        """
        self._state_manager.set_state(
            phase.name, "status", "executing"
        )

        try:
            result = await self._strategy_runner.run(
                phase=phase,
                context=context,
            )
        except PhaseStrategyError as e:
            logger.error(
                "PhaseOrchestrator — strategy error",
                extra={
                    "phase": phase.name,
                    "error": str(e),
                },
            )
            return PhaseResult(
                success=False,
                error=f"Strategy error: {e}",
                escalation="workflow",
            )
        except Exception as e:
            logger.error(
                "PhaseOrchestrator — unexpected error",
                extra={
                    "phase": phase.name,
                    "error": str(e),
                },
            )
            return PhaseResult(
                success=False,
                error=f"Unexpected orchestration error: {e}",
                escalation="workflow",
            )

        # Apply circuit breaker logic for failed steps
        if not result.success and result.step_results:
            for step_entry in result.step_results:
                if not step_entry.get("success", True):
                    step_key = (
                        f"{phase.name}.{step_entry.get('step_name', 'unknown')}"
                    )
                    tripped = self._circuit_breaker_registry.record_failure(
                        step_key
                    )
                    if tripped:
                        result.escalation = (
                            self._circuit_breaker_registry.determine_escalation(
                                step_key
                            )
                        )
                        logger.warning(
                            "PhaseOrchestrator — circuit tripped",
                            extra={
                                "step_key": step_key,
                                "escalation": result.escalation,
                            },
                        )

        return result

    async def get_phase_status(self, phase_name: str) -> str | None:
        """Get the status of a phase.

        Args:
            phase_name: Name of the phase.

        Returns:
            Status string ("entering", "executing", "completed",
            "failed"), or None if the phase has no stored state.
        """
        return self._state_manager.get_state(phase_name, "status")

    def list_registered_phases(self) -> list[str]:
        """List all registered phase names.

        Returns:
            List of registered phase names.
        """
        return list(self._phases.keys())

    def get_phase_history(self) -> list[str]:
        """Get the ordered list of phases entered.

        Returns:
            List of phase names in entry order.
        """
        return list(self._phase_history)

    def _determine_next_phase(
        self,
        phase: Phase,
        result: PhaseResult,
    ) -> str | None:
        """Determine the next phase based on re-entry semantics.

        Args:
            phase: The completed Phase definition.
            result: The execution result.

        Returns:
            Next phase name if re-entry is specified and phase
            failed, or None.
        """
        if result.success:
            return None

        if phase.reentry == "restart":
            return phase.name
        elif phase.reentry == "resume":
            # Resume would retry failed steps — return same phase
            return phase.name

        return None
