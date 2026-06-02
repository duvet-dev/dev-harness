"""Typed results for miscellaneous operations.

Covers: next, query_status, query_whats_next.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.command.types import TypedResult


@dataclass(frozen=True)
class NextResult(TypedResult):
    """Result of advancing the engagement."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    error: str = ""


@dataclass(frozen=True)
class QueryStatusResult(TypedResult):
    """Result of querying engagement health."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    all_ok: bool = True
    warnings: list[dict[str, str]] = field(default_factory=list)
    error: str = ""


@dataclass(frozen=True)
class QueryWhatsNextResult(TypedResult):
    """Result of querying next actions."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    status: str = ""
    current_phase: str = ""
    pending_phases: list[str] = field(default_factory=list)
    completed_phases: list[str] = field(default_factory=list)
    available_commands: list[str] = field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""
    error: str = ""


__all__ = [
    "NextResult",
    "QueryStatusResult",
    "QueryWhatsNextResult",
]
