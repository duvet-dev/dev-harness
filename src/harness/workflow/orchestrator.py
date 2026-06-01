"""WorkflowOrchestrator — multi-phase workflow lifecycle — V7 §5.14.

Orchestrates the execution of multiple phases in sequence, managing
phase-to-phase transitions and coordinating with PhaseOrchestrator
for individual phase lifecycle management.

The orchestrator:
- select_workflow(): Picks the right workflow for a session type
- enter_workflow(): Starts a workflow from its first phase
- advance_workflow(): Moves to the next phase after the current one
- Tracks workflow state (pending, active, completed, failed)
- Passes artifacts between phases

See V7 §5.14 and §6.1 for the design.
"""

from __future__ import annotations

from typing import Any

from harness.domain.engagement.model import Engagement
from harness.errors import UnknownWorkflowError, WorkflowNotActiveError
from harness.phase.orchestrator import PhaseOrchestrator
from harness.tracing import TraceLogger
from harness.workflow.model import (
    Workflow,
    WorkflowResult,
    WorkflowState,
    WorkflowStatus,
)

logger = TraceLogger("harness.workflow.orchestrator")

# ── Workflow Registry ────────────────────────────────────────────────

# Default workflow definitions keyed by workflow name.
# These can be overridden by configuration in later waves.
DEFAULT_WORKFLOWS: dict[str, Workflow] = {
    "standard": Workflow(
        name="standard",
        phases=[
            "discover",
            "design",
            "planning",  # ADDED v3 — planning after design
            "build",
            "review",
            "test",
            "validate",
            "deliver",
        ],
    ),
    "brownfield": Workflow(  # NEW v3
        name="brownfield",
        phases=[
            "analyse",
            "design",
            "planning",
            "build",
            "test",
            "review",
        ],
    ),
    "quick-fix": Workflow(
        name="quick-fix",
        phases=["fix", "test", "validate", "deliver"],
    ),
    "refactoring": Workflow(
        name="refactoring",
        phases=["assess", "refactor", "test", "validate"],
    ),
    "get-well": Workflow(
        name="get-well",
        phases=[
            "analyse",  # ADDED v3 — prepend analyse per Andy C3
            "assessment-triage",
            "remediation-requirements",
            "architecture-design",
            "planning",
            "implementation",
            "testing",
            "review",
        ],
    ),
    "inspect": Workflow(
        name="inspect",
        phases=["audit", "report"],
    ),
}

# Session type → workflow name mapping
SESSION_TYPE_MAP: dict[str, str] = {
    "greenfield": "standard",
    "brownfield": "brownfield",  # ADDED v3
    "quick-fix": "quick-fix",
    "refactoring": "refactoring",
    "get-well": "get-well",
    "audit": "inspect",  # canonical
    "inspect": "inspect",
    # "review" maps to inspect for backward compatibility
    "review": "inspect",
}


