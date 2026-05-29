"""CommandBus package — DDD command bus infrastructure.

Provides the CommandBus, CommandRegistry, and delegation-thin handler
pattern for the Dev Harness engagement lifecycle.

See V7 §5.20 for the full design.
"""

from harness.command.bus import CommandBus
from harness.command.registry import CommandRegistry
from harness.command.types import Command, CommandHandler, CommandResult

__all__ = [
    "CommandBus",
    "CommandRegistry",
    "Command",
    "CommandHandler",
    "CommandResult",
]
