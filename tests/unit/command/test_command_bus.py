"""Tests for CommandBus dispatch, register, and error handling.

Covers:
- CommandBus.register() and CommandRegistry registration
- CommandBus.dispatch() and dispatch_async()
- UnknownCommandError for unregistered commands
- CommandRegistry.register_all(), get_handler(), has_handler()
"""

from __future__ import annotations

import pytest

from harness.command.bus import CommandBus
from harness.command.registry import CommandRegistry
from harness.command.types import Command, CommandHandler, CommandResult
from harness.errors import UnknownCommandError


# ── Fixtures ─────────────────────────────────────────────────────────


class _EchoHandler(CommandHandler):
    """Test handler that echoes back command data."""

    def handle(self, command: Command) -> CommandResult:
        return CommandResult(
            success=True,
            message=f"Echo: {command.command_type}",
            data={"slug": command.slug, "type": command.command_type},
        )


class _AsyncHandler(CommandHandler):
    """Test handler with async handle method."""

    async def handle(self, command: Command) -> CommandResult:
        return CommandResult(
            success=True,
            message=f"Async: {command.command_type}",
            data={"slug": command.slug, "type": command.command_type},
        )


class _FailingHandler(CommandHandler):
    """Test handler that always fails."""

    def handle(self, command: Command) -> CommandResult:
        return CommandResult(
            success=False,
            error="Intentional failure",
            message="Handler failed as designed",
        )


@pytest.fixture
def empty_registry() -> CommandRegistry:
    return CommandRegistry()


@pytest.fixture
def populated_registry() -> CommandRegistry:
    registry = CommandRegistry()
    registry.register("echo", _EchoHandler())
    registry.register("fail", _FailingHandler())
    return registry


@pytest.fixture
def bus() -> CommandBus:
    return CommandBus()


@pytest.fixture
def populated_bus(populated_registry: CommandRegistry) -> CommandBus:
    return CommandBus(registry=populated_registry)


# ── CommandRegistry Tests ──────────────────────────────────────────


