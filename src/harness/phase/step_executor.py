"""StepExecutor — dispatch any step type — V7 §5.2.

The StepExecutor is the central dispatch point for all three step
types (agent, loop, phase). It delegates to the appropriate handler:
- Agent/team steps → StepDispatcher
- Loop steps → LoopRunner
- Phase steps → PhaseOrchestrator

Usage::

    executor = StepExecutor(
        step_dispatcher=StepDispatcher(...),
        loop_runner=LoopRunner(...),
        phase_orchestrator=PhaseOrchestrator(...),
    )
    result = await executor.execute(step, context)
    if result.success:
        print(f"Step completed: {len(result.artifacts)} artifacts")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.artifact.repository import Artifact
from harness.errors import LoopExecutionError, PhaseExecutionError
from harness.phase.model import Step
from harness.tracing import TraceLogger

logger = TraceLogger("harness.phase.step_executor")


@dataclass
class StepResult:
    """Result of executing a single step.

    Attributes:
        success: True if the step completed successfully.
        artifacts: Artifacts produced by the step.
        error: Error message if the step failed.
        step_type: The type of step that was executed
            ("agent", "team", "loop", "phase").
        escalation: Escalation target if step failed
            ("loop", "phase", "workflow", or None).
        trace_id: Trace ID for structured logging.
    """

    success: bool
    artifacts: list[Artifact] = field(default_factory=list)
    error: str | None = None
    step_type: str = "unknown"
    escalation: str | None = None
    trace_id: str = ""


class StepExecutor:
    """Central step dispatch — routes each step to the right handler.

    The StepExecutor implements the recursive dispatch pattern:
    - Agent/team steps → StepDispatcher (agent dispatch)
    - Loop steps → LoopRunner (recursive sub-step execution)
    - Phase steps → PhaseOrchestrator (phase jump)

    This mirrors the Harness's own escalation chain: step → loop →
    phase → workflow.
    """

    def __init__(
        self,
        step_dispatcher: Any | None = None,
        loop_runner: Any | None = None,
        phase_orchestrator: Any | None = None,
    ) -> None:
        """Initialise the StepExecutor.

        Args:
            step_dispatcher: Dispatcher for agent/team steps.
                If None, a stub is used.
            loop_runner: LoopRunner for loop steps.
                If None, a stub is used.
            phase_orchestrator: PhaseOrchestrator for phase steps.
                If None, a stub is used.
        """
        self._step_dispatcher = step_dispatcher or self._stub_dispatcher
        self._loop_runner = loop_runner or self._stub_loop_runner
        self._phase_orchestrator = (
            phase_orchestrator or self._stub_phase_orchestrator
        )

    async def execute(
        self,
        step: Step,
        context: Any | None = None,
    ) -> StepResult:
        """Execute any step type by routing to the right handler.

        Args:
            step: The step to execute (agent, loop, or phase).
            context: Execution context with slug, mode, and
                accumulated data.

        Returns:
            StepResult with execution status and artifacts.

        Raises:
            LoopExecutionError: If loop step fails entirely.
            PhaseExecutionError: If phase step fails entirely.
        """
        trace_id = getattr(context, "trace_id", "") if context else ""

        if step.agents or step.team:
            return await self._dispatch_agent_step(step, context)

        elif step.loop:
            return await self._dispatch_loop_step(step, context)

        elif step.phase:
            return await self._dispatch_phase_step(step, context)

        # Should never reach here due to Step.__post_init__
        logger.error(
            "StepExecutor — unknown step type",
            extra={"step": str(step)},
        )
        return StepResult(
            success=False,
            error="Unknown step type (no agents, team, loop, or phase)",
            step_type="unknown",
            trace_id=trace_id,
        )

    async def _dispatch_agent_step(
        self,
        step: Step,
        context: Any | None,
    ) -> StepResult:
        """Dispatch an agent or team step via StepDispatcher."""
        trace_id = self._get_context_attr(context, "trace_id", "")

        logger.info(
            "StepExecutor — dispatching agent step",
            extra={
                "step_type": step.step_type,
                "has_agents": step.agents is not None,
                "has_team": step.team is not None,
            },
        )

        try:
            dispatch_result = await self._step_dispatcher.dispatch(
                step, context
            )

            return StepResult(
                success=getattr(dispatch_result, "success", False),
                artifacts=getattr(
                    dispatch_result, "artifacts", []
                ),
                error=getattr(dispatch_result, "error", None),
                step_type=step.step_type,
                escalation=getattr(
                    dispatch_result, "escalation", None
                ),
                trace_id=trace_id,
            )

        except Exception as e:
            logger.error(
                "StepExecutor — agent dispatch error",
                extra={"error": str(e)},
            )
            return StepResult(
                success=False,
                error=f"Agent dispatch error: {e}",
                step_type=step.step_type,
                escalation="phase",
                trace_id=trace_id,
            )

    async def _dispatch_loop_step(
        self,
        step: Step,
        context: Any | None,
    ) -> StepResult:
        """Dispatch a loop step via LoopRunner."""
        trace_id = self._get_context_attr(context, "trace_id", "")

        logger.info(
            "StepExecutor — dispatching loop step",
            extra={
                "count": step.loop.count if step.loop else 0,
                "description": (
                    step.loop.description if step.loop else ""
                ),
            },
        )

        if step.loop is None:
            return StepResult(
                success=False,
                error="Loop step has no loop configuration",
                step_type="loop",
                trace_id=trace_id,
            )

        # Extract sub-steps from context or default to an empty list
        # Loop steps reference sub-steps via context.steps
        sub_steps = getattr(context, "steps", []) or []
        reentry = getattr(context, "reentry", None)

        try:
            loop_result = await self._loop_runner.run(
                loop_config=step.loop,
                steps=sub_steps,
                context=_LoopContext.from_context(context),
                reentry=reentry,
            )

            if not loop_result.success:
                raise LoopExecutionError(
                    loop_result.error
                    or f"Loop failed after {loop_result.iteration_count} iterations"
                )

            return StepResult(
                success=True,
                artifacts=loop_result.last_artifacts,
                step_type="loop",
                escalation=None,
                trace_id=trace_id,
            )

        except LoopExecutionError:
            raise  # Re-raise loop errors directly

        except Exception as e:
            logger.error(
                "StepExecutor — loop dispatch error",
                extra={"error": str(e)},
            )
            raise LoopExecutionError(
                f"Loop execution error: {e}"
            ) from e

    def _get_context_attr(
        self,
        context: Any | None,
        attr: str,
        default: Any = "",
    ) -> Any:
        """Get attribute from context, supporting both dict and object."""
        if context is None:
            return default
        if isinstance(context, dict):
            return context.get(attr, default)
        return getattr(context, attr, default)

    async def _dispatch_phase_step(
        self,
        step: Step,
        context: Any | None,
    ) -> StepResult:
        """Dispatch a phase step via PhaseOrchestrator."""
        trace_id = self._get_context_attr(context, "trace_id", "")
        slug = self._get_context_attr(context, "slug", "")
        mode = self._get_context_attr(context, "mode", "auto")
        phase_name = step.phase or ""

        logger.info(
            "StepExecutor — dispatching phase step",
            extra={
                "phase": phase_name,
                "slug": slug,
                "mode": mode,
            },
        )

        try:
            orchestrator_result = await self._phase_orchestrator.enter_phase(
                slug=slug,
                phase_name=phase_name,
                mode=mode,
            )

            if not orchestrator_result.success:
                raise PhaseExecutionError(
                    orchestrator_result.error
                    or f"Phase '{phase_name}' failed"
                )

            return StepResult(
                success=True,
                artifacts=[],
                step_type="phase",
                escalation=None,
                trace_id=trace_id,
            )

        except PhaseExecutionError:
            raise  # Re-raise phase errors directly

        except Exception as e:
            logger.error(
                "StepExecutor — phase dispatch error",
                extra={"error": str(e)},
            )
            raise PhaseExecutionError(
                f"Phase execution error: {e}"
            ) from e

    # ── Stubs for testing / unconfigured use ──────────────────────────

    async def _stub_dispatcher(
        self, step: Step, context: Any | None = None
    ) -> Any:
        """Stub StepDispatcher for testing."""
        from types import SimpleNamespace

        return SimpleNamespace(
            success=True,
            artifacts=[],
            error=None,
            escalation=None,
        )

    async def _stub_loop_runner(
        self, loop_config: Any, steps: list[Step], context: Any
    ) -> Any:
        """Stub LoopRunner for testing."""
        from types import SimpleNamespace

        return SimpleNamespace(
            success=True,
            iteration_count=1,
            iteration_results=[],
            last_artifacts=[],
            error=None,
            escalation=None,
        )

    async def _stub_phase_orchestrator(
        self, slug: str, phase_name: str, mode: str = "auto"
    ) -> Any:
        """Stub PhaseOrchestrator for testing."""
        from types import SimpleNamespace

        return SimpleNamespace(
            success=True,
            phase_result=None,
            phase_name=phase_name,
            next_phase=None,
            error=None,
            escalation=None,
        )


class _LoopContext:
    """Adapter that wraps a user context for loop execution.

    Provides a minimal interface for LoopRunner to read slug,
    mode, trace_id, steps, and reentry from any context shape.
    """

    def __init__(self) -> None:
        self.slug: str = ""
        self.mode: str = "auto"
        self.trace_id: str = ""
        self.steps: list[Step] = []
        self.reentry: str | None = None
        self._loop_metadata: dict[str, Any] = {}

    @classmethod
    def from_context(cls, context: Any | None) -> _LoopContext:
        """Create a _LoopContext from any context-like object."""
        lc = cls()
        if context is None:
            return lc

        if isinstance(context, dict):
            lc.slug = context.get("slug", "")
            lc.mode = context.get("mode", "auto")
            lc.trace_id = context.get("trace_id", "")
            lc.steps = context.get("steps", [])
            lc.reentry = context.get("reentry", None)
            return lc

        lc.slug = getattr(context, "slug", "")
        lc.mode = getattr(context, "mode", "auto")
        lc.trace_id = getattr(context, "trace_id", "")
        lc.steps = getattr(context, "steps", [])
        lc.reentry = getattr(context, "reentry", None)
        return lc

    def setdefault(self, key: str, value: Any) -> None:
        """Dict-like setdefault for backwards compat with dict context."""
        if not hasattr(self, key):
            setattr(self, key, value)
