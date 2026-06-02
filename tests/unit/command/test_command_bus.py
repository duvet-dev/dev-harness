"""Tests for CommandBus typed dispatch, register, and error handling.

Covers:
- CommandBus.register_type() and register_types() for typed commands
- CommandBus.dispatch() and dispatch_async() for typed commands
- UnknownCommandError for unregistered commands
- TypedCommand construction and dispatch
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from harness.command.bus import CommandBus
from harness.command.types import (
    CommandResult,
    TypedCommand,
    TypedHandler,
    TypedResult,
)
from harness.errors import UnknownCommandError


# ── Test typed command and handler types ──────────────────────────────


@dataclass(frozen=True)
class _EchoCommand(TypedCommand):
    """Test typed command that echoes."""
    slug: str
    message: str = ""


@dataclass(frozen=True)
class _EchoResult(TypedResult):
    """Test typed result."""
    success: bool = True
    message: str = ""


class _EchoHandler(TypedHandler):
    """Test handler that echoes back command data."""

    def handle(self, command: _EchoCommand) -> _EchoResult:
        return _EchoResult(
            success=True,
            message=f"Echo: {command.message or command.slug}",
        )


@dataclass(frozen=True)
class _AsyncCommand(TypedCommand):
    """Test typed command with async handler."""
    slug: str


@dataclass(frozen=True)
class _AsyncResult(TypedResult):
    """Test async result."""
    success: bool = True
    message: str = ""


class _AsyncHandler(TypedHandler):
    """Test handler with async handle method."""

    async def handle(self, command: _AsyncCommand) -> _AsyncResult:
        return _AsyncResult(
            success=True,
            message=f"Async: {command.slug}",
        )


@dataclass(frozen=True)
class _FailingCommand(TypedCommand):
    """Test typed command with failing handler."""
    slug: str


@dataclass(frozen=True)
class _FailingResult(TypedResult):
    """Test failing result."""
    success: bool = False
    error: str = ""


class _FailingHandler(TypedHandler):
    """Test handler that always fails."""

    def handle(self, command: _FailingCommand) -> _FailingResult:
        return _FailingResult(
            success=False,
            error="Intentional failure",
        )


@dataclass(frozen=True)
class _UnregisteredCommand(TypedCommand):
    """Test typed command with no handler registered."""
    slug: str


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def bus() -> CommandBus:
    return CommandBus()


@pytest.fixture
def populated_bus(bus: CommandBus) -> CommandBus:
    bus.register_type(_EchoHandler(), _EchoCommand)
    bus.register_type(_FailingHandler(), _FailingCommand)
    return bus


# ── CommandBus Tests ───────────────────────────────────────────────


class TestCommandBus:
    """Tests for CommandBus typed dispatch and registration."""

    def test_dispatch_known_typed_command(self, populated_bus: CommandBus):
        """Dispatching a registered typed command returns the handler's result."""
        cmd = _EchoCommand(slug="test-eng", message="hello")
        result = populated_bus.dispatch(cmd)
        assert result.success is True
        assert "Echo: hello" in result.message

    def test_dispatch_failing_handler(self, populated_bus: CommandBus):
        """Dispatching to a failing handler returns failure result."""
        cmd = _FailingCommand(slug="test-eng")
        result = populated_bus.dispatch(cmd)
        assert result.success is False
        assert result.error == "Intentional failure"

    def test_dispatch_unknown_typed_command_raises(self, populated_bus: CommandBus):
        """Dispatching an unregistered typed command raises UnknownCommandError."""
        cmd = _UnregisteredCommand(slug="test-eng")
        with pytest.raises(UnknownCommandError, match="_UnregisteredCommand"):
            populated_bus.dispatch(cmd)

    def test_dispatch_empty_registry(self, bus: CommandBus):
        """Dispatching with empty bus raises UnknownCommandError."""
        cmd = _EchoCommand(slug="test-eng")
        with pytest.raises(UnknownCommandError):
            bus.dispatch(cmd)

    def test_register_type_sync(self, bus: CommandBus):
        """Registering a typed handler enables dispatch."""
        bus.register_type(_EchoHandler(), _EchoCommand)
        cmd = _EchoCommand(slug="test-eng", message="sync")
        result = bus.dispatch(cmd)
        assert result.success is True

    def test_dispatch_async_sync_handler(self, populated_bus: CommandBus):
        """dispatch_async works with sync handlers."""
        import asyncio
        cmd = _EchoCommand(slug="test-eng")
        result = asyncio.run(populated_bus.dispatch_async(cmd))
        assert result.success is True

    def test_dispatch_async_async_handler(self, bus: CommandBus):
        """dispatch_async awaits async handlers."""
        import asyncio
        bus.register_type(_AsyncHandler(), _AsyncCommand)
        cmd = _AsyncCommand(slug="test-eng")
        result = asyncio.run(bus.dispatch_async(cmd))
        assert result.success is True
        assert "Async:" in result.message

    def test_register_types_bulk(self, bus: CommandBus):
        """register_types registers multiple handlers at once."""
        bus.register_types({
            _EchoCommand: _EchoHandler(),
            _FailingCommand: _FailingHandler(),
        })
        r1 = bus.dispatch(_EchoCommand(slug="t1"))
        assert r1.success is True
        r2 = bus.dispatch(_FailingCommand(slug="t2"))
        assert r2.success is False

    def test_typed_result_wrapped(self, populated_bus: CommandBus):
        """Typed results are wrapped in CommandResult for uniform API."""
        cmd = _EchoCommand(slug="test")
        result = populated_bus.dispatch(cmd)
        assert isinstance(result, CommandResult)
        # The typed result is stored in data
        assert "typed_result" in result.data
        assert isinstance(result.data["typed_result"], _EchoResult)

    def test_dispatch_async_unknown_command(self, bus: CommandBus):
        """dispatch_async raises UnknownCommandError for unregistered commands."""
        import asyncio
        cmd = _UnregisteredCommand(slug="test")
        with pytest.raises(UnknownCommandError):
            asyncio.run(bus.dispatch_async(cmd))

    def test_dispatch_async_wraps_typed_result(self, bus: CommandBus):
        """dispatch_async wraps typed results in CommandResult."""
        import asyncio
        bus.register_type(_EchoHandler(), _EchoCommand)
        cmd = _EchoCommand(slug="test")
        result = asyncio.run(bus.dispatch_async(cmd))
        assert isinstance(result, CommandResult)
        assert "typed_result" in result.data

    def test_multiple_dispatch_consistent(self, populated_bus: CommandBus):
        """Dispatching the same typed command multiple times is consistent."""
        cmd = _EchoCommand(slug="test-eng")
        r1 = populated_bus.dispatch(cmd)
        r2 = populated_bus.dispatch(cmd)
        assert r1.message == r2.message
        assert r1.success == r2.success

    def test_slug_in_typed_command(self, populated_bus: CommandBus):
        """Typed commands carry their slug through dispatch."""
        cmd = _EchoCommand(slug="my-eng")
        result = populated_bus.dispatch(cmd)
        assert result.success is True

    def test_frozen_dataclass_command(self):
        """Typed commands are frozen dataclasses and immutable."""
        cmd = _EchoCommand(slug="test")
        with pytest.raises((AttributeError, TypeError)):
            cmd.slug = "changed"  # type: ignore[misc]


# ── Command Types Tests ────────────────────────────────────────────


class TestCommandTypes:
    """Tests for CommandResult, TypedCommand, TypedHandler base types."""

    def test_command_result_defaults(self):
        """CommandResult with no args defaults to success."""
        result = CommandResult()
        assert result.success is True
        assert result.error == ""
        assert result.message == ""
        assert result.data == {}

    def test_command_result_failure(self):
        """CommandResult can represent failure."""
        result = CommandResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"

    def test_command_result_with_data(self):
        """CommandResult can carry payload data."""
        result = CommandResult(success=True, message="Done", data={"id": 42})
        assert result.message == "Done"
        assert result.data == {"id": 42}

    def test_typed_command_frozen(self):
        """Typed commands are frozen dataclasses."""
        @dataclass(frozen=True)
        class MyCmd(TypedCommand):
            slug: str
        cmd = MyCmd(slug="test")
        assert cmd.slug == "test"
        with pytest.raises((AttributeError, TypeError)):
            cmd.slug = "new"  # type: ignore[misc]
