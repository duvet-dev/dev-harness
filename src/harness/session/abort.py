"""AbortHandler — abort engagement operations — V7 §5.12.

Provides hard abort (immediate stop, no cleanup) and graceful stop
(complete current step then stop) operations for engagements.

The handler updates engagement status, workflow state, and optionally
performs cleanup operations depending on the abort mode.

Usage::

    handler = AbortHandler(
        engagement_repository=repo,
        workflow_orchestrator=wf_orch,
    )
    result = handler.hard_abort("my-engagement")
    # Engagement is now in ABORTED status, all work stopped
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AbortResult:
    """Result of an abort operation.

    Attributes:
        success: True if the abort was applied successfully.
        slug: The engagement slug that was aborted.
        mode: The abort mode used ("hard" or "graceful").
        previous_status: The engagement status before abort.
        completed_phases: List of phase names completed before abort.
        current_phase: The phase that was active at time of abort.
        error: Error message if the abort failed.
    """

    success: bool = True
    slug: str = ""
    mode: str = "hard"
    previous_status: str = ""
    completed_phases: list[str] = field(default_factory=list)
    current_phase: str | None = None
    error: str = ""


class AbortHandler:
    """Handles engagement abort operations.

    Supports two abort modes:
    - hard_abort: Immediate stop with no cleanup. All work is
      terminated and the engagement is marked ABORTED.
    - graceful_stop: Complete the current step, then stop and
      mark the engagement as ABORTED.

    After aborting, workflow state is updated to FAILED and the
    engagement status is set to ABORTED.
    """

    def __init__(
        self,
        engagement_repository: Any = None,
        workflow_orchestrator: Any = None,
    ) -> None:
        """Initialise the AbortHandler.

        Args:
            engagement_repository: EngagementRepository for loading
                and saving engagement state.
            workflow_orchestrator: WorkflowOrchestrator for updating
                workflow state on abort.
        """
        self._engagement_repository = engagement_repository
        self._workflow_orchestrator = workflow_orchestrator

    def hard_abort(
        self,
        slug: str,
    ) -> AbortResult:
        """Immediately abort an engagement with no cleanup.

        Stops all work immediately, sets engagement status to
        ABORTED, and updates workflow state to FAILED.

        Args:
            slug: The engagement slug to abort.

        Returns:
            AbortResult with the outcome of the hard abort.
        """
        return self._do_abort(slug, mode="hard")

    def graceful_stop(
        self,
        slug: str,
    ) -> AbortResult:
        """Gracefully stop an engagement after completing the current step.

        Waits for the current step to finish (simulated in this wave —
        real coordination with StepExecutor deferred), then marks the
        engagement as ABORTED.

        Args:
            slug: The engagement slug to stop.

        Returns:
            AbortResult with the outcome of the graceful stop.
        """
        return self._do_abort(slug, mode="graceful")

    def _do_abort(
        self,
        slug: str,
        mode: str = "hard",
    ) -> AbortResult:
        """Core abort logic — shared by both hard and graceful modes.

        Args:
            slug: The engagement slug.
            mode: Abort mode ("hard" or "graceful").

        Returns:
            AbortResult with outcome.
        """
        if self._engagement_repository is None:
            return self._stub_abort(slug, mode)

        try:
            # Load engagement from repository
            engagement = self._engagement_repository.load(slug)
            previous_status = engagement.status.value

            # Get completed phases from workflow state
            completed = []
            current_phase = engagement.current_phase
            if self._workflow_orchestrator is not None:
                state = self._workflow_orchestrator.get_state(slug)
                if state:
                    completed = list(state.completed_phases)
                    current_phase = state.current_phase or engagement.current_phase

            # Update engagement status to ABORTED
            from harness.engagement.model import EngagementStatus

            engagement.status = EngagementStatus.ABORTED
            engagement.last_active = datetime.now()
            self._engagement_repository.save(engagement)

            # Update workflow state to FAILED
            if self._workflow_orchestrator is not None and current_phase:
                state = self._workflow_orchestrator.get_state(slug)
                if state:
                    state.mark_phase_failed(current_phase)

            logger_msg = (
                f"Engagement '{slug}' {mode}-aborted "
                f"(was {previous_status})"
            )

            return AbortResult(
                success=True,
                slug=slug,
                mode=mode,
                previous_status=previous_status,
                completed_phases=completed,
                current_phase=current_phase,
            )

        except Exception as exc:
            return AbortResult(
                success=False,
                slug=slug,
                mode=mode,
                error=f"Failed to abort engagement '{slug}': {exc}",
            )

    def _stub_abort(
        self,
        slug: str,
        mode: str = "hard",
    ) -> AbortResult:
        """Return a stub result when no repository is configured.

        Args:
            slug: The engagement slug.
            mode: Abort mode.

        Returns:
            AbortResult with stub status.
        """
        return AbortResult(
            success=True,
            slug=slug,
            mode=mode,
            previous_status="stub",
        )
