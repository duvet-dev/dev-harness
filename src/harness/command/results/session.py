"""Typed results for session and chat operations.

Covers: session, chat.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness.command.types import TypedResult


@dataclass(frozen=True)
class SessionResult(TypedResult):
    """Result of starting a session."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    phase: str = ""
    phase_entered: str = ""
    session_type: str = ""
    context_tier: int = 2
    get_well: bool = False
    error: str = ""


@dataclass(frozen=True)
class ChatResult(TypedResult):
    """Result of opening a chat session."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    phase: str = ""
    context_tier: int = 2
    prompt: str | None = None
    error: str = ""


__all__ = [
    "SessionResult",
    "ChatResult",
]
