"""Command types — shared contracts for the CommandBus.

Defines the base Command dataclass, CommandResult, and CommandHandler
abstract base class used by all delegation-thin handlers.

WAVE 1: Adds typed generic infrastructure alongside existing concrete types.
Old patterns (Command, CommandResult, CommandHandler) remain unchanged for
backward compatibility during migration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, Protocol, TypeVar


# ====================================================================
# Legacy types (concrete, backward-compat during migration)
# ====================================================================


@dataclass
class Command:
    """Base dataclass for all commands dispatched via CommandBus.

    Attributes:
        slug: Unique identifier for this command instance (e.g. engagement slug).
        command_type: Machine-readable command type string (e.g. "create_engagement").
        data: Optional payload dict for additional command parameters.
    """

    slug: str
    command_type: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandResult:
    """Result of a command dispatch.

    Attributes:
        success: Whether the command was handled successfully.
        error: Error message if success is False.
        message: Human-readable result message.
        data: Optional result payload.
    """

    success: bool = True
    error: str = ""
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class CommandHandler(ABC):
    """Abstract base class for all command handlers.

    Subclasses implement ``handle()`` to process a specific command type.
    Handlers are delegation-thin — they call exactly one business component
    method and wrap the result in a CommandResult.
    """

    @abstractmethod
    def handle(self, command: Command) -> CommandResult:
        """Handle a command and return a result.

        Args:
            command: The command to handle.

        Returns:
            CommandResult indicating success or failure.
        """
        ...


# ====================================================================
# New typed infrastructure (Wave 1+)
# ====================================================================


# Type variables for generic handlers
TCommand_co = TypeVar("TCommand_co", bound=Command, covariant=True)
TResult_co = TypeVar("TResult_co", bound=CommandResult, covariant=True)
TCommand = TypeVar("TCommand", bound=Command)
TResult = TypeVar("TResult", bound=CommandResult)

# Separate type variables for typed command/result subclasses
TTypedCommand = TypeVar("TTypedCommand", bound="TypedCommand")
TTypedResult = TypeVar("TTypedResult", bound="TypedResult")


class TypedCommand:
    """Base type for typed commands. Marker base — no shared fields.

    Used by fully typed handlers in the post-migration command subsystem.
    Subclasses are frozen dataclasses with explicit typed fields.
    """

    __slots__ = ()  # prevent __dict__ on dataclass subclasses


class TypedResult:
    """Base type for typed results. Shared structural fields.

    Subclasses must define at least: success, message.
    """

    __slots__ = ()


class TypedHandler(ABC, Generic[TCommand, TResult]):
    """Generic handler for typed commands.

    Handles a single command type and returns a typed result.
    Type relationship is enforced by the generic signature.
    """

    @abstractmethod
    def handle(self, command: TCommand) -> TResult:
        ...


# ── Presenter protocol ─────────────────────────────────────────────


class CommandPresenter(Protocol[TResult]):
    """Format a typed result for display.

    Separate from handler — CLI, REPL, and sessions each have their
    own presenter implementations.
    """

    def present(self, result: TResult) -> str:
        """Return formatted output string (success case)."""
        ...

    def present_error(self, result: TResult) -> str:
        """Return formatted error string (failure case)."""
        ...


__all__ = [
    # Legacy types
    "Command",
    "CommandResult",
    "CommandHandler",
    # Typed infrastructure
    "TypedCommand",
    "TypedResult",
    "TypedHandler",
    "CommandPresenter",
    # Type variables
    "TCommand",
    "TResult",
    "TCommand_co",
    "TResult_co",
    "TTypedCommand",
    "TTypedResult",
]
