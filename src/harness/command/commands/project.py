"""Typed commands for project initialisation operations.

Covers: init_project.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from harness.command.types import TypedCommand


@dataclass(frozen=True)
class InitProjectCommand(TypedCommand):
    """Initialise a new harness project."""

    project_dir: str | None = None
    template: str | None = None
    seed: str | None = None
    no_git: bool = False
    force: bool = False
    root: Path = field(default_factory=lambda: Path.cwd())


__all__ = [
    "InitProjectCommand",
]
