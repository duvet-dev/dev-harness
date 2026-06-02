"""Tests for delegation-thin command handlers.

Covers remaining typed handlers.
"""

from __future__ import annotations

from harness.command.handlers.mgmt_handlers import (
    AgentListTypedHandler,
    ConsultTypedHandler,
    FleetListTypedHandler,
)
from harness.command.setup import create_bus
from harness.command.types import CommandHandler, CommandResult


class TestAgentListTypedHandler:
    """Tests for AgentListTypedHandler."""

    def test_importable(self):
        handler = AgentListTypedHandler()
        assert isinstance(handler, AgentListTypedHandler)

    def test_returns_agent_list(self):
        handler = AgentListTypedHandler()
        from harness.command.commands.mgmt import AgentListCommand
        cmd = AgentListCommand()
        result = handler.handle(cmd)
        assert result.success
        assert result.count >= 1

    def test_registered_in_registry(self):
        bus = create_bus()
        from harness.command.commands.mgmt import AgentListCommand
        result = bus.dispatch(AgentListCommand())
        assert isinstance(result, CommandResult)


class TestFleetListTypedHandler:
    """Tests for FleetListTypedHandler."""

    def test_importable(self):
        handler = FleetListTypedHandler()
        assert isinstance(handler, FleetListTypedHandler)

    def test_returns_team_list(self):
        handler = FleetListTypedHandler()
        from harness.command.commands.mgmt import FleetListCommand
        cmd = FleetListCommand()
        result = handler.handle(cmd)
        assert result.success
        assert result.count >= 1

    def test_registered_in_registry(self):
        bus = create_bus()
        from harness.command.commands.mgmt import FleetListCommand
        result = bus.dispatch(FleetListCommand())
        assert isinstance(result, CommandResult)


class TestConsultTypedHandler:
    """Tests for ConsultTypedHandler."""

    def test_importable(self):
        handler = ConsultTypedHandler()
        assert isinstance(handler, ConsultTypedHandler)

    def test_routes_question(self):
        handler = ConsultTypedHandler()
        from harness.command.commands.mgmt import ConsultCommand
        cmd = ConsultCommand(question="test query")
        result = handler.handle(cmd)
        assert isinstance(result, CommandResult) or hasattr(result, 'success')

    def test_registered_in_registry(self):
        bus = create_bus()
        from harness.command.commands.mgmt import ConsultCommand
        result = bus.dispatch(ConsultCommand(question="test"))
        assert isinstance(result, CommandResult)
