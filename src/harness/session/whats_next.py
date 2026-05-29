"""WhatsNextEngine — query available actions for an engagement — V7 §5.12.

Provides user-facing information about what can be done next in
an engagement: which phases are pending, what commands are valid,
and whether anything is currently blocked.

The engine reads engagement state from WorkflowOrchestrator and
EngagementRepository to produce a structured summary of available
actions.

Usage::

    engine = WhatsNextEngine(workflow_orchestrator=wf_orch)
    result = engine.query("my-engagement")
    print(f"Pending phases: {result.pending_phases}")
    print(f"Available commands: {result.available_commands}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WhatsNextResult:
    """Result of querying available next actions.

    Attributes:
        success: True if the query succeeded.
        slug: The engagement slug that was queried.
        status: Engagement lifecycle status (created, active,
            paused, aborted, completed).
        current_phase: Name of the currently active phase, or None.
        pending_phases: Ordered list of phase names not yet started.
        completed_phases: Ordered list of phase names that finished.
        available_commands: List of command strings valid for the
            current state (e.g. ["next", "abort", "status"]).
        blocked: True if the engagement is in a blocked state.
        block_reason: Human-readable explanation of why blocked.
        error: Error message if the query failed.
    """

    success: bool = True
    slug: str = ""
    status: str = ""
    current_phase: str | None = None
    pending_phases: list[str] = field(default_factory=list)
    completed_phases: list[str] = field(default_factory=list)
    available_commands: list[str] = field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""
    error: str = ""


class WhatsNextEngine:
    """Queries what actions are available for a given engagement.

    Stateless engine that reads engagement and workflow state to
    determine available commands and next steps.

    Command availability is determined by engagement status:
    - CREATED → next, abort, status
    - ACTIVE → next, abort, status, phases
    - PAUSED → resume, abort, status
    - COMPLETED → status (terminal)
    - ABORTED → status (terminal)
    """

    def __init__(
        self,
        workflow_orchestrator: Any = None,
        engagement_repository: Any = None,
    ) -> None:
        """Initialise the WhatsNextEngine.

        Args:
            workflow_orchestrator: WorkflowOrchestrator for checking
                workflow state. If None, runs in stub mode.
            engagement_repository: EngagementRepository for loading
                engagement state. If None, uses stub.
        """
        self._workflow_orchestrator = workflow_orchestrator
        self._engagement_repository = engagement_repository

    def query(
        self,
        slug: str,
    ) -> WhatsNextResult:
        """Query what actions are available for this engagement.

        Args:
            slug: The engagement slug to query.

        Returns:
            WhatsNextResult with available actions and state info.
        """
        if self._engagement_repository is None and self._workflow_orchestrator is None:
            return self._stub_query(slug)

        try:
            # Try loading from engagement repository first
            engagement = None
            if self._engagement_repository is not None:
                engagement = self._engagement_repository.load(slug)

            # Get workflow state
            state = None
            if self._workflow_orchestrator is not None:
                state = self._workflow_orchestrator.get_state(slug)

            # Build result
            status = (engagement.status.value if engagement else
                      state.status.value if state else "unknown")

            # Determine current phase
            current_phase = None
            if state and state.current_phase:
                current_phase = state.current_phase
            elif engagement and engagement.current_phase:
                current_phase = engagement.current_phase

            pending = list(state.pending_phases) if state else []
            completed = list(state.completed_phases) if state else []

            commands = self._available_commands_for_status(status)

            return WhatsNextResult(
                success=True,
                slug=slug,
                status=status,
                current_phase=current_phase,
                pending_phases=pending,
                completed_phases=completed,
                available_commands=commands,
                blocked=self._is_blocked(status),
                block_reason=self._block_reason(status),
            )

        except Exception as exc:
            return WhatsNextResult(
                success=False,
                slug=slug,
                error=f"Failed to query engagement state: {exc}",
            )

    def available_commands(
        self,
        slug: str,
    ) -> list[str]:
        """Get the list of valid commands for the current engagement state.

        Convenience method that calls query() and returns only the
        command list.

        Args:
            slug: The engagement slug.

        Returns:
            List of command strings valid for the current state.
        """
        result = self.query(slug)
        return result.available_commands

    def _available_commands_for_status(
        self,
        status: str,
    ) -> list[str]:
        """Determine available commands based on engagement status.

        Args:
            status: Engagement lifecycle status string.

        Returns:
            List of valid command type strings.
        """
        base_commands = ["query_status", "query_whats_next"]

        status_command_map: dict[str, set[str]] = {
            "created": {"next", "abort_engagement"},
            "active": {"next", "abort_engagement", "enter_phase"},
            "paused": {"resume_engagement", "abort_engagement"},
            "completed": set(),
            "aborted": set(),
        }

        extra = status_command_map.get(status, base_commands)
        return base_commands + sorted(extra - set(base_commands))

    def _is_blocked(
        self,
        status: str,
    ) -> bool:
        """Check if the engagement is blocked."""
        return status in ("aborted", "completed")

    def _block_reason(
        self,
        status: str,
    ) -> str:
        """Get human-readable block reason."""
        reasons = {
            "completed": "Engagement has completed all phases.",
            "aborted": "Engagement was aborted.",
        }
        return reasons.get(status, "")

    def _stub_query(self, slug: str) -> WhatsNextResult:
        """Return a stub result when no dependencies are configured.

        Args:
            slug: The engagement slug.

        Returns:
            WhatsNextResult with stub data.
        """
        return WhatsNextResult(
            success=True,
            slug=slug,
            status="stub",
            available_commands=[
                "query_status",
                "query_whats_next",
                "next",
                "abort_engagement",
            ],
        )
