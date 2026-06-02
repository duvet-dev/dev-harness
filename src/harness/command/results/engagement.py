"""Typed results for engagement lifecycle operations.

Covers: create_engagement, resume_engagement, abort_engagement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.command.types import TypedResult


@dataclass(frozen=True)
class CreateEngagementResult(TypedResult):
    """Result of creating an engagement."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    workflow_name: str | None = None
    status: str = ""
    current_phase: str | None = None
    target_branch: str | None = None
    branch_created: bool = False
    warnings: list[dict[str, str]] = field(default_factory=list)
    error: str = ""


@dataclass(frozen=True)
class ResumeEngagementResult(TypedResult):
    """Result of resuming an engagement."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    status: str = ""
    current_phase: str | None = None
    workflow_name: str | None = None
    warnings: list[dict[str, str]] = field(default_factory=list)
    error: str = ""


@dataclass(frozen=True)
class AbortEngagementResult(TypedResult):
    """Result of aborting an engagement."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    mode: str = "graceful"
    previous_status: str = ""
    completed_phases: list[str] = field(default_factory=list)
    current_phase: str = ""
    error: str = ""


__all__ = [
    "CreateEngagementResult",
    "ResumeEngagementResult",
    "AbortEngagementResult",
]
