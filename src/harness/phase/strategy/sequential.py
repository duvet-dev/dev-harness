"""SequentialPhaseStrategy — default phase execution — V7 §5.5.

Iterates steps in order, dispatching each via StepDispatcher.
Artifact outputs from one step feed as inputs to the next.

This is the default strategy used when a phase does not specify
parallel execution.

See V7 §5.5 for the design and §5.3 for StepDispatcher integration.
"""

from __future__ import annotations

from typing import Any

from harness.artifact.repository import Artifact
from harness.phase.dispatcher import StepDispatcher, StepResult
from harness.phase.model import Phase, Step
from harness.phase.strategy.base import PhaseResult, PhaseStrategy, PhaseStrategyError
from harness.tracing import TraceLogger

logger = TraceLogger("harness.phase.strategy.sequential")


class SequentialPhaseStrategy(PhaseStrategy):
    """Executes phase steps sequentially, in order.

    Each step is dispatched one at a time. Artifact outputs from
    completed steps are accumulated and available as context for
    subsequent steps.

    Usage::

        strategy = SequentialPhaseStrategy(dispatcher=step_dispatcher)
        result = await strategy.execute(phase, context)
    """

    def __init__(
        self,
        dispatcher: StepDispatcher,
    ) -> None:
        """Initialise the sequential strategy.

        Args:
            dispatcher: StepDispatcher for dispatching individual
                steps to agents.
        """
        self._dispatcher = dispatcher

    async def execute(
        self,
        phase: Phase,
        context: Any | None = None,
    ) -> PhaseResult:
        """Execute all steps in a phase sequentially.

        Iterates through each step in order, dispatches via
        StepDispatcher, and accumulates artifacts. If any step
        fails, the phase is marked as failed with escalation
        details.

        Args:
            phase: The Phase definition with ordered steps.
            context: Optional execution context (accumulated
                artifacts from previous steps are merged into
                context for subsequent steps).

        Returns:
            PhaseResult with per-step results and overall status.
        """
        if not phase.steps:
            logger.warning(
                "SequentialPhaseStrategy — no steps in phase",
                extra={"phase": phase.name},
            )
            return PhaseResult(success=True, step_results=[])

        step_results: list[dict[str, Any]] = []
        accumulated_artifacts: list[Artifact] = []

        for i, step in enumerate(phase.steps):
            step_context = self._build_step_context(
                context, accumulated_artifacts
            )

            step_name = self._step_display_name(step, i)

            try:
                result: StepResult = await self._dispatcher.dispatch(
                    step=step,
                    context=step_context,
                )
            except PhaseStrategyError:
                raise
            except Exception as e:
                logger.error(
                    "SequentialPhaseStrategy — dispatch error",
                    extra={
                        "phase": phase.name,
                        "step_index": i,
                        "error": str(e),
                    },
                )
                return PhaseResult(
                    success=False,
                    step_results=step_results,
                    error=f"Step {i} dispatch failed: {e}",
                    partial=bool(step_results),
                    escalation="phase",
                )

            step_entry = {
                "step_name": step_name,
                "step_index": i,
                "success": result.success,
                "artifacts": result.artifacts,
                "error": result.error,
                "dissenting_notes": result.dissenting_notes,
            }
            step_results.append(step_entry)

            if result.success and result.artifacts:
                accumulated_artifacts.extend(result.artifacts)

            if not result.success:
                logger.warning(
                    "SequentialPhaseStrategy — step failed",
                    extra={
                        "phase": phase.name,
                        "step_index": i,
                        "error": result.error,
                    },
                )
                partial = any(
                    prev.get("success", False)
                    for prev in step_results[:-1]
                )
                return PhaseResult(
                    success=False,
                    step_results=step_results,
                    error=(
                        result.error
                        or f"Step '{step_name}' failed without error message"
                    ),
                    partial=partial,
                    escalation="phase",
                )

        logger.info(
            "SequentialPhaseStrategy — phase complete",
            extra={
                "phase": phase.name,
                "steps": len(step_results),
                "success": True,
            },
        )

        return PhaseResult(
            success=True,
            step_results=step_results,
        )

    def _build_step_context(
        self,
        context: Any | None,
        artifacts: list[Artifact],
    ) -> Any:
        """Build context for a step including accumulated artifacts.

        Merges accumulated artifacts into the step's context so
        outputs from earlier steps are available as inputs.
        Returns a copy of the artifacts list to avoid aliasing
        with the running accumulated_artifacts list.

        Args:
            context: Original execution context.
            artifacts: Accumulated artifacts from prior steps.

        Returns:
            Context dict with accumulated artifacts if available.
        """
        if not artifacts:
            return context
        if context is None:
            return {"accumulated_artifacts": list(artifacts)}
        if isinstance(context, dict):
            return {
                **context,
                "accumulated_artifacts": (
                    list(context.get("accumulated_artifacts", []))
                    + list(artifacts)
                ),
            }
        return context

    def _step_display_name(self, step: Step, index: int) -> str:
        """Produce a human-readable display name for a step.

        Args:
            step: The Step to name.
            index: The step's index in the phase.

        Returns:
            A display string like "step_0" or "step_3".
        """
        return f"step_{index}"
