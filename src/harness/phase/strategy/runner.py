"""StrategyRunner — selects and runs the appropriate strategy — V7 §5.5.

The StrategyRunner wraps strategy execution with error handling,
selecting the correct strategy (sequential/parallel) based on
phase configuration.

If a strategy selection fails, the StrategyRunner logs the error
and returns a PhaseResult with escalation set to "workflow" to
trigger the next escalation level (V7 §5.8).

See V7 §5.5 for the design.
"""

from __future__ import annotations

from typing import Any

from harness.phase.model import Phase
from harness.phase.strategy.base import PhaseResult, PhaseStrategy, PhaseStrategyError
from harness.phase.strategy.parallel import ParallelPhaseStrategy
from harness.phase.strategy.sequential import SequentialPhaseStrategy
from harness.tracing import TraceLogger

logger = TraceLogger("harness.phase.strategy.runner")


class StrategyRunner:
    """Selects and runs the appropriate phase execution strategy.

    Default strategy is SequentialPhaseStrategy. If the phase
    explicitly requests parallel, ParallelPhaseStrategy is used.

    Usage::

        runner = StrategyRunner(
            sequential=SequentialPhaseStrategy(dispatcher),
            parallel=ParallelPhaseStrategy(dispatcher),
        )
        result = await runner.run(phase, context)
    """

    def __init__(
        self,
        sequential: SequentialPhaseStrategy,
        parallel: ParallelPhaseStrategy | None = None,
    ) -> None:
        """Initialise the StrategyRunner.

        Args:
            sequential: The sequential strategy instance.
            parallel: Optional parallel strategy instance. If not
                provided, parallel requests fall back to sequential.
        """
        self._sequential = sequential
        self._parallel = parallel

    async def run(
        self,
        phase: Phase,
        context: Any | None = None,
    ) -> PhaseResult:
        """Run a phase using the appropriate strategy.

        Selects strategy based on phase configuration:
        - If any step has parallel=True and a parallel strategy is
          available, uses ParallelPhaseStrategy.
        - Otherwise uses SequentialPhaseStrategy.

        Args:
            phase: The Phase to execute.
            context: Optional execution context.

        Returns:
            PhaseResult from the executed strategy.

        Raises:
            PhaseStrategyError: If no valid strategy can be
                selected for the phase.
        """
        try:
            strategy = self._select_strategy(phase)
            logger.info(
                "StrategyRunner — selected strategy",
                extra={
                    "phase": phase.name,
                    "strategy": strategy.__class__.__name__,
                    "steps": len(phase.steps),
                },
            )
            return await strategy.execute(phase=phase, context=context)
        except PhaseStrategyError:
            raise
        except Exception as e:
            logger.error(
                "StrategyRunner — execution error",
                extra={
                    "phase": phase.name,
                    "error": str(e),
                },
            )
            return PhaseResult(
                success=False,
                error=f"Strategy execution error: {e}",
                escalation="workflow",
            )

    def _select_strategy(self, phase: Phase) -> PhaseStrategy:
        """Select the appropriate strategy for the given phase.

        If any step in the phase has parallel=True and a parallel
        strategy is available, uses parallel. Otherwise sequential.

        Args:
            phase: The Phase to select a strategy for.

        Returns:
            A PhaseStrategy instance.

        Raises:
            PhaseStrategyError: If parallel was requested but no
                parallel strategy is available.
        """
        has_parallel_steps = any(
            step.parallel for step in phase.steps
        )

        if has_parallel_steps:
            if self._parallel:
                return self._parallel
            logger.warning(
                "StrategyRunner — parallel requested but "
                "no parallel strategy available, falling back "
                "to sequential",
                extra={"phase": phase.name},
            )

        return self._sequential
