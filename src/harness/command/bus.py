"""CommandBus — core dispatch engine for the command pattern.

The CommandBus registers command types with handlers and dispatches
commands to their registered handlers. It supports both sync and
async dispatch.

See V7 §5.20 for the design.
"""

from __future__ import annotations

import asyncio
import inspect

from harness.command.registry import CommandRegistry
from harness.command.types import Command, CommandHandler, CommandResult
from harness.errors import UnknownCommandError


class CommandBus:
    """Dispatches commands to registered handlers.

    Usage::

        bus = CommandBus()
        registry = CommandRegistry()
        registry.register("create_engagement", CreateEngagementHandler())
        bus.register_from(registry)

        result = bus.dispatch(Command(slug="my-eng", command_type="create_engagement"))
    """

    def __init__(self, registry: CommandRegistry | None = None) -> None:
        self._registry = registry or CommandRegistry()

    @property
    def registry(self) -> CommandRegistry:
        """The underlying CommandRegistry."""
        return self._registry

    def register(self, command_type: str, handler: CommandHandler) -> None:
        """Register a handler for a command type on the internal registry.

        Args:
            command_type: The command type string.
            handler: A CommandHandler instance.
        """
        self._registry.register(command_type, handler)

    def register_from(self, registry: CommandRegistry) -> None:
        """Import all registrations from another registry.

        Args:
            registry: A CommandRegistry whose handlers to import.
        """
        for command_type in registry.list_registered():
            handler = registry.get_handler(command_type)
            if handler is not None:
                self._registry.register(command_type, handler)

    def dispatch(self, command: Command) -> CommandResult:
        """Dispatch a command to its registered handler.

        Args:
            command: The command to dispatch. ``command.command_type`` must
                match a registered handler.

        Returns:
            CommandResult from the handler.

        Raises:
            UnknownCommandError: If no handler is registered for the command type.
        """
        handler = self._find_handler(command)
        return handler.handle(command)

    async def dispatch_async(self, command: Command) -> CommandResult:
        """Dispatch a command asynchronously.

        If the registered handler's ``handle()`` method is a coroutine
        function, it is awaited. Otherwise it runs synchronously.

        Args:
            command: The command to dispatch.

        Returns:
            CommandResult from the handler.

        Raises:
            UnknownCommandError: If no handler is registered for the command type.
        """
        handler = self._find_handler(command)
        result = handler.handle(command)
        if inspect.iscoroutine(result):
            return await result
        return result

    def _find_handler(self, command: Command) -> CommandHandler:
        """Find the handler for a command, raising UnknownCommandError if not found.

        Args:
            command: The command to find a handler for.

        Returns:
            The registered CommandHandler.

        Raises:
            UnknownCommandError: If no handler is found.
        """
        handler = self._registry.get_handler(command.command_type)
        if handler is None:
            raise UnknownCommandError(
                f"No handler registered for command type '{command.command_type}'"
            )
        return handler
