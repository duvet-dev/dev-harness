"""Typed commands for miscellaneous operations.

Covers: next, query_status, query_whats_next.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness.command.types import TypedCommand


@dataclass(frozen=True)
class NextCommand(TypedCommand):
    """Advance the engagement to the next step."""

    slug: str


@dataclass(frozen=True)
class QueryStatusCommand(TypedCommand):
    """Query engagement health status."""

    slug: str


@dataclass(frozen=True)
class QueryWhatsNextCommand(TypedCommand):
    """Query available next actions for an engagement."""

    slug: str


__all__ = [
    "NextCommand",
    "QueryStatusCommand",
    "QueryWhatsNextCommand",
]
