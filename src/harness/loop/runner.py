"""LoopRunner — recursive loop step execution — V7 §5.2, R33.

Executes LoopConfig steps: runs a sequence of sub-steps ``count`` times
(or until convergence), feeding outputs from iteration N to iteration N+1.
Supports re-entry semantics (R18), loop counter tracking (per-loop, not
global), convergence-aware iteration with 5 strategies, and circuit
breaker escalation per iteration.

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

Convergence-aware usage::

    from harness.loop.convergence import resolve_strategy

    config = ConvergenceConfig(strategy="gate_judgment", max_iterations=3)
    strategy = resolve_strategy(config)

    async def convergence_check(step_results, artifacts, iteration):
        return await strategy.check(step_results, artifacts, iteration)

    result = await runner.run(
        loop_config=LoopConfig(convergence=config),
        steps=[step1, step2, step3],
        context=context,
        convergence_check=convergence_check,
    )
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from harness.errors import LoopExecutionError
from harness.loop.model import LoopState
from harness.phase.circuit_breaker import CircuitBreakerRegistry
from harness.phase.model import (
    ConvergenceConfig,
    ConvergenceVerdict,
    LoopConfig,
    Step,
    StepResult,
)
from harness.tracing import TraceLogger

logger = TraceLogger("harness.loop.runner")

# Type alias for convergence check callable
ConvergenceCheckFn = Callable[
    [list[StepResult], dict[str, str], int],
    Coroutine[Any, Any, ConvergenceVerdict],
]


@dataclass
class LoopRunnerResult:
    """Result of executing a loop step.

    Attributes:
        success: True if ALL iterations completed successfully.
        iteration_count: Number of iterations executed.
        iteration_results: Results from each iteration, in order.
        step_results: All step results across all iterations.
        last_artifacts: Artifacts from the final iteration.
        error: Error message if the loop failed entirely.
        escalation: Escalation target ("iteration", "loop",
            "phase", "workflow", or None).
        convergence_status: How the loop ended ("complete", "timeout",
            "error", "phase_jump:<name>", or None).
        trace_id: Trace ID for structured logging.
    """

    success: bool
    iteration_count: int = 0
    iteration_results: list[dict[str, Any]] = field(
        default_factory=list
    )
    step_results: list[StepResult] = field(default_factory=list)
    last_artifacts: list[Any] = field(default_factory=list)
    error: str | None = None
    escalation: str | None = None
    convergence_status: str | None = None
    trace_id: str = ""


class LoopRunner:
    """Executes loop steps by iterating over sub-steps.

    Each iteration executes the sub-steps in order. Outputs from
    iteration N are passed as inputs to iteration N+1 (feed-forward).

    Convergence-aware iteration: when a `convergence_check` callable
    is provided, the loop checks after each iteration whether to stop
    early. This enables critic loops with gate_judgment, all_gates,
    test_suite, stable, and external_approval strategies.

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
        convergence_check: ConvergenceCheckFn | None = None,
    ) -> LoopRunnerResult:
        """Execute a loop step.

        When convergence_check is provided, the loop checks after each
        successful iteration whether to stop early. If converged, returns
        with convergence_status set. Phase-jump signals are propagated
        through convergence_status.

        Test output feed-through (v4 Fix 2):
        Test output from test_suite strategy is injected into context
        AFTER _update_context() to survive context rebuilds. A persistent
        file fallback ensures robustness.

        Args:
            loop_config: The loop configuration (count, description,
                convergence).
            steps: The sub-steps to execute in each iteration.
            context: Execution context with slug, mode, and
                accumulated artifacts.
            reentry: Re-entry semantics override. If "resume",
                counters continue from previous run. Otherwise
                counters reset.
            convergence_check: Optional async callable that checks
                convergence after each iteration. Receives
                (step_results, artifacts_dict, iteration_idx) and
                returns ConvergenceVerdict.

        Returns:
            LoopRunnerResult with iteration results, step results,
            and convergence status.
        """
        loop_id = self._get_attr(context, "_loop_id", None) or id(loop_config)
        trace_id = self._get_attr(context, "trace_id", "")

        # Re-entry handling (R18)
        loop_state = self._loop_states.get(loop_id)
        if loop_state is None or reentry != "resume":
            loop_state = LoopState()
            self._loop_states[loop_id] = loop_state

        # Determine max iterations (convergence-aware)
        max_iterations = (
            loop_config.convergence.max_iterations
            if loop_config.convergence
            else loop_config.count
        )
        effective_count = max_iterations

        logger.info(
            "LoopRunner.run — starting loop",
            extra={
                "loop_count": max_iterations,
                "description": loop_config.description or "",
                "steps": len(steps),
                "reentry": reentry or "default",
                "iteration_start": loop_state.current_iteration + 1,
                "has_convergence": convergence_check is not None,
            },
        )

        iteration_results: list[dict[str, Any]] = []
        all_step_results: list[StepResult] = []
        accumulated_context = context
        last_verdict: ConvergenceVerdict | None = None

        for iteration in range(
            loop_state.current_iteration + 1, max_iterations + 1
        ):
            loop_state.current_iteration = iteration
            loop_state.total_iterations = max_iterations

            logger.info(
                "LoopRunner — iteration",
                extra={
                    "iteration": iteration,
                    "total": max_iterations,
                },
            )

            # Execute all sub-steps for this iteration
            iteration_step_results: list[StepResult] = []
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
                                "total_iterations": max_iterations,
                            }
                        )

                    step_result = await self._step_executor.execute(
                        step, accumulated_context
                    )

                    success = getattr(
                        step_result, "success", True
                    )
                    error = getattr(
                        step_result, "error", None
                    )

                    # Build StepResult for convergence analysis
                    sr = StepResult(
                        step_type=getattr(step, "role", "") or step.step_type,
                        step_role=getattr(step, "agents", [None])[0]
                        if step.agents else "",
                        status="success" if success else "failure",
                        artifacts=getattr(step_result, "artifacts", {})
                        if hasattr(step_result, "artifacts") else {},
                        error=error,
                        iteration=iteration,
                    )

                    if isinstance(sr.artifacts, dict) and not sr.artifacts:
                        # Try converting list artifacts to dict for analysis
                        list_arts = getattr(step_result, "artifacts", [])
                        if isinstance(list_arts, list) and list_arts:
                            sr.artifacts = {
                                f"output_{i}": str(a)
                                for i, a in enumerate(list_arts)
                            }

                    iteration_step_results.append(sr)

                    if not success:
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
            all_step_results.extend(iteration_step_results)

            # Convergence check (NEW)
            if convergence_check and iteration_success:
                # Build artifacts dict from accumulated context
                artifacts_dict = self._build_artifacts_dict(
                    accumulated_context, iteration_artifacts
                )
                last_verdict = await convergence_check(
                    iteration_step_results,
                    artifacts_dict,
                    iteration - 1,  # 0-based
                )

                if last_verdict.converged or last_verdict.status_override:
                    loop_state.mark_completed()
                    logger.info(
                        "LoopRunner — converged",
                        extra={
                            "iteration": iteration,
                            "reason": last_verdict.reason,
                            "status_override": last_verdict.status_override,
                        },
                    )
                    return LoopRunnerResult(
                        success=True,
                        iteration_count=iteration,
                        iteration_results=iteration_results,
                        step_results=all_step_results,
                        last_artifacts=accumulated_context.get("artifacts", [])
                        if hasattr(accumulated_context, "get")
                        else iteration_artifacts,
                        convergence_status=(
                            last_verdict.status_override or "complete"
                        ),
                        trace_id=trace_id,
                    )

            # Feed forward: pass artifacts to next iteration
            if iteration_success and iteration < max_iterations:
                # Step 1: Apply _update_context (may replace, not merge)
                accumulated_context = self._update_context(
                    accumulated_context, iteration_artifacts
                )

                # Step 2 (v4 Fix 2): Inject test_output AFTER _update_context.
                # This ensures test_output survives context replacement.
                if convergence_check and last_verdict and last_verdict.test_output:
                    self._inject_artifact(
                        accumulated_context,
                        "test_output",
                        last_verdict.test_output,
                    )

                # Step 3 (v4 Fix 2): Also check persistent artifact file.
                # If the in-memory injection was lost (e.g. _update_context
                # deep-clones and drops extra keys), read from disk.
                self._ensure_test_output_in_context(
                    accumulated_context, loop_config
                )

            elif not iteration_success:
                return LoopRunnerResult(
                    success=False,
                    iteration_count=iteration,
                    iteration_results=iteration_results,
                    step_results=all_step_results,
                    last_artifacts=iteration_artifacts,
                    error=iteration_error,
                    escalation="loop",
                    trace_id=trace_id,
                )

        # Max iterations reached — apply timeout behaviour
        # If convergence was configured, use the configured timeout mode.
        # If no convergence (count-based loop), all iterations completed
        # successfully — original behaviour.
        if loop_config.convergence:
            timeout_is_error = loop_config.convergence.on_timeout == "fail"
            convergence_status = "error" if timeout_is_error else "timeout"
            success = not timeout_is_error
        else:
            success = True
            convergence_status = None

        logger.info(
            "LoopRunner.run — all iterations complete (or timeout)",
            extra={
                "iteration_count": max_iterations,
                "has_convergence": loop_config.convergence is not None,
            },
        )

        return LoopRunnerResult(
            success=success,
            iteration_count=max_iterations,
            iteration_results=iteration_results,
            step_results=all_step_results,
            last_artifacts=accumulated_context.get("artifacts", [])
            if hasattr(accumulated_context, "get")
            else [],
            convergence_status=convergence_status,
            trace_id=trace_id,
        )

    def _build_artifacts_dict(
        self,
        context: Any,
        iteration_artifacts: list[Any],
    ) -> dict[str, str]:
        """Build a dict of artifacts from context and iteration output.

        Args:
            context: Current execution context.
            iteration_artifacts: Artifacts produced in current iteration.

        Returns:
            Dict mapping artifact names to string content.
        """
        artifacts_dict: dict[str, str] = {}
        if hasattr(context, "get"):
            ctx_arts = context.get("artifacts", [])
            if isinstance(ctx_arts, list):
                for i, a in enumerate(ctx_arts):
                    artifacts_dict[f"ctx_artifact_{i}"] = str(a)
            elif isinstance(ctx_arts, dict):
                artifacts_dict.update(ctx_arts)
        for i, a in enumerate(iteration_artifacts):
            artifacts_dict[f"iter_artifact_{i}"] = str(a)
        return artifacts_dict

    def _inject_artifact(
        self,
        context: Any,
        key: str,
        value: str,
    ) -> None:
        """Inject an artifact into the context.

        Supports both dict and object contexts.
        """
        if isinstance(context, dict):
            if "artifacts" not in context:
                context["artifacts"] = {}
            if isinstance(context["artifacts"], dict):
                context["artifacts"][key] = value
            elif isinstance(context["artifacts"], list):
                context["artifacts"].append({key: value})
        elif hasattr(context, "artifacts"):
            try:
                if isinstance(context.artifacts, dict):
                    context.artifacts[key] = value
                elif isinstance(context.artifacts, list):
                    context.artifacts.append({key: value})
            except (AttributeError, TypeError):
                pass

    def _ensure_test_output_in_context(
        self,
        context: Any,
        loop_config: LoopConfig,
    ) -> None:
        """v4 (Fix 2): Ensure test_output is in context even if
        _update_context dropped the in-memory injection.

        Reads from the persistent artifact file written by
        TestSuiteStrategy. This provides a last-resort fallback.
        """
        if not loop_config or not loop_config.convergence:
            return
        if loop_config.convergence.strategy != "test_suite":
            # Also check alias
            from harness.loop.convergence import resolve_strategy_name
            if resolve_strategy_name(loop_config.convergence.strategy) != "test_suite":
                return

        # Already has test_output in context?
        if self._context_has_artifact(context, "test_output"):
            return

        # Read from persistent artifact file
        test_output_path = (
            loop_config.convergence.test_output_path
            or ".harness/test_output/latest.txt"
        )
        try:
            path = Path(test_output_path)
            if path.exists():
                content = path.read_text()
                if content.strip():
                    self._inject_artifact(context, "test_output", content)
        except (OSError, IOError):
            pass  # Non-fatal

    @staticmethod
    def _context_has_artifact(context: Any, key: str) -> bool:
        """Check if context contains an artifact by key."""
        if isinstance(context, dict):
            artifacts = context.get("artifacts", {})
            if isinstance(artifacts, dict):
                return key in artifacts
            return False
        if hasattr(context, "artifacts"):
            try:
                if isinstance(context.artifacts, dict):
                    return key in context.artifacts
            except (AttributeError, TypeError):
                pass
        return False

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
