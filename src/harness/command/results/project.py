"""Typed results for project initialisation operations.

Covers: init_project.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness.command.types import TypedResult


@dataclass(frozen=True)
class InitProjectResult(TypedResult):
    """Result of project initialisation."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    project: str = ""
    template: str | None = None
    path: str = ""
    git_initted: bool = False
    error: str = ""


__all__ = [
    "InitProjectResult",
]
