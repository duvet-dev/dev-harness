"""CommandBus package — DDD command bus infrastructure.

Provides the CommandBus and delegation-thin handler
pattern for the Dev Harness engagement lifecycle.
"""

from harness.command.bus import CommandBus
from harness.command.errors import HandlerError
from harness.command.setup import create_bus, get_shared_bus, reset_shared_bus
from harness.command.types import (
    CommandHandler,
    CommandPresenter,
    CommandResult,
    TypedCommand,
    TypedHandler,
    TypedResult,
)
from harness.domain.enums import (
    AbortMode,
    AutoMode,
    BranchStrategy,
    PhaseName,
    ReviewDecision,
    SessionType,
)

__all__ = [
    "CommandBus",
    "CommandHandler",
    "CommandResult",
    "CommandPresenter",
    "TypedCommand",
    "TypedResult",
    "TypedHandler",
    "HandlerError",
    "create_bus",
    "get_shared_bus",
    "reset_shared_bus",
    # Values
    "PhaseName",
    "SessionType",
    "AutoMode",
    "ReviewDecision",
    "AbortMode",
    "BranchStrategy",
]
