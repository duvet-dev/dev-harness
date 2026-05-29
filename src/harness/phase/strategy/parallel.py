"""ParallelPhaseStrategy — parallel step execution — V7 §5.5.

Dispatches all eligible steps at once, using the StepDispatcher's
parallel dispatch mode. The LeadAggregator handles merging results.

Only steps with parallel=True are dispatched in parallel; other
steps fall back to sequential dispatch internally.

See V7 §5.5 for the design and §6.3 for parallel dispatch protocol.
"""

from __future__ import annotations

import asyncio
from typing import Any

from harness.artifact.repository import Artifact
from harness.phase.dispatcher import StepDispatcher, StepResult
from harness.phase.model import Phase, Step
from harness.phase.strategy.base import PhaseResult, PhaseStrategy, PhaseStrategyError
from harness.tracing import TraceLogger

logger = TraceLogger("harness.phase.strategy.parallel")


class ParallelPhaseStrategy(PhaseStrategy):
    """Executes phase steps with parallel dispatch.

    Steps flagged with parallel=True are dispatched concurrently
    via StepDispatcher's parallel mode. Results are aggregated
    using the LeadAggregator.

    Usage::

        strategy = ParallelPhaseStrategy(dispatcher=step_dispatcher)
        result = await strategy.execute(phase, context)
    """

    def __init__(
        self,
        dispatcher: StepDispatcher,
    ) -> None:
        """Initialise the parallel strategy.

        Args:
            dispatcher: StepDispatcher for dispatching steps to
                agents (handles parallel dispatch internally).
        """
        self._dispatcher = dispatcher

    async def execute(
        self,
        phase: Phase,
        context: Any | None = None,
    ) -> PhaseResult:
        """Execute phase steps, parallelising flagged steps.

        Steps with parallel=True are dispatched simultaneously.
        All other steps are dispatched sequentially through the
        StepDispatcher (each step may itself be parallel internally).

        Args:
            phase: The Phase definition with ordered steps.
            context: Optional execution context.

        Returns:
            PhaseResult with per-step results and overall status.
        """
        if not phase.steps:
            logger.warning(
                "ParallelPhaseStrategy — no steps in phase",
                extra={"phase": phase.name},
            )
            return PhaseResult(success=True, step_results=[])

        step_results: list[dict[str, Any]] = []
        accumulated_artifacts: list[Artifact] = []

        # Group consecutive parallel steps into batches
        batches = self._batch_steps(phase.steps)

        for batch in batches:
            if batch[0].parallel and len(batch) > 1:
                batch_result = await self._execute_parallel_batch(
                    batch, phase, context
                )
                step_results.extend(batch_result)
                for entry in batch_result:
                    if entry["success"] and entry.get("artifacts"):
                        accumulated_artifacts.extend(entry["artifacts"])

                if any(not entry["success"] for entry in batch_result):
                    failed = [
                        e for e in batch_result if not e["success"]
                    ]
                    errors = "; ".join(
                        f"Step '{e['step_name']}': {e.get('error', 'unknown')}"
                        for e in failed
                    )
                    return PhaseResult(
                        success=False,
                        step_results=step_results,
                        error=errors[:200],
                        partial=bool(step_results),
                        escalation="phase",
                    )
            else:
                # Single step (parallel or sequential)
                step = batch[0]
                step_context = (
                    {"accumulated_artifacts": accumulated_artifacts}
                    if accumulated_artifacts
                    else context
                )
                entry = await self._dispatch_single_step(
                    step, phase, context
                )
                step_results.append(entry)
                if entry["success"] and entry.get("artifacts"):
                    accumulated_artifacts.extend(entry["artifacts"])
                if not entry["success"]:
                    return PhaseResult(
                        success=False,
                        step_results=step_results,
                        error=(
                            entry.get("error")
                            or f"Step '{entry['step_name']}' failed"
                        ),
                        partial=bool(step_results),
                        escalation="phase",
                    )

        logger.info(
            "ParallelPhaseStrategy — phase complete",
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

    async def _execute_parallel_batch(
        self,
        batch: list[Step],
        phase: Phase,
        context: Any | None,
    ) -> list[dict[str, Any]]:
        """Execute a batch of parallel steps concurrently.

        Each step is dispatched independently via StepDispatcher.
        Results are collected as they complete.

        Args:
            batch: List of steps to dispatch in parallel.
            phase: The parent phase.
            context: Execution context.

        Returns:
            List of step result dicts.
        """
        async def dispatch_step(step: Step, index: int) -> dict[str, Any]:
            step_context = context
            try:
                result = await self._dispatcher.dispatch(
                    step=step,
                    context=step_context,
                )
                return {
                    "step_name": f"step_{index}",
                    "step_index": index,
                    "success": result.success,
                    "artifacts": result.artifacts,
                    "error": result.error,
                    "dissenting_notes": result.dissenting_notes,
                }
            except Exception as e:
                return {
                    "step_name": f"step_{index}",
                    "step_index": index,
                    "success": False,
                    "artifacts": [],
                    "error": str(e),
                    "dissenting_notes": [],
                }

        tasks = []
        for i, step in enumerate(batch):
            tasks.append(dispatch_step(step, i))

        return await asyncio.gather(*tasks)

    async def _dispatch_single_step(
        self,
        step: Step,
        phase: Phase,
        context: Any | None,
    ) -> dict[str, Any]:
        """Dispatch a single step via StepDispatcher.

        Args:
            step: The step to dispatch.
            phase: The parent phase.
            context: Execution context.

        Returns:
            A step result dict.
        """
        try:
            result: StepResult = await self._dispatcher.dispatch(
                step=step,
                context=context,
            )
            return {
                "step_name": f"step_{step.step_type}",
                "step_index": 0,
                "success": result.success,
                "artifacts": result.artifacts,
                "error": result.error,
                "dissenting_notes": result.dissenting_notes,
            }
        except Exception as e:
            logger.error(
                "ParallelPhaseStrategy — dispatch error",
                extra={
                    "phase": phase.name,
                    "step_type": step.step_type,
                    "error": str(e),
                },
            )
            return {
                "step_name": f"step_{step.step_type}",
                "step_index": 0,
                "success": False,
                "artifacts": [],
                "error": str(e),
                "dissenting_notes": [],
            }

    def _batch_steps(self, steps: list[Step]) -> list[list[Step]]:
        """Group steps into sequential and parallel batches.

        Consecutive parallel steps are grouped into a single batch.
        Sequential steps are each their own batch.

        Args:
            steps: The ordered list of steps from the phase.

        Returns:
            List of batches (each a list of steps to execute together).
        """
        if not steps:
            return []

        batches: list[list[Step]] = []
        current_batch: list[Step] = []
        in_parallel = False

        for step in steps:
            if step.parallel:
                if not in_parallel:
                    if current_batch:
                        batches.append(current_batch)
                        current_batch = []
                    in_parallel = True
                current_batch.append(step)
            else:
                if in_parallel:
                    batches.append(current_batch)
                    current_batch = []
                    in_parallel = False
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                current_batch.append(step)
                batches.append(current_batch)
                current_batch = []

        if current_batch:
            batches.append(current_batch)

        return batches
