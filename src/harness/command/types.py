"""Command types — shared contracts for the CommandBus.

Defines the base Command dataclass, CommandResult, and CommandHandler
abstract base class used by all delegation-thin handlers.

See V7 §5.20 for the design.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


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
