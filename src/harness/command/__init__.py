"""CommandBus package — DDD command bus infrastructure.

Provides the CommandBus, CommandRegistry, and delegation-thin handler
pattern for the Dev Harness engagement lifecycle.
"""

from harness.command.bus import CommandBus
from harness.command.errors import HandlerError
from harness.command.registry import CommandRegistry
from harness.command.setup import create_bus
from harness.command.types import (
    Command,
    CommandHandler,
    CommandPresenter,
    CommandResult,
    TypedCommand,
    TypedHandler,
    TypedResult,
)
from harness.command.values import (
    AbortMode,
    AutoMode,
    BranchStrategy,
    EngStatus,
    PhaseName,
    ReviewDecision,
    SessionType,
)

__all__ = [
    "CommandBus",
    "CommandRegistry",
    "Command",
    "CommandHandler",
    "CommandResult",
    "CommandPresenter",
    "TypedCommand",
    "TypedResult",
    "TypedHandler",
    "HandlerError",
    "create_bus",
    # Values
    "PhaseName",
    "SessionType",
    "AutoMode",
    "EngStatus",
    "ReviewDecision",
    "AbortMode",
    "BranchStrategy",
]
