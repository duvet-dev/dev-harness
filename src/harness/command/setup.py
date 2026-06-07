"""Command subsystem setup — bus factory and handler registration.

Provides ``create_bus()``, ``get_shared_bus()``, and ``reset_shared_bus()``
functions that create a fully configured CommandBus with all typed handlers
registered. This is the entry point for CLI, REPL, and session integration.

All handler registrations are derived from ``@register`` decorators in the
CLI module (``harness.cli.main``). See ``_registration.py`` for details.
"""

from __future__ import annotations

from harness.command.bus import CommandBus

# Module-level singleton shared bus.
_SHARED_BUS: CommandBus | None = None


def _build_bus() -> CommandBus:
    """Build a fully configured CommandBus from @register decorators.

    Returns:
        A CommandBus instance with all typed handlers registered via
        ``register_bus_handlers()``.
    """
    from harness.cli import main as _unused  # populate REGISTRY via @register

    from harness.command._registration import register_bus_handlers

    bus = CommandBus()
    register_bus_handlers(bus)
    return bus


def create_bus() -> CommandBus:
    """Create a fresh fully configured CommandBus with all typed handlers.

    Returns:
        A CommandBus instance with all typed handlers registered.
    """
    return _build_bus()


def get_shared_bus() -> CommandBus:
    """Return (or create) the module-level shared CommandBus singleton.

    The shared bus is created once and reused for the lifetime of the
    process. All CLI commands and REPL dispatches share this single bus.

    Returns:
        The shared CommandBus instance.
    """
    global _SHARED_BUS
    if _SHARED_BUS is None:
        _SHARED_BUS = _build_bus()
    return _SHARED_BUS


def reset_shared_bus() -> None:
    """Reset the shared bus singleton. Useful in tests."""
    global _SHARED_BUS
    _SHARED_BUS = None


__all__ = [
    "create_bus",
    "get_shared_bus",
    "reset_shared_bus",
]
