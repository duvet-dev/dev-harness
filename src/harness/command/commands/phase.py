"""Typed commands for phase lifecycle operations.

Covers: enter_phase, manage_phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness.command.types import TypedCommand
from harness.domain.enums import PhaseName


@dataclass(frozen=True)
class EnterPhaseCommand(TypedCommand):
    """Enter a phase in an engagement."""

    slug: str
    phase: str
    force: bool = False
    root: Path | None = None


@dataclass(frozen=True)
class ManagePhaseCommand(TypedCommand):
    """Manage engagement phases: list, navigate, feedback, resume, status."""

    slug: str
    action: str
    target: str | None = None
    feedback_reason: str = ""
    force: bool = False
    root: str = "."


__all__ = [
    "EnterPhaseCommand",
    "ManagePhaseCommand",
]