class WorkflowOrchestrator:
    """Orchestrates multi-phase workflow execution.

    Manages the lifecycle of a full workflow: selecting the
    appropriate workflow, entering phases in order, advancing
    through the phase sequence, and tracking overall state.

    Coordinates with PhaseOrchestrator for individual phase
    execution.

    Usage::

        wf_orch = WorkflowOrchestrator(phase_orchestrator)
        wf_orch.register_workflows(DEFAULT_WORKFLOWS)

        result = await wf_orch.enter_workflow(
            slug="my-engagement",
            workflow_name="standard",
            mode="auto",
        )
        # Phase executes...
        result = await wf_orch.advance_workflow("my-engagement")
    """

    def __init__(
        self,
        phase_orchestrator: PhaseOrchestrator,
    ) -> None:
        """Initialise the WorkflowOrchestrator.

        Args:
            phase_orchestrator: PhaseOrchestrator for executing
                individual phases.
        """
        self._phase_orchestrator = phase_orchestrator
        self._workflows: dict[str, Workflow] = {}
        self._states: dict[str, WorkflowState] = {}

    # ── Workflow Registration ────────────────────────────────────────

    def register_workflow(self, workflow: Workflow) -> None:
        """Register a workflow definition.

        Args:
            workflow: The Workflow definition to register.
        """
        self._workflows[workflow.name] = workflow
        logger.debug(
            "WorkflowOrchestrator — workflow registered",
            extra={"workflow": workflow.name, "phases": len(workflow.phases)},
        )

    def register_workflows(
        self, workflows: dict[str, Workflow]
    ) -> None:
        """Register multiple workflow definitions.

        Args:
            workflows: Dict mapping workflow names to Workflow
                definitions.
        """
        for workflow in workflows.values():
            self.register_workflow(workflow)

    def get_workflow(self, name: str) -> Workflow | None:
        """Get a registered workflow by name.

        Args:
            name: Workflow name.

        Returns:
            The Workflow definition, or None if not found.
        """
        return self._workflows.get(name)

    def list_workflows(self) -> list[str]:
        """List all registered workflow names.

        Returns:
            Sorted list of registered workflow names.
        """
        return sorted(self._workflows.keys())

    # ── Workflow Selection ───────────────────────────────────────────

    def select_workflow(
        self,
        session_type: str,
        engagement: Engagement | None = None,
    ) -> str:
        """Select the appropriate workflow for a session type.

        Maps session types to workflow names. If the session type
        is unknown, returns a default workflow name.

        Args:
            session_type: Type of session (e.g. "greenfield",
                "refactoring", "quick-fix", "get-well").
            engagement: Optional Engagement for context-aware
                selection (may influence workflow choice based on
                engagement state).

        Returns:
            The name of the selected workflow.

        Raises:
            UnknownWorkflowError: If the mapped workflow is not
                registered.
        """
        # Check engagement for explicit workflow override
        if engagement and engagement.workflow_name:
            wf_name = engagement.workflow_name
            if wf_name in self._workflows:
                return wf_name

        # Map session type to workflow
        wf_name = SESSION_TYPE_MAP.get(session_type, "standard")

        # Fall back to standard if mapped workflow not registered
        if wf_name not in self._workflows:
            wf_name = "standard"

        if wf_name not in self._workflows:
            raise UnknownWorkflowError(
                f"Default workflow '{wf_name}' not registered "
                f"(session_type={session_type})"
            )

        return wf_name

    # ── Workflow Lifecycle ───────────────────────────────────────────

    async def enter_workflow(
        self,
        slug: str,
        workflow_name: str,
        mode: str = "auto",
    ) -> WorkflowResult:
        """Enter a workflow and start its first phase.

        Creates a WorkflowState from the registered workflow,
        sets the first phase as current, and dispatches it to
        PhaseOrchestrator for execution.

        Args:
            slug: Unique identifier for this workflow execution
                (typically the engagement slug).
            workflow_name: Name of the workflow to start.
            mode: Execution mode ("auto" or "manual").

        Returns:
            WorkflowResult with the result of the first phase
            execution.

        Raises:
            UnknownWorkflowError: If the workflow is not registered.
        """
        workflow = self._workflows.get(workflow_name)
        if workflow is None:
            logger.error(
                "WorkflowOrchestrator — unknown workflow",
                extra={"workflow_name": workflow_name},
            )
            return WorkflowResult(
                success=False,
                workflow_name=workflow_name,
                slug=slug,
                error=f"Unknown workflow: '{workflow_name}'",
                escalation="user",
            )

        if not workflow.phases:
            return WorkflowResult(
                success=False,
                workflow_name=workflow_name,
                slug=slug,
                error=f"Workflow '{workflow_name}' has no phases defined",
                escalation="user",
            )

        logger.info(
            "WorkflowOrchestrator — entering workflow",
            extra={
                "slug": slug,
                "workflow": workflow_name,
                "phases": len(workflow.phases),
                "mode": mode,
            },
        )

        # Create workflow state
        state = WorkflowState.from_workflow(
            workflow=workflow,
            slug=slug,
            mode=mode,
        )

        # Mark the first phase as current
        first_phase = workflow.phases[0]
        state.mark_phase_started(first_phase)
        self._states[slug] = state

        # Dispatch to PhaseOrchestrator
        phase_result = await self._phase_orchestrator.enter_phase(
            slug=slug,
            phase_name=first_phase,
            mode=mode,
        )

        # Update workflow state based on phase result
        if phase_result.success:
            state.mark_phase_completed(first_phase)
        else:
            state.mark_phase_failed(first_phase)

        logger.info(
            "WorkflowOrchestrator — phase complete (enter)",
            extra={
                "slug": slug,
                "phase": first_phase,
                "success": phase_result.success,
                "state": state.status.value,
            },
        )

        return self._build_result(state, phase_result)

    async def advance_workflow(
        self,
        slug: str,
    ) -> WorkflowResult:
        """Advance to the next phase in the workflow.

        Moves to the next pending phase after the current one
        completes, or reports completion if all phases are done.

        Args:
            slug: Unique identifier for the workflow execution.

        Returns:
            WorkflowResult with the result of the next phase
            execution, or completion status if all phases done.

        Raises:
            WorkflowNotActiveError: If the workflow is not active.
        """
        state = self._states.get(slug)
        if state is None:
            return WorkflowResult(
                success=False,
                slug=slug,
                error=f"No active workflow for slug '{slug}'",
                escalation="user",
            )

        if not state.is_active and state.status != WorkflowStatus.COMPLETED:
            logger.warning(
                "WorkflowOrchestrator — workflow not active",
                extra={
                    "slug": slug,
                    "status": state.status.value,
                },
            )
            return WorkflowResult(
                success=False,
                workflow_name=state.workflow_name,
                slug=slug,
                error=f"Workflow '{slug}' is not active (status: {state.status.value})",
                escalation="user",
                status=state.status,
            )

        # Check if all phases are complete
        if not state.pending_phases and state.current_phase is None:
            state.status = WorkflowStatus.COMPLETED
            logger.info(
                "WorkflowOrchestrator — workflow completed",
                extra={"slug": slug, "workflow": state.workflow_name},
            )
            return WorkflowResult(
                success=True,
                workflow_name=state.workflow_name,
                slug=slug,
                current_phase=None,
                completed_phases=list(state.completed_phases),
                pending_phases=[],
                status=WorkflowStatus.COMPLETED,
                mode=state.mode,
            )

        # Move to the next phase
        if not state.pending_phases:
            state.status = WorkflowStatus.COMPLETED
            return WorkflowResult(
                success=True,
                workflow_name=state.workflow_name,
                slug=slug,
                current_phase=None,
                completed_phases=list(state.completed_phases),
                pending_phases=[],
                status=WorkflowStatus.COMPLETED,
                mode=state.mode,
            )

        next_phase = state.pending_phases[0]
        state.mark_phase_started(next_phase)

        logger.info(
            "WorkflowOrchestrator — advancing to phase",
            extra={
                "slug": slug,
                "phase": next_phase,
                "completed": len(state.completed_phases),
                "remaining": len(state.pending_phases),
            },
        )

        # Dispatch to PhaseOrchestrator
        phase_result = await self._phase_orchestrator.enter_phase(
            slug=slug,
            phase_name=next_phase,
            mode=state.mode,
        )

        # Update workflow state
        if phase_result.success:
            state.mark_phase_completed(next_phase)
        else:
            state.mark_phase_failed(next_phase)

            # Check escalation from PhaseOrchestrator
            if phase_result.escalation in ("loop", "phase", "workflow"):
                # Internal escalation — if escalation is "workflow",
                # we may re-enter depending on context
                logger.warning(
                    "WorkflowOrchestrator — phase escalation",
                    extra={
                        "slug": slug,
                        "phase": next_phase,
                        "escalation": phase_result.escalation,
                    },
                )

        logger.info(
            "WorkflowOrchestrator — phase complete (advance)",
            extra={
                "slug": slug,
                "phase": next_phase,
                "success": phase_result.success,
                "state": state.status.value,
                "completed": len(state.completed_phases),
                "remaining": len(state.pending_phases),
            },
        )

        return self._build_result(state, phase_result)

    async def get_workflow_status(
        self, slug: str
    ) -> WorkflowState | None:
        """Get the current workflow state for a slug.

        Args:
            slug: Unique identifier for the workflow execution.

        Returns:
            WorkflowState, or None if no workflow is active for
            this slug.
        """
        return self._states.get(slug)

    def get_state(self, slug: str) -> WorkflowState | None:
        """Synchronous alias for get_workflow_status.

        Args:
            slug: Unique identifier for the workflow execution.

        Returns:
            WorkflowState, or None if not found.
        """
        return self._states.get(slug)

    def has_active_workflow(self, slug: str) -> bool:
        """Check if a workflow is currently active for the slug.

        Args:
            slug: Unique identifier for the workflow execution.

        Returns:
            True if a workflow exists and is active.
        """
        state = self._states.get(slug)
        return state is not None and state.is_active

    # ── Internal Helpers ─────────────────────────────────────────────

    def _build_result(
        self,
        state: WorkflowState,
        phase_result: Any,
    ) -> WorkflowResult:
        """Build a WorkflowResult from state and phase result.

        Args:
            state: The current workflow state.
            phase_result: The PhaseOrchestratorResult.

        Returns:
            A populated WorkflowResult.
        """
        return WorkflowResult(
            success=phase_result.success if hasattr(phase_result, "success") else state.status != WorkflowStatus.FAILED,
            workflow_name=state.workflow_name,
            slug=state.slug,
            current_phase=state.current_phase,
            completed_phases=list(state.completed_phases),
            pending_phases=list(state.pending_phases),
            status=state.status,
            phase_result=phase_result,
            error=phase_result.error if hasattr(phase_result, "error") else None,
            escalation=phase_result.escalation if hasattr(phase_result, "escalation") else None,
            mode=state.mode,
        )
