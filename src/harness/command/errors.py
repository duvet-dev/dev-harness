"""Command subsystem errors.

Typed error classes for command dispatch failures.
UnknownCommandError is already defined in harness.errors for backward
compatibility; this module re-exports it and adds HandlerError.
"""

from __future__ import annotations

from harness.errors import UnknownCommandError


class HandlerError(Exception):
    """Raised when a command handler encounters an unexpected error.

    This is distinct from UnknownCommandError (no handler registered).
    HandlerError wraps exceptions from within a handler's handle() call.
    """

    def __init__(self, message: str = "", original: Exception | None = None) -> None:
        self.original = original
        super().__init__(message)


__all__ = [
    "UnknownCommandError",
    "HandlerError",
]
