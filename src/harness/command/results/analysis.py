"""Typed results for analysis operations.

Covers: summary, inspect, assess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.command.types import TypedResult


@dataclass(frozen=True)
class SummaryResult(TypedResult):
    """Result of project summary analysis."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    report: str = ""
    output_format: str = "markdown"
    error: str = ""


@dataclass(frozen=True)
class InspectResult(TypedResult):
    """Result of observer analysis."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    report: str = ""
    findings_count: int | str = "?"
    score: int | str = "?"
    error: str = ""


@dataclass(frozen=True)
class AssessResult(TypedResult):
    """Result of full assessment."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    report: str = ""
    findings_count: int | str = "?"
    score: int | str = "?"
    error: str = ""


__all__ = [
    "SummaryResult",
    "InspectResult",
    "AssessResult",
]
