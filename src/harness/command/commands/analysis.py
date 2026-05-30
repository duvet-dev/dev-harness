"""Typed commands for analysis operations.

Covers: summary, inspect, assess.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness.command.types import TypedCommand


@dataclass(frozen=True)
class SummaryCommand(TypedCommand):
    """Run project summary analysis."""

    slug: str = ""
    deep: bool = False
    assess_flag: bool = False
    json_flag: bool = False
    reconcile: bool = False


@dataclass(frozen=True)
class InspectCommand(TypedCommand):
    """Run observer analysis."""

    slug: str = ""
    root: str = "."


@dataclass(frozen=True)
class AssessCommand(TypedCommand):
    """Run the full assessment on the project."""

    slug: str = ""
    root: str = "."
    deep_flag: bool = True
    project_type: str = "python"


__all__ = [
    "SummaryCommand",
    "InspectCommand",
    "AssessCommand",
]
