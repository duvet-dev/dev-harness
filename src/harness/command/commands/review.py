"""Typed commands for review operations.

Covers: finish_engagement, review_engagement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.command.types import TypedCommand


@dataclass(frozen=True)
class FinishEngagementCommand(TypedCommand):
    """Complete an engagement."""

    slug: str
    root: str = "."
    re_assess: bool = False


@dataclass(frozen=True)
class ReviewEngagementCommand(TypedCommand):
    """Record a gate review decision."""

    slug: str
    decision: str = ""
    root: str = "."
    feedback_items: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""


__all__ = [
    "FinishEngagementCommand",
    "ReviewEngagementCommand",
]
