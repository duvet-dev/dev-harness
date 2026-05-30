"""Additional tests for command types module.

Covers remaining uncovered lines in types.py.
"""

from __future__ import annotations

from harness.command.types import (
    CommandResult,
    TypedCommand,
    TypedHandler,
    TypedResult,
)


class TestCommandResultEdgeCases:
    """Edge cases for CommandResult."""

    def test_custom_data(self):
        """CommandResult can hold arbitrary data."""
        r = CommandResult(data={"key": "val", "nested": {"a": 1}})
        assert r.data["key"] == "val"
        assert r.data["nested"]["a"] == 1

    def test_empty_fields(self):
        """Default empty fields are empty strings."""
        r = CommandResult()
        assert r.message == ""
        assert r.error == ""
        assert r.data == {}

    def test_bool_success(self):
        """Success can be True or False."""
        assert CommandResult(success=True).success is True
        assert CommandResult(success=False).success is False

    def test_str_message(self):
        """Message can be any string."""
        r = CommandResult(message="test message")
        assert str(r.message) == "test message"


class TestTypedHandlerProtocol:
    """Tests that TypedHandler can be subclassed."""

    def test_handler_inheritance(self):
        """TypedHandler subclasses work as expected."""
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class Cmd(TypedCommand):
            slug: str

        @dataclass(frozen=True)
        class Res(TypedResult):
            success: bool = True
            message: str = ""

        class MyHandler(TypedHandler[Cmd, Res]):
            def handle(self, command: Cmd) -> Res:
                return Res(success=True, message=command.slug)

        handler = MyHandler()
        cmd = Cmd(slug="test")
        result = handler.handle(cmd)
        assert result.success is True
        assert result.message == "test"


class TestBusImport:
    """Tests that bus module is importable with correct exports."""

    def test_bus_exports(self):
        import harness.command.bus as bus
        assert hasattr(bus, "CommandBus")

    def test_types_exports(self):
        import harness.command.types as types
        assert hasattr(types, "CommandResult")
        assert hasattr(types, "TypedCommand")
        assert hasattr(types, "TypedHandler")
        assert hasattr(types, "TypedResult")
