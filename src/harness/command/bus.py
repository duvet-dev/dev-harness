"""CommandBus — core dispatch engine for the typed command pattern.

The CommandBus registers concrete command types with handlers and
dispatches typed commands to their registered handlers. Supports both
sync and async dispatch via type-based lookup only (string-based
dispatch was removed in the typed-command migration).

Usage::

    bus = CommandBus()
    bus.register_type(CreateEngagementHandler(), CreateEngagementCommand)

    # Type-based dispatch
    result = bus.dispatch(CreateEngagementCommand(slug="my-eng"))
"""

from __future__ import annotations

import asyncio
import inspect

from harness.command.types import (
    CommandHandler,
    CommandResult,
    TypedCommand,
    TypedHandler,
)
from harness.errors import UnknownCommandError


class CommandBus:
    """Dispatches typed commands to their registered handlers.

    Only supports type-based dispatch: ``dispatch(TypedCommand)``
    looks up the handler by ``type(command)``.

    Usage::

        bus = CommandBus()
        bus.register_type(CreateEngagementHandler(), CreateEngagementCommand)
        result = bus.dispatch(CreateEngagementCommand(slug="my-eng"))
    """

    def __init__(self) -> None:
        # Type-based handler map: type -> handler
        self._type_handlers: dict[type, CommandHandler | TypedHandler] = {}

    # ── Type-based registration ─────────────────────────────────────────

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

    def dispatch(self, command: TypedCommand) -> CommandResult:
        """Dispatch a typed command to its registered handler.

        Uses type-based lookup on ``type(command)``.

        Args:
            command: The typed command to dispatch.

        Returns:
            CommandResult from the handler.

        Raises:
            UnknownCommandError: If no handler is registered for the command type.
        """
        handler = self._type_handlers.get(type(command))
        if handler is None:
            raise UnknownCommandError(
                f"No handler registered for command type {type(command).__name__}"
            )

        result = handler.handle(command)

        # If the handler returned a CommandResult, return it directly
        if isinstance(result, CommandResult):
            return result

        # Wrap typed results in CommandResult for a uniform API
        return CommandResult(
            success=getattr(result, "success", True),
            error=getattr(result, "error", ""),
            message=getattr(result, "message", str(result)),
            data={"typed_result": result},
        )

    async def dispatch_async(self, command: TypedCommand) -> CommandResult:
        """Dispatch a typed command asynchronously.

        If the registered handler's ``handle()`` method is a coroutine
        function, it is awaited. Otherwise it runs synchronously.

        Args:
            command: The typed command to dispatch.

        Returns:
            CommandResult from the handler.

        Raises:
            UnknownCommandError: If no handler is registered for the command type.
        """
        handler = self._type_handlers.get(type(command))
        if handler is None:
            raise UnknownCommandError(
                f"No handler registered for command type {type(command).__name__}"
            )

        result = handler.handle(command)
        if inspect.iscoroutine(result):
            result = await result

        if isinstance(result, CommandResult):
            return result

        return CommandResult(
            success=getattr(result, "success", True),
            error=getattr(result, "error", ""),
            message=getattr(result, "message", str(result)),
            data={"typed_result": result},
        )
