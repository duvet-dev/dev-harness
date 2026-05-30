"""Typed commands for session and chat operations.

Covers: session, chat.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness.command.types import TypedCommand


@dataclass(frozen=True)
class SessionCommand(TypedCommand):
    """Start a phase-walking session."""

    slug: str
    phase: str = "requirements"
    session_type: str | None = None
    context_tier: int = 2
    get_well: bool = False


@dataclass(frozen=True)
class ChatCommand(TypedCommand):
    """Open a chat session."""

    slug: str
    prompt: str | None = None
    phase: str = "design"
    context_tier: int = 2


__all__ = [
    "SessionCommand",
    "ChatCommand",
]
