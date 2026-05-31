"""Engagement data model.

Defines the Engagement dataclass, EngagementStatus enum,
and HealthWarning — the core engagement lifecycle types.
See V7 §5.23 for the design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from harness.domain.enums import SessionType


class EngagementStatus(str, Enum):
    """Lifecycle status of an engagement.

    CREATED → ACTIVE → COMPLETED (or → PAUSED → ACTIVE → COMPLETED)
    or → ABORTED at any point.
    """

    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    ABORTED = "aborted"
    COMPLETED = "completed"


@dataclass
class HealthWarning:
    """A non-fatal warning about engagement health.

    Attributes:
        type: Machine-readable warning type (e.g. "dirty_repo",
            "branch_missing", "stale_engagement").
        message: Human-readable description of the warning.
        timestamp: When the warning was recorded.
    """

    type: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Engagement:
    """Represents a single development engagement session.

    Attributes:
        slug: Unique human-readable identifier for the engagement.
        workflow_name: Name of the workflow to execute.
        session_type: Type of session (greenfield, refactoring,
            get-well, etc.).
        current_phase: Name of the currently active phase, or None
            if not started.
        status: Current lifecycle status.
        created_at: When the engagement was created.
        last_active: When the engagement was last active.
        target_branch: Git branch for this engagement's work.
        warnings: List of non-fatal health warnings.
    """

    slug: str
    workflow_name: str = "standard"
    session_type: SessionType = SessionType.GREENFIELD
    current_phase: str | None = None
    status: EngagementStatus = EngagementStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    target_branch: str = ""
    warnings: list[HealthWarning] = field(default_factory=list)
