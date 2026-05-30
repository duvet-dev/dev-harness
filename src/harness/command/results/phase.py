"""Typed results for phase lifecycle operations.

Covers: enter_phase, manage_phase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.command.types import TypedResult


@dataclass(frozen=True)
class EnterPhaseResult(TypedResult):
    """Result of entering a phase."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    phase: str = ""
    started: bool = False
    error: str = ""


@dataclass(frozen=True)
class ManagePhaseResult(TypedResult):
    """Result of phase management actions."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    action: str = ""
    phases: list[dict[str, Any]] = field(default_factory=list)
    from_phase: str = ""
    to_phase: str = ""
    checkpoint: str = ""
    feedback_path: str = ""
    resumed: bool = False
    findings_count: int = 0
    phase: str = ""
    error: str = ""


__all__ = [
    "EnterPhaseResult",
    "ManagePhaseResult",
]
