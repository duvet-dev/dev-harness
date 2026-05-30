"""CommandRegistry — maps command types to handler instances.

Provides registration and lookup of command handlers by command type
string. Used by CommandBus to resolve handlers at dispatch time.
"""

from __future__ import annotations

from harness.command.types import CommandHandler
from harness.errors import HandlerNotFoundError


class CommandRegistry:
    """Registry mapping command type strings to handler instances.

    Thread-safe for reads (registration is typically done at startup).
    """

    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {}

    def register(self, command_type: str, handler: CommandHandler) -> None:
        """Register a handler for a command type.

        Args:
            command_type: The command type string (e.g. "create_engagement").
            handler: A CommandHandler instance.

        Raises:
            ValueError: If a handler is already registered for this type.
        """
        if not isinstance(command_type, str) or not command_type:
            raise ValueError("command_type must be a non-empty string")
        if command_type in self._handlers:
            raise ValueError(
                f"Handler already registered for command type '{command_type}'"
            )
        self._handlers[command_type] = handler

    def get_handler(self, command_type: str) -> CommandHandler | None:
        """Look up a handler for a command type.

        Args:
            command_type: The command type string to look up.

        Returns:
            The registered handler, or None if not found.
        """
        return self._handlers.get(command_type)

    def register_all(self, handlers: dict[str, CommandHandler]) -> None:
        """Bulk register handlers from a dict.

        Args:
            handlers: Dict mapping command_type strings to handler instances.

        Raises:
            ValueError: If any command type has a conflict.
        """
        for command_type, handler in handlers.items():
            self.register(command_type, handler)

    def has_handler(self, command_type: str) -> bool:
        """Check if a handler is registered for a command type.

        Args:
            command_type: The command type string to check.

        Returns:
            True if a handler is registered.
        """
        return command_type in self._handlers

    def list_registered(self) -> list[str]:
        """List all registered command types.

        Returns:
            Sorted list of registered command type strings.
        """
        return sorted(self._handlers.keys())

    def clear(self) -> None:
        """Remove all registered handlers."""
        self._handlers.clear()

    def __len__(self) -> int:
        return len(self._handlers)
