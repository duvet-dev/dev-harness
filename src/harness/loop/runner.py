"""LoopRunner — recursive loop step execution — V7 §5.2, R33.

Executes LoopConfig steps: runs a sequence of sub-steps ``count`` times,
feeding outputs from iteration N to iteration N+1. Supports re-entry
semantics (R18), loop counter tracking (per-loop, not global), and
circuit breaker escalation per iteration.

Escalation chain per iteration: iteration → loop → parent step.

Error classification: raises LoopExecutionError if the loop fails
entirely.

Usage::

    runner = LoopRunner(
        step_executor=step_executor,
        circuit_breaker_registry=circuit_breaker_registry,
    )
    result = await runner.run(
        loop_config=LoopConfig(count=3, description="Review cycle"),
        steps=[step1, step2],
        context=StepContext(slug="my-workflow", mode="auto"),
    )
    print(f"Iterations: {result.iteration_count}")
    print(f"Success: {result.success}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.errors import LoopExecutionError
from harness.loop.model import LoopState
from harness.phase.circuit_breaker import CircuitBreakerRegistry
from harness.phase.model import LoopConfig, Step
from harness.tracing import TraceLogger

logger = TraceLogger("harness.loop.runner")


@dataclass
class LoopRunnerResult:
    """Result of executing a loop step.

    Attributes:
        success: True if ALL iterations completed successfully.
        iteration_count: Number of iterations executed.
        iteration_results: Results from each iteration, in order.
        last_artifacts: Artifacts from the final iteration.
        error: Error message if the loop failed entirely.
        escalation: Escalation target ("iteration", "loop",
            "phase", "workflow", or None).
        trace_id: Trace ID for structured logging.
    """

    success: bool
    iteration_count: int = 0
    iteration_results: list[dict[str, Any]] = field(
        default_factory=list
    )
    last_artifacts: list[Any] = field(default_factory=list)
    error: str | None = None
    escalation: str | None = None
    trace_id: str = ""


class LoopRunner:
    """Executes loop steps by iterating over sub-steps.

    Each iteration executes the sub-steps in order. Outputs from
    iteration N are passed as inputs to iteration N+1 (feed-forward).

    Loop counters are tracked per-loop instance (not globally), so
    nested loops each have independent counters.

    Re-entry semantics (R18):
    - Default: counters reset on re-entry (fresh loop each time)
    - Override with ``reentry: resume`` — counters continue from
      previous run

    Failure handling:
    - Circuit breaker applies per iteration
    - Escalation: iteration → loop → parent step → phase → workflow
    - If circuit breaker trips mid-loop, remaining iterations are
      skipped and the loop reports the failure
    """

    def __init__(
        self,
        step_executor: Any | None = None,
        circuit_breaker_registry: CircuitBreakerRegistry | None = None,
        state_manager: Any | None = None,
    ) -> None:
        """Initialise the LoopRunner.

        Args:
            step_executor: StepExecutor for dispatching individual
                sub-steps within each iteration. If None, uses a
                stub that returns success (for testing).
            circuit_breaker_registry: Registry for per-step circuit
                breakers. Created with defaults if not provided.
            state_manager: Optional PhaseStateManager for tracking
                loop state across iterations.
        """
        self._step_executor = step_executor or self._stub_executor
        self._circuit_breaker_registry = (
            circuit_breaker_registry or CircuitBreakerRegistry()
        )
        self._state_manager = state_manager
        self._loop_states: dict[str, LoopState] = {}

    @staticmethod
    def _get_attr(
        obj: Any, attr: str, default: Any = ""
    ) -> Any:
        """Get attribute from dict or object."""
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    async def run(
        self,
        loop_config: LoopConfig,
        steps: list[Step],
        context: Any,
        reentry: str | None = None,
    ) -> LoopRunnerResult:
        """Execute a loop step.

        Args:
            loop_config: The loop configuration (count, description).
            steps: The sub-steps to execute in each iteration.
            context: Execution context with slug, mode, and
                accumulated artifacts.
            reentry: Re-entry semantics override. If "resume",
                counters continue from previous run. Otherwise
                counters reset.

        Returns:
            LoopRunnerResult with iteration results and status.
        """
        loop_id = self._get_attr(context, "_loop_id", None) or id(loop_config)
        trace_id = self._get_attr(context, "trace_id", "")

        # Re-entry handling (R18)
        loop_state = self._loop_states.get(loop_id)
        if loop_state is None or reentry != "resume":
            loop_state = LoopState()
            self._loop_states[loop_id] = loop_state

        logger.info(
            "LoopRunner.run — starting loop",
            extra={
                "loop_count": loop_config.count,
                "description": loop_config.description or "",
                "steps": len(steps),
                "reentry": reentry or "default",
                "iteration_start": loop_state.current_iteration + 1,
            },
        )

        iteration_results: list[dict[str, Any]] = []
        accumulated_context = context

        for iteration in range(
            loop_state.current_iteration + 1, loop_config.count + 1
        ):
            loop_state.current_iteration = iteration
            loop_state.total_iterations = loop_config.count

            logger.info(
                "LoopRunner — iteration",
                extra={
                    "iteration": iteration,
                    "total": loop_config.count,
                },
            )

            # Execute all sub-steps for this iteration
            iteration_artifacts = []
            iteration_success = True
            iteration_error: str | None = None

            for step_idx, step in enumerate(steps):
                step_key = (
                    f"loop.{self._get_attr(context, 'slug', 'unknown')}.{loop_id}.{iteration}.{step_idx}"
                )

                # Check circuit breaker before executing step
                if not self._circuit_breaker_registry.can_dispatch(
                    step_key
                ):
                    escalation = (
                        self._circuit_breaker_registry.determine_escalation(
                            step_key
                        )
                    )
                    logger.warning(
                        "LoopRunner — circuit tripped, skipping",
                        extra={
                            "step_key": step_key,
                            "escalation": escalation,
                        },
                    )
                    return LoopRunnerResult(
                        success=False,
                        iteration_count=iteration - 1,
                        iteration_results=iteration_results,
                        last_artifacts=[],
                        error=(
                            f"Circuit breaker tripped at iteration {iteration}, "
                            f"step {step_idx}"
                        ),
                        escalation=escalation,
                        trace_id=trace_id,
                    )

                try:
                    # Record loop metadata on context for tracing
                    if hasattr(accumulated_context, "_set_loop_metadata"):
                        accumulated_context.setdefault(
                            "_loop_metadata", {}
                        ).update(
                            {
                                "iteration": iteration,
                                "step_index": step_idx,
                                "total_iterations": loop_config.count,
                            }
                        )

                    step_result = await self._step_executor.execute(
                        step, accumulated_context
                    )

                    success = getattr(
                        step_result, "success", True
                    )
                    if not success:
                        error = getattr(
                            step_result, "error",
                            f"Step {step_idx} failed in iteration {iteration}",
                        )
                        logger.warning(
                            "LoopRunner — step failed in iteration",
                            extra={
                                "iteration": iteration,
                                "step_idx": step_idx,
                                "error": error,
                            },
                        )
                        self._circuit_breaker_registry.record_failure(
                            step_key
                        )
                        iteration_success = False
                        iteration_error = error
                        break  # Fail-fast within iteration

                    # Collect artifacts from step result
                    artifacts = getattr(
                        step_result, "artifacts", []
                    )
                    if artifacts:
                        iteration_artifacts.extend(artifacts)

                except Exception as e:
                    error_msg = (
                        f"Step {step_idx} in iteration {iteration} "
                        f"raised exception: {e}"
                    )
                    logger.error(
                        "LoopRunner — step exception",
                        extra={
                            "iteration": iteration,
                            "step_idx": step_idx,
                            "error": str(e),
                        },
                    )
                    self._circuit_breaker_registry.record_failure(
                        step_key
                    )
                    iteration_success = False
                    iteration_error = error_msg
                    break  # Fail-fast within iteration

            # Record iteration result
            iteration_record = {
                "iteration": iteration,
                "success": iteration_success,
                "error": iteration_error,
                "artifact_count": len(iteration_artifacts),
            }
            iteration_results.append(iteration_record)
            loop_state.iteration_results.append(iteration_record)

            # Feed forward: pass artifacts to next iteration
            if iteration_success and iteration < loop_config.count:
                accumulated_context = self._update_context(
                    accumulated_context, iteration_artifacts
                )
            elif not iteration_success:
                return LoopRunnerResult(
                    success=False,
                    iteration_count=iteration,
                    iteration_results=iteration_results,
                    last_artifacts=iteration_artifacts,
                    error=iteration_error,
                    escalation="loop",
                    trace_id=trace_id,
                )

        # All iterations completed successfully
        logger.info(
            "LoopRunner.run — all iterations complete",
            extra={
                "iteration_count": loop_config.count,
            },
        )

        return LoopRunnerResult(
            success=True,
            iteration_count=loop_config.count,
            iteration_results=iteration_results,
            last_artifacts=accumulated_context.get("artifacts", [])
            if hasattr(accumulated_context, "get")
            else [],
            trace_id=trace_id,
        )

    def reset_loop_state(self, loop_id: str) -> None:
        """Reset loop state for a specific loop (re-entry reset).

        Args:
            loop_id: The loop identifier to reset.
        """
        self._loop_states.pop(loop_id, None)
        logger.debug(
            "LoopRunner — loop state reset",
            extra={"loop_id": loop_id},
        )

    def reset_all_state(self) -> None:
        """Reset all loop states (cleanup)."""
        self._loop_states.clear()
        logger.debug("LoopRunner — all loop states reset")

    def get_loop_state(self, loop_id: str) -> LoopState | None:
        """Get the current state of a loop.

        Args:
            loop_id: The loop identifier.

        Returns:
            LoopState if the loop has been started, or None.
        """
        return self._loop_states.get(loop_id)

    def _update_context(
        self,
        context: Any,
        iteration_artifacts: list[Any],
    ) -> Any:
        """Feed artifacts forward to the next iteration.

        If context is a dict, updates the 'artifacts' key.
        If context has attributes, tries to set artifacts.

        Args:
            context: The current execution context.
            iteration_artifacts: Artifacts from the completed
                iteration.

        Returns:
            Updated context with iteration artifacts folded in.
        """
        if isinstance(context, dict):
            context["artifacts"] = iteration_artifacts
            if "iteration_artifacts" not in context:
                context["iteration_artifacts"] = []
            context["iteration_artifacts"].extend(
                iteration_artifacts
            )
        elif hasattr(context, "artifacts"):
            context.artifacts = iteration_artifacts
        return context

    async def _stub_executor(
        self, step: Step, context: Any
    ) -> Any:
        """Stub step executor for testing / unconfigured use.

        Returns a simple success result object.
        """
        from types import SimpleNamespace

        return SimpleNamespace(
            success=True,
            artifacts=[],
            error=None,
        )
