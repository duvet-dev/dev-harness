"""Typed commands for engagement lifecycle operations.

Covers: create_engagement, resume_engagement, abort_engagement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.command.types import TypedCommand
from harness.domain.enums import AutoMode, SessionType


@dataclass(frozen=True)
class CreateEngagementCommand(TypedCommand):
    """Create a new engagement."""

    slug: str
    workflow_name: str | None = None
    session_type: str = "greenfield"
    mode: str = "auto"


@dataclass(frozen=True)
class ResumeEngagementCommand(TypedCommand):
    """Resume an existing engagement."""

    slug: str
    mode: str = "auto"


@dataclass(frozen=True)
class AbortEngagementCommand(TypedCommand):
    """Abort an engagement."""

    slug: str
    mode: str = "graceful"


__all__ = [
    "CreateEngagementCommand",
    "ResumeEngagementCommand",
    "AbortEngagementCommand",
]
