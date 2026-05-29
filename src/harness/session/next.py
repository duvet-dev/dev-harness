"""NextEngine — advance engagement to the next step/phase/workflow — V7 §5.12.

Coordinates WorkflowOrchestrator + PhaseOrchestrator + StepExecutor
to advance an engagement through its lifecycle.

The engine determines the current position (workflow → phase → step)
and advances accordingly. If the current phase has more steps, the
next step is dispatched. If the phase is complete, the workflow
advances to the next phase. If the workflow is complete, the
engagement is marked completed.

Usage::

    engine = NextEngine(
        workflow_orchestrator=wf_orch,
        step_executor=step_exec,
    )
    result = await engine.advance("my-engagement")
    print(f"Phase: {result.phase_name}, Step: {result.step_name}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.tracing import TraceLogger

logger = TraceLogger("harness.session.next")


@dataclass
class NextResult:
    """Result of advancing an engagement.

    Attributes:
        success: True if advancement succeeded.
        slug: The engagement slug that was advanced.
        action: What action was taken: "workflow_start",
            "phase_advance", "step_executed", "workflow_complete",
            "already_completed", or "error".
        workflow_name: Name of the active workflow.
        phase_name: Name of the current or newly-entered phase.
        step_name: Name of the executed step, if any.
        artifacts_produced: List of artifact descriptions from the step.
        error: Error message if advancement failed.
        escalation: Escalation target if advancement failed.
    """

    success: bool = True
    slug: str = ""
    action: str = ""
    workflow_name: str = ""
    phase_name: str = ""
    step_name: str = ""
    artifacts_produced: list[str] = field(default_factory=list)
    error: str = ""
    escalation: str = ""


class NextEngine:
    """Advances engagements through the workflow/phase/step lifecycle.

    Delegates to WorkflowOrchestrator for workflow-level transitions,
    PhaseOrchestrator for phase-level transitions, and StepExecutor
    for individual step execution.

    The engine is stateless; all state is managed by the underlying
    orchestrators, state managers, and engagement repository.
    """

    def __init__(
        self,
        workflow_orchestrator: Any = None,
        step_executor: Any = None,
    ) -> None:
        """Initialise the NextEngine.

        Args:
            workflow_orchestrator: WorkflowOrchestrator instance for
                workflow-level operations. If None, uses a stub.
            step_executor: StepExecutor instance for step-level
                operations. If None, uses a stub.
        """
        self._workflow_orchestrator = workflow_orchestrator
        self._step_executor = step_executor

    async def advance(
        self,
        slug: str,
        workflow_name: str | None = None,
    ) -> NextResult:
        """Advance the engagement to its next logical step.

        Decision logic:
        1. Check if a workflow is active for this slug.
        2. If no workflow exists yet → start a new workflow.
        3. If workflow is completed → mark engagement completed.
        4. If workflow is active → advance to next phase.
        5. If phase is executing → execute the next step.

        Args:
            slug: The engagement slug to advance.
            workflow_name: Optional workflow name to start (if no
                workflow is active). Defaults to "standard".

        Returns:
            NextResult describing what action was taken.
        """
        logger.info(
            "NextEngine.advance",
            extra={"slug": slug, "workflow_name": workflow_name or "standard"},
        )

        # ── 1. Check workflow state ─────────────────────────────────
        if self._workflow_orchestrator is None:
            return self._stub_advance(slug)

        state = self._workflow_orchestrator.get_state(slug)

        # ── 2. No workflow yet → start one ──────────────────────────
        if state is None:
            logger.info(
                "NextEngine — starting new workflow",
                extra={"slug": slug, "workflow": workflow_name or "standard"},
            )
            result = await self._workflow_orchestrator.enter_workflow(
                slug=slug,
                workflow_name=workflow_name or "standard",
                mode="auto",
            )

            if not result.success:
                return NextResult(
                    success=False,
                    slug=slug,
                    action="error",
                    error=result.error or "Failed to enter workflow",
                    escalation=result.escalation or "workflow",
                )

            return NextResult(
                success=True,
                slug=slug,
                action="workflow_start",
                workflow_name=result.workflow_name,
                phase_name=result.current_phase or "",
            )

        # ── 3. Workflow completed ───────────────────────────────────
        if state.is_completed:
            logger.info(
                "NextEngine — workflow already completed",
                extra={"slug": slug},
            )
            return NextResult(
                success=True,
                slug=slug,
                action="workflow_complete",
                workflow_name=state.workflow_name,
                phase_name=state.current_phase or "",
            )

        # ── 4. Workflow active → advance phase ──────────────────────
        if state.is_active:
            logger.info(
                "NextEngine — advancing workflow",
                extra={
                    "slug": slug,
                    "current_phase": state.current_phase,
                    "completed": len(state.completed_phases),
                    "pending": len(state.pending_phases),
                },
            )

            result = await self._workflow_orchestrator.advance_workflow(
                slug=slug,
            )

            if not result.success:
                return NextResult(
                    success=False,
                    slug=slug,
                    action="error",
                    workflow_name=result.workflow_name,
                    error=result.error or "Failed to advance workflow",
                    escalation=result.escalation or "workflow",
                )

            # Check if workflow is now complete
            if result.status.value == "completed":
                return NextResult(
                    success=True,
                    slug=slug,
                    action="workflow_complete",
                    workflow_name=result.workflow_name,
                    phase_name="",
                )

            return NextResult(
                success=True,
                slug=slug,
                action="phase_advance",
                workflow_name=result.workflow_name,
                phase_name=result.current_phase or "",
            )

        # ── 5. Check for step execution ─────────────────────────────
        # If a phase is executing and we have a step executor,
        # try to execute the next step within the current phase.
        if self._step_executor is not None and state.current_phase:
            try:
                # Attempt to execute next step in current phase
                # (delegates to StepExecutor which routes to the right
                #  strategy runner for the current phase)
                step_result = await self._step_executor.dispatch(
                    slug=slug,
                    phase_name=state.current_phase,
                )
                step_name = getattr(step_result, "step_name", "")
                artifacts = getattr(step_result, "artifacts", [])

                return NextResult(
                    success=True,
                    slug=slug,
                    action="step_executed",
                    workflow_name=state.workflow_name,
                    phase_name=state.current_phase,
                    step_name=step_name or "",
                    artifacts_produced=list(
                        str(a) for a in (artifacts or [])
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "NextEngine — step dispatch failed",
                    extra={"slug": slug, "phase": state.current_phase, "error": str(exc)},
                )
                # Fall through — phase advance instead

        # Fallback: return current state as info
        return NextResult(
            success=True,
            slug=slug,
            action="phase_advance",
            workflow_name=state.workflow_name,
            phase_name=state.current_phase or "",
        )

    def _stub_advance(self, slug: str) -> NextResult:
        """Return a stub result when no orchestrator is configured.

        Args:
            slug: The engagement slug.

        Returns:
            NextResult with stub status.
        """
        return NextResult(
            success=True,
            slug=slug,
            action="stub",
            workflow_name="standard",
            phase_name="discover",
        )
