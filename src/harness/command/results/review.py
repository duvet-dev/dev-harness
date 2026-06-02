"""Typed results for review operations.

Covers: finish_engagement, review_engagement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.command.types import TypedResult


@dataclass(frozen=True)
class FinishEngagementResult(TypedResult):
    """Result of finishing an engagement."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    head_sha: str = ""
    branch: str = ""
    slug: str = ""
    completed_engagement: bool = False
    re_assessment: dict[str, Any] | None = None
    error: str = ""


@dataclass(frozen=True)
class ReviewEngagementResult(TypedResult):
    """Result of a review decision."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    decision: str = ""
    temporal_ok: bool = False
    snapshot_updated: bool = False
    error: str = ""


__all__ = [
    "FinishEngagementResult",
    "ReviewEngagementResult",
]
