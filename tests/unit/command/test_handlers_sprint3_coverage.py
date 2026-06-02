"""Coverage tests for typed CommandBus handlers.

Verifies the typed handler infrastructure works correctly.
"""
from __future__ import annotations

from harness.command.setup import create_bus
from harness.command.types import Command, CommandResult

smoke = __import__("pytest").mark.smoke


def test_create_bus_returns_working_bus():
    """create_bus() creates a working CommandBus."""
    bus = create_bus()
    assert bus is not None


def test_dispatch_typed_command():
    """Typed commands dispatch through the bus."""
    bus = create_bus()
    from harness.command.commands.misc import NextCommand
    cmd = NextCommand(slug="test-coverage")
    result = bus.dispatch(cmd)
    assert isinstance(result, CommandResult)