class TestCommandRegistry:
    """Tests for CommandRegistry — registration and lookup."""

    def test_register_handler(self, empty_registry: CommandRegistry):
        """Registering a handler allows get_handler to find it."""
        handler = _EchoHandler()
        empty_registry.register("echo", handler)
        assert empty_registry.get_handler("echo") is handler

    def test_register_duplicate_raises(self, empty_registry: CommandRegistry):
        """Registering a duplicate command type raises ValueError."""
        empty_registry.register("echo", _EchoHandler())
        with pytest.raises(ValueError, match="already registered"):
            empty_registry.register("echo", _EchoHandler())

    def test_register_empty_type_raises(self, empty_registry: CommandRegistry):
        """Registering with empty string raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            empty_registry.register("", _EchoHandler())

    def test_register_invalid_type_raises(self, empty_registry: CommandRegistry):
        """Registering with non-string type raises ValueError."""
        with pytest.raises(ValueError):
            empty_registry.register(123, _EchoHandler())  # type: ignore[arg-type]

    def test_get_handler_returns_none_for_unknown(
        self, empty_registry: CommandRegistry
    ):
        """get_handler returns None for unregistered command types."""
        assert empty_registry.get_handler("nonexistent") is None

    def test_register_all_bulk(self, empty_registry: CommandRegistry):
        """register_all registers multiple handlers at once."""
        handlers = {
            "echo": _EchoHandler(),
            "fail": _FailingHandler(),
        }
        empty_registry.register_all(handlers)
        assert empty_registry.has_handler("echo") is True
        assert empty_registry.has_handler("fail") is True

    def test_register_all_conflict_raises(self, empty_registry: CommandRegistry):
        """register_all raises ValueError if any type conflicts."""
        empty_registry.register("echo", _EchoHandler())
        with pytest.raises(ValueError):
            empty_registry.register_all({"echo": _EchoHandler()})

    def test_has_handler(self, populated_registry: CommandRegistry):
        """has_handler correctly reports registration status."""
        assert populated_registry.has_handler("echo") is True
        assert populated_registry.has_handler("unknown") is False

    def test_list_registered(self, populated_registry: CommandRegistry):
        """list_registered returns sorted list of registered types."""
        types = populated_registry.list_registered()
        assert types == ["echo", "fail"]

    def test_list_registered_empty(self, empty_registry: CommandRegistry):
        """list_registered returns empty list when nothing registered."""
        assert empty_registry.list_registered() == []

    def test_clear(self, populated_registry: CommandRegistry):
        """clear removes all registered handlers."""
        populated_registry.clear()
        assert populated_registry.list_registered() == []


# ── CommandBus Tests ───────────────────────────────────────────────


class TestCommandBus:
    """Tests for CommandBus dispatch and registration."""

    def test_dispatch_known_command(self, populated_bus: CommandBus):
        """Dispatching a registered command returns the handler's result."""
        cmd = Command(slug="test-eng", command_type="echo")
        result = populated_bus.dispatch(cmd)
        assert result.success is True
        assert "Echo: echo" in result.message

    def test_dispatch_failing_handler(self, populated_bus: CommandBus):
        """Dispatching to a failing handler returns failure result."""
        cmd = Command(slug="test-eng", command_type="fail")
        result = populated_bus.dispatch(cmd)
        assert result.success is False
        assert result.error == "Intentional failure"

    def test_dispatch_unknown_command_raises(self, populated_bus: CommandBus):
        """Dispatching an unregistered command raises UnknownCommandError."""
        cmd = Command(slug="test-eng", command_type="nonexistent")
        with pytest.raises(UnknownCommandError, match="nonexistent"):
            populated_bus.dispatch(cmd)

    def test_dispatch_empty_registry(self, bus: CommandBus):
        """Dispatching with empty registry raises UnknownCommandError."""
        cmd = Command(slug="test-eng", command_type="anything")
        with pytest.raises(UnknownCommandError):
            bus.dispatch(cmd)

    def test_register_handler(self, bus: CommandBus):
        """Registering on the bus delegates to the registry."""
        bus.register("echo", _EchoHandler())
        cmd = Command(slug="test-eng", command_type="echo")
        result = bus.dispatch(cmd)
        assert result.success is True

    def test_dispatch_async_sync_handler(self, populated_bus: CommandBus):
        """dispatch_async works with sync handlers."""
        import asyncio
        cmd = Command(slug="test-eng", command_type="echo")
        result = asyncio.run(populated_bus.dispatch_async(cmd))
        assert result.success is True

    def test_dispatch_async_async_handler(self, bus: CommandBus):
        """dispatch_async awaits async handlers."""
        import asyncio
        bus.register("async", _AsyncHandler())
        cmd = Command(slug="test-eng", command_type="async")
        result = asyncio.run(bus.dispatch_async(cmd))
        assert result.success is True
        assert "Async:" in result.message

    def test_register_from_imports_handlers(self, bus: CommandBus):
        """register_from imports all handlers from another registry."""
        registry = CommandRegistry()
        registry.register("echo", _EchoHandler())
        bus.register_from(registry)
        cmd = Command(slug="test-eng", command_type="echo")
        result = bus.dispatch(cmd)
        assert result.success is True

    def test_register_from_conflict_raises(self, bus: CommandBus):
        """register_from raises if it creates a type conflict."""
        bus.register("echo", _EchoHandler())
        registry = CommandRegistry()
        registry.register("echo", _EchoHandler())
        with pytest.raises(ValueError):
            bus.register_from(registry)

    def test_registry_property(self, populated_bus: CommandBus):
        """The registry property exposes the underlying registry."""
        assert isinstance(populated_bus.registry, CommandRegistry)

    def test_command_with_data(self, populated_bus: CommandBus):
        """Commands can carry additional data."""
        cmd = Command(
            slug="test-eng",
            command_type="echo",
            data={"extra": "value"},
        )
        result = populated_bus.dispatch(cmd)
        assert result.success is True

    def test_multiple_dispatch_consistent(self, populated_bus: CommandBus):
        """Dispatching the same command multiple times is consistent."""
        cmd = Command(slug="test-eng", command_type="echo")
        r1 = populated_bus.dispatch(cmd)
        r2 = populated_bus.dispatch(cmd)
        assert r1.message == r2.message
        assert r1.success == r2.success


# ── Command Types Tests ────────────────────────────────────────────


class TestCommandTypes:
    """Tests for Command, CommandResult, and CommandHandler base types."""

    def test_command_defaults(self):
        """Command with minimal args has sensible defaults."""
        cmd = Command(slug="test")
        assert cmd.command_type == ""
        assert cmd.data == {}
        assert cmd.slug == "test"

    def test_command_full(self):
        """Command with all args sets fields correctly."""
        cmd = Command(slug="test", command_type="test_cmd", data={"key": "val"})
        assert cmd.slug == "test"
        assert cmd.command_type == "test_cmd"
        assert cmd.data == {"key": "val"}

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

    def test_command_handler_abc_cannot_instantiate(self):
        """CommandHandler ABC cannot be instantiated directly."""
        with pytest.raises(TypeError):
            CommandHandler()  # type: ignore[abstract]
