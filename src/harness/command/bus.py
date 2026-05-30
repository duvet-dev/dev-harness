"""CommandBus — core dispatch engine for the command pattern.

The CommandBus registers command types with handlers and dispatches
commands to their registered handlers. It supports both sync and
async dispatch, and both string-based (legacy) and type-based (new)
dispatch mechanisms.
"""

from __future__ import annotations

import asyncio
import inspect

from harness.command.registry import CommandRegistry
from harness.command.types import (
    Command,
    CommandHandler,
    CommandResult,
    TypedCommand,
    TypedHandler,
)
from harness.errors import UnknownCommandError


class CommandBus:
    """Dispatches commands to registered handlers.

    Supports two dispatch modes:
    1. **String-based** (legacy): dispatch by ``command.command_type`` string.
    2. **Type-based** (new): dispatch by ``type(command)``.

    Usage::

        bus = CommandBus()
        registry = CommandRegistry()
        registry.register("create_engagement", CreateEngagementHandler())
        bus.register_from(registry)

        # String-based dispatch (legacy)
        result = bus.dispatch(Command(slug="my-eng", command_type="create_engagement"))

        # Type-based dispatch (new)
        result = bus.dispatch(CreateEngagementCommand(slug="my-eng"))
    """

    def __init__(self, registry: CommandRegistry | None = None) -> None:
        self._registry = registry or CommandRegistry()
        # Type-based handler map: type -> handler
        self._type_handlers: dict[type, CommandHandler | TypedHandler] = {}

    @property
    def registry(self) -> CommandRegistry:
        """The underlying string-based CommandRegistry."""
        return self._registry

    # ── String-based registration (legacy) ──────────────────────────────

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

    # ── Type-based registration (new) ───────────────────────────────────

    def register_type(
        self,
        handler: TypedHandler,
        command_type: type,
    ) -> None:
        """Register a handler for a typed command class.

        Args:
            handler: A TypedHandler instance.
            command_type: The command class to handle.
        """
        self._type_handlers[command_type] = handler

    def register_types(self, handlers: dict[type, TypedHandler]) -> None:
        """Bulk register type-based handlers.

        Args:
            handlers: Dict mapping command types to handler instances.
        """
        self._type_handlers.update(handlers)

    # ── Dispatch ───────────────────────────────────────────────────────

    def dispatch(self, command: Command | TypedCommand) -> CommandResult:
        """Dispatch a command to its registered handler.

        Uses type-based dispatch if available (for TypedCommand subclasses),
        falling back to string-based dispatch (legacy Command with
        command_type attribute).

        Args:
            command: The command to dispatch.

        Returns:
            CommandResult from the handler.

        Raises:
            UnknownCommandError: If no handler is registered for the command.
        """
        # Try type-based dispatch first
        if isinstance(command, TypedCommand):
            handler = self._type_handlers.get(type(command))
            if handler is not None:
                result = handler.handle(command)
                if isinstance(result, CommandResult):
                    return result
                # Typed result — wrap in CommandResult for backward compat
                return CommandResult(
                    success=getattr(result, "success", True),
                    message=getattr(result, "message", str(result)),
                    data={"typed_result": result},
                )

        # Fall back to string-based dispatch (legacy)
        if isinstance(command, Command):
            handler = self._find_handler(command)
            return handler.handle(command)

        raise UnknownCommandError(
            f"No handler registered for command type {type(command).__name__}"
        )

    async def dispatch_async(self, command: Command | TypedCommand) -> CommandResult:
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
        # Try type-based dispatch first
        if isinstance(command, TypedCommand):
            handler = self._type_handlers.get(type(command))
            if handler is not None:
                result = handler.handle(command)
                if inspect.iscoroutine(result):
                    result = await result
                if isinstance(result, CommandResult):
                    return result
                return CommandResult(
                    success=getattr(result, "success", True),
                    message=getattr(result, "message", str(result)),
                    data={"typed_result": result},
                )

        # Fall back to string-based dispatch (legacy)
        if isinstance(command, Command):
            handler = self._find_handler(command)
            result = handler.handle(command)
            if inspect.iscoroutine(result):
                return await result
            return result

        raise UnknownCommandError(
            f"No handler registered for command type {type(command).__name__}"
        )

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
