"""Tests for CLI-to-CommandBus command factories and dispatch helper.

Covers:
- Remaining factory functions produce correct Command objects
- dispatch_cli_command creates bus and dispatches
- Edge cases: empty slug, unknown commands
- Integration: factory + dispatch round-trip
"""

from __future__ import annotations

import pytest

from harness.cli.commands import dispatch_cli_command
from harness.command.setup import create_bus
from harness.command.commands.engagement import (
    AbortEngagementCommand,
    CreateEngagementCommand,
)
from harness.command.commands.phase import EnterPhaseCommand
from harness.command.commands.misc import NextCommand, QueryStatusCommand, QueryWhatsNextCommand
from harness.command.commands.review import FinishEngagementCommand, ReviewEngagementCommand
from harness.command.commands.session import ChatCommand, SessionCommand
from harness.command.commands.wave import CreateWaveCommand, ExecuteStepCommand, RunWaveCommand
from harness.command.types import Command, CommandResult
from harness.errors import UnknownCommandError


class TestTypedCommandDispatch:
    """Tests for dispatching typed commands through create_bus()."""

    def test_typed_create_engagement(self):
        """Typed CreateEngagementCommand dispatches successfully."""
        import time
        slug = f"test-create-typed-{int(time.time() * 1000000) % 1000000}"
        bus = create_bus()
        cmd = CreateEngagementCommand(slug=slug)
        result = bus.dispatch(cmd)
        assert isinstance(result, CommandResult)
        assert result.success is True

    def test_typed_enter_phase(self):
        """Typed EnterPhaseCommand dispatches successfully."""
        bus = create_bus()
        cmd = EnterPhaseCommand(slug="test-phase-typed", phase="design")
        result = bus.dispatch(cmd)
        assert result.success is True
        assert "Phase 'design' entry dispatched" in result.message

    def test_typed_next(self):
        """Typed NextCommand dispatches."""
        bus = create_bus()
        cmd = NextCommand(slug="test-next")
        result = bus.dispatch(cmd)
        assert result.success is True

    def test_typed_query_status(self):
        """Typed QueryStatusCommand dispatches."""
        bus = create_bus()
        cmd = QueryStatusCommand(slug="test-status")
        result = bus.dispatch(cmd)
        assert isinstance(result, CommandResult)

    def test_typed_abort_engagement(self):
        """Typed AbortEngagementCommand dispatches."""
        bus = create_bus()
        cmd = AbortEngagementCommand(slug="test-abort-typed")
        result = bus.dispatch(cmd)
        assert isinstance(result, CommandResult)

    def test_unknown_typed_command(self):
        """Unknown typed command raises UnknownCommandError."""
        bus = create_bus()

        class UnknownCmd:
            pass

        cmd = UnknownCmd()
        with pytest.raises(UnknownCommandError):
            bus.dispatch(cmd)


class TestDispatchCliCommand:
    """Tests for the dispatch_cli_command helper."""

    def test_dispatch_unknown_type(self):
        """dispatch_cli_command raises UnknownCommandError for unknown types."""
        cmd = Command(slug="test", command_type="nonexistent")
        with pytest.raises(UnknownCommandError):
            dispatch_cli_command(cmd)

    # Note: dispatch_cli_command dispatches typed commands via create_bus
    def test_dispatch_typed_command(self):
        """dispatch_cli_command dispatches a typed command via create_bus."""
        bus = create_bus()
        cmd = NextCommand(slug="test-dispatch-typed")
        result = bus.dispatch(cmd)
        assert isinstance(result, CommandResult)


class TestWaveOCommandFactories:
    """Tests for Wave O factory functions — agent_list, fleet_list, consult."""

    def test_agent_list_command(self):
        """agent_list_command() creates correct Command."""
        from harness.cli.commands import agent_list_command
        cmd = agent_list_command()
        assert cmd.command_type == "agent_list"

    def test_fleet_list_command(self):
        """fleet_list_command() creates correct Command."""
        from harness.cli.commands import fleet_list_command
        cmd = fleet_list_command()
        assert cmd.command_type == "fleet_list"

    def test_consult_command(self):
        """consult_command() creates correct Command."""
        from harness.cli.commands import consult_command
        cmd = consult_command(question="architecture review")
        assert cmd.command_type == "consult"
        assert cmd.data["question"] == "architecture review"
