"""Command subsystem setup — bus factory and handler registration.

Provides a single ``create_bus()`` factory function that creates a fully
configured CommandBus with all handlers registered. This is the entry
point for CLI, REPL, and session integration.

As handlers are migrated to typed commands (Waves 2-6), they are
registered via ``bus.register_type()`` instead of the legacy
``bus.register()``.
"""

from __future__ import annotations

from harness.command.bus import CommandBus
from harness.command.handlers import register_all_handlers
from harness.command.registry import CommandRegistry


def create_bus() -> CommandBus:
    """Create a fully configured CommandBus.

    Returns:
        A CommandBus instance with all current handlers registered.
    """
    registry = CommandRegistry()
    register_all_handlers(registry)
    bus = CommandBus(registry=registry)
    return bus


__all__ = [
    "create_bus",
]
