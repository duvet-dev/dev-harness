"""Workflow data model — V7 §5.14.

Defines the Workflow dataclass and WorkflowState tracking model
for full workflow lifecycle management.

WorkflowState tracks which phases are pending, completed, and the
currently active phase — used by WorkflowOrchestrator to manage
phase-to-phase transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkflowStatus(str, Enum):
    """Lifecycle status of a workflow execution.

    PENDING → ACTIVE → COMPLETED (or → FAILED)
    """

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Workflow:
    """A named collection of phases forming a development workflow.

    Attributes:
        name: Unique workflow name (e.g. "standard", "quick-fix").
        phases: Ordered list of phase names in execution order.
            Referenced by Phase definitions in phase config.
    """

    name: str
    phases: list[str] = field(default_factory=list)


@dataclass
class WorkflowState:
    """Runtime state for an active workflow execution.

    Tracks the current position within a workflow's phase sequence
    and the status of each phase.

    Attributes:
        workflow_name: Name of the executing workflow.
        slug: Unique identifier for this workflow execution.
        current_phase: Name of the currently active phase, or None
            if not started or completed.
        pending_phases: Ordered list of phase names not yet started.
        completed_phases: Ordered list of phase names that have
            finished successfully.
        failed_phases: Ordered list of phase names that failed.
        status: Overall workflow lifecycle status.
        mode: Execution mode ("auto" or "manual").
        metadata: Arbitrary key-value metadata for extension.
    """

    workflow_name: str
    slug: str = ""
    current_phase: str | None = None
    pending_phases: list[str] = field(default_factory=list)
    completed_phases: list[str] = field(default_factory=list)
    failed_phases: list[str] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    mode: str = "auto"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Check if the workflow is currently active."""
        return self.status == WorkflowStatus.ACTIVE

    @property
    def is_completed(self) -> bool:
        """Check if the workflow has completed all phases."""
        return self.status == WorkflowStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if the workflow has failed."""
        return self.status == WorkflowStatus.FAILED

    @property
    def all_phases(self) -> list[str]:
        """Return all phases in original order: completed + current + pending.

        Excludes failed phases so the sequence shows un-failed flow.
        """
        result: list[str] = []
        result.extend(self.completed_phases)
        if self.current_phase:
            result.append(self.current_phase)
        result.extend(
            p for p in self.pending_phases if p not in result
        )
        return result

    @property
    def progress(self) -> float:
        """Calculate workflow completion progress as a fraction (0.0–1.0).

        Returns 0.0 if there are no phases defined.
        """
        total = len(self.completed_phases) + len(self.pending_phases) + (1 if self.current_phase else 0)
        if total == 0:
            return 0.0
        return len(self.completed_phases) / total

    def mark_phase_started(self, phase_name: str) -> None:
        """Mark a phase as started, moving it from pending to current.

        Args:
            phase_name: Name of the phase to start.

        Raises:
            ValueError: If the phase is not in pending_phases and
                is not the first phase being started.
        """
        if self.current_phase is not None:
            raise ValueError(
                f"Cannot start '{phase_name}': phase "
                f"'{self.current_phase}' is still active"
            )

        if phase_name in self.pending_phases:
            self.pending_phases.remove(phase_name)
        self.current_phase = phase_name
        if self.status == WorkflowStatus.PENDING:
            self.status = WorkflowStatus.ACTIVE

    def mark_phase_completed(self, phase_name: str) -> None:
        """Mark a phase as completed successfully.

        Args:
            phase_name: Name of the phase to mark complete.

        Raises:
            ValueError: If the phase is not the current phase.
        """
        if self.current_phase != phase_name:
            raise ValueError(
                f"Cannot complete '{phase_name}': not the current phase "
                f"(current: '{self.current_phase}')"
            )

        self.completed_phases.append(phase_name)
        self.current_phase = None

        # Check if all phases are done
        if not self.pending_phases and self.current_phase is None:
            self.status = WorkflowStatus.COMPLETED

    def mark_phase_failed(self, phase_name: str) -> None:
        """Mark a phase as failed.

        Args:
            phase_name: Name of the phase that failed.
        """
        if self.current_phase == phase_name:
            self.failed_phases.append(phase_name)
            self.current_phase = None
            self.status = WorkflowStatus.FAILED

    def reset_to_phase(self, phase_name: str) -> None:
        """Reset workflow state so the given phase becomes current.

        All phases after the specified phase in the original sequence
        are moved back to pending. The specified phase becomes the
        current phase.

        Args:
            phase_name: Name of the phase to make current.

        Raises:
            ValueError: If the phase was not completed or pending.
        """
        if phase_name in self.completed_phases:
            # Move all phases after this one back to pending
            idx = self.completed_phases.index(phase_name)
            later_phases = self.completed_phases[idx + 1 :]
            self.completed_phases = self.completed_phases[:idx]
            self.pending_phases = later_phases + self.pending_phases

            self.current_phase = phase_name
            self.status = WorkflowStatus.ACTIVE
        elif phase_name in self.pending_phases:
            self.current_phase = phase_name
            self.pending_phases.remove(phase_name)
            self.status = WorkflowStatus.ACTIVE
        else:
            raise ValueError(
                f"Cannot reset to '{phase_name}': phase not found "
                f"in completed or pending phases"
            )

    @classmethod
    def from_workflow(
        cls,
        workflow: Workflow,
        slug: str = "",
        mode: str = "auto",
    ) -> WorkflowState:
        """Create a WorkflowState from a Workflow definition.

        Args:
            workflow: The Workflow definition to derive state from.
            slug: Unique identifier for this execution.
            mode: Execution mode ("auto" or "manual").

        Returns:
            A new WorkflowState with all phases set to pending.
        """
        return cls(
            workflow_name=workflow.name,
            slug=slug,
            pending_phases=list(workflow.phases),
            mode=mode,
        )


@dataclass
class WorkflowResult:
    """Result of entering or advancing a workflow.

    Attributes:
        success: True if the workflow operation succeeded.
        workflow_name: Name of the workflow that was executed.
        slug: Unique identifier for this workflow execution.
        current_phase: Name of the current (or resulting) phase.
        completed_phases: List of phases completed so far.
        pending_phases: List of phases remaining.
        status: Overall workflow lifecycle status.
        phase_result: Optional result from PhaseOrchestrator.
        error: Error message if the operation failed.
        escalation: Escalation target if advancement failed
            ("workflow", "user", or None).
        artifact_map: Mapping of phase names to lists of artifacts
            they produced.
        mode: Execution mode used ("auto" or "manual").
    """

    success: bool
    workflow_name: str = ""
    slug: str = ""
    current_phase: str | None = None
    completed_phases: list[str] = field(default_factory=list)
    pending_phases: list[str] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    phase_result: Any = None
    error: str | None = None
    escalation: str | None = None
    artifact_map: dict[str, list[Any]] = field(default_factory=dict)
    mode: str = "auto"
