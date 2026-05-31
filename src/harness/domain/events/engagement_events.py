"""Engagement domain events — event types for the engagement lifecycle.

Published by the Engagement aggregate when state transitions occur.
Event handlers can react to these events for side effects (logging,
snapshots, notifications, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from harness.domain.events.event_bus import Event


@dataclass
class EngagementCreated(Event):
    """Published when a new engagement is created."""

    slug: str
    session_type: str
    created_at: datetime = datetime.now(timezone.utc)


@dataclass
class EngagementStarted(Event):
    """Published when an engagement transitions from CREATED to ACTIVE."""

    slug: str
    started_at: datetime = datetime.now(timezone.utc)


@dataclass
class EngagementStatusChanged(Event):
    """Published when an engagement's status changes."""

    slug: str
    old_status: str
    new_status: str
    changed_at: datetime = datetime.now(timezone.utc)


@dataclass
class EngagementCompleted(Event):
    """Published when an engagement reaches COMPLETED status."""

    slug: str
    completed_at: datetime = datetime.now(timezone.utc)


@dataclass
class EngagementAborted(Event):
    """Published when an engagement is aborted."""

    slug: str
    reason: str = ""
    aborted_at: datetime = datetime.now(timezone.utc)


@dataclass
class PhaseTransitioned(Event):
    """Published when an engagement transitions between phases."""

    slug: str
    from_phase: str
    to_phase: str
    transitioned_at: datetime = datetime.now(timezone.utc)


@dataclass
class WaveCommitted(Event):
    """Published when a wave is committed within an engagement."""

    slug: str
    wave_id: str
    wave_name: str
    committed_at: datetime = datetime.now(timezone.utc)
