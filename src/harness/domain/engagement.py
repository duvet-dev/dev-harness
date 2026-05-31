"""Engagement aggregate root — consolidates engagement lifecycle.

Replaces the old engagement module files (model.py, lifecycle.py,
startup.py, resolver.py, checkpoint.py, feedback.py, health.py,
rename.py, repository.py, phase_state.py) with a single aggregate
root that manages the engagement lifecycle and publishes domain events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from harness.domain.enums import SessionType
from harness.domain.events.engagement_events import (
    EngagementAborted,
    EngagementCompleted,
    EngagementCreated,
    EngagementStarted,
    EngagementStatusChanged,
    PhaseTransitioned,
    WaveCommitted,
)
from harness.domain.events.event_bus import EventBus
from harness.domain.identifiers import Slug


class EngagementStatus(str):
    """Lifecycle status of an engagement.

    CREATED -> ACTIVE -> COMPLETED (or -> PAUSED -> ACTIVE -> COMPLETED)
    or -> ABORTED at any point.
    """

    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    ABORTED = "aborted"
    COMPLETED = "completed"


@dataclass
class HealthWarning:
    """A non-fatal warning about engagement health."""

    type: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Engagement:
    """Aggregate root for the engagement lifecycle.

    Manages engagement state and publishes domain events when
    state transitions occur.
    """

    slug: Slug
    workflow_name: str = "standard"
    session_type: SessionType = SessionType.GREENFIELD
    current_phase: str | None = None
    status: str = EngagementStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    target_branch: str = ""
    warnings: list[HealthWarning] = field(default_factory=list)
    _events: list[object] = field(default_factory=list)
    _event_bus: EventBus = field(default_factory=EventBus)

    # ── Lifecycle transitions ─────────────────────────────────────────────

    def start(self) -> None:
        """Transition engagement from CREATED to ACTIVE.

        Raises:
            ValueError: If engagement is not in CREATED status.
        """
        if self.status != EngagementStatus.CREATED:
            raise ValueError(
                f"Cannot start engagement in status '{self.status}'; "
                f"expected '{EngagementStatus.CREATED}'"
            )
        self.status = EngagementStatus.ACTIVE
        self.last_active = datetime.now(timezone.utc)
        self._publish(EngagementStarted(slug=str(self.slug)))

    def complete(self) -> None:
        """Mark engagement as completed."""
        self.status = EngagementStatus.COMPLETED
        self.last_active = datetime.now(timezone.utc)
        self._publish(EngagementCompleted(slug=str(self.slug)))

    def abort(self, reason: str = "") -> None:
        """Abort the engagement."""
        old_status = self.status
        self.status = EngagementStatus.ABORTED
        self.last_active = datetime.now(timezone.utc)
        self._publish(EngagementAborted(slug=str(self.slug), reason=reason))

    def pause(self) -> None:
        """Pause the engagement."""
        if self.status != EngagementStatus.ACTIVE:
            raise ValueError(
                f"Cannot pause engagement in status '{self.status}'; "
                f"expected '{EngagementStatus.ACTIVE}'"
            )
        old_status = self.status
        self.status = EngagementStatus.PAUSED
        self._publish(
            EngagementStatusChanged(
                slug=str(self.slug),
                old_status=old_status,
                new_status=self.status,
            )
        )

    def resume(self) -> None:
        """Resume a paused engagement."""
        if self.status != EngagementStatus.PAUSED:
            raise ValueError(
                f"Cannot resume engagement in status '{self.status}'; "
                f"expected '{EngagementStatus.PAUSED}'"
            )
        self.status = EngagementStatus.ACTIVE
        self.last_active = datetime.now(timezone.utc)
        self._publish(EngagementStatusChanged(
            slug=str(self.slug),
            old_status=EngagementStatus.PAUSED,
            new_status=EngagementStatus.ACTIVE,
        ))

    def transition_phase(self, to_phase: str) -> None:
        """Transition to a new phase.

        Args:
            to_phase: The phase to transition to.
        """
        from_phase = self.current_phase
        self.current_phase = to_phase
        self.last_active = datetime.now(timezone.utc)
        if from_phase is not None:
            self._publish(PhaseTransitioned(
                slug=str(self.slug),
                from_phase=from_phase,
                to_phase=to_phase,
            ))

    def commit_wave(self, wave_id: str, wave_name: str = "") -> None:
        """Record a wave being committed.

        Args:
            wave_id: The wave identifier.
            wave_name: Optional human-readable wave name.
        """
        self.last_active = datetime.now(timezone.utc)
        self._publish(WaveCommitted(
            slug=str(self.slug),
            wave_id=wave_id,
            wave_name=wave_name or wave_id,
        ))

    def add_warning(self, warning_type: str, message: str) -> None:
        """Add a health warning to the engagement.

        Args:
            warning_type: Machine-readable warning type.
            message: Human-readable description.
        """
        self.warnings.append(HealthWarning(type=warning_type, message=message))

    def clear_warnings(self) -> None:
        """Clear all health warnings."""
        self.warnings.clear()

    # ── Event publishing ──────────────────────────────────────────────────

    def _publish(self, event: object) -> None:
        """Publish a domain event through the event bus.

        Args:
            event: The event to publish.
        """
        self._events.append(event)
        self._event_bus.publish(event)

    @property
    def event_bus(self) -> EventBus:
        """Get the event bus for this aggregate."""
        return self._event_bus

    @event_bus.setter
    def event_bus(self, bus: EventBus) -> None:
        """Set the event bus for this aggregate."""
        self._event_bus = bus

    def pop_events(self) -> list[object]:
        """Get and clear pending domain events.

        Returns:
            List of events published since last pop.
        """
        events = list(self._events)
        self._events.clear()
        return events

    def __str__(self) -> str:
        return f"Engagement(slug={self.slug}, status={self.status})"
