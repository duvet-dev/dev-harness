"""Tests for CommandBus dispatch via shared bus.

Covers:
- Typed commands dispatch through the shared bus
- Edge cases: empty slug, unknown commands
- Integration: command construction + bus dispatch round-trip
"""

from __future__ import annotations

import pytest

from harness.command.setup import create_bus, get_shared_bus, reset_shared_bus
from harness.command.commands.engagement import (
    AbortEngagementCommand,
    CreateEngagementCommand,
)
from harness.command.commands.phase import EnterPhaseCommand
from harness.command.commands.misc import NextCommand, QueryStatusCommand, QueryWhatsNextCommand
from harness.command.commands.review import FinishEngagementCommand, ReviewEngagementCommand
from harness.command.commands.session import ChatCommand, SessionCommand
from harness.command.commands.wave import RunWaveCommand
from harness.command.commands.mgmt import AgentListCommand, TeamListCommand, ConsultCommand
from harness.command.types import CommandResult
from harness.errors import UnknownCommandError


class TestTypedCommandDispatch:
    """Tests for dispatching typed commands through the shared bus."""

    def setup_method(self):
        reset_shared_bus()

    def test_typed_create_engagement(self):
        """Typed CreateEngagementCommand dispatches successfully."""
        import time
        slug = f"test-create-typed-{int(time.time() * 1000000) % 1000000}"
        bus = get_shared_bus()
        cmd = CreateEngagementCommand(slug=slug)
        result = bus.dispatch(cmd)
        assert isinstance(result, CommandResult)
        assert result.success is True

    def test_typed_enter_phase(self):
        """Typed EnterPhaseCommand dispatches successfully."""
        reset_shared_bus()
        bus = get_shared_bus()
        cmd = EnterPhaseCommand(slug="test-phase-typed", phase="design")
        result = bus.dispatch(cmd)
        assert result.success is True
        assert "Phase 'design' entry dispatched" in result.message

    @pytest.mark.skip(reason="NextCommand dead handler - removed in Wave 4")
    def test_typed_next(self):
        """Typed NextCommand dispatches."""
        bus = get_shared_bus()
        cmd = NextCommand(slug="test-next")
        result = bus.dispatch(cmd)
        assert result.success is True

    def test_typed_query_status(self):
        """Typed QueryStatusCommand dispatches."""
        bus = get_shared_bus()
        cmd = QueryStatusCommand(slug="test-status")
        result = bus.dispatch(cmd)
        assert isinstance(result, CommandResult)

    def test_typed_abort_engagement(self):
        """Typed AbortEngagementCommand dispatches."""
        bus = get_shared_bus()
        cmd = AbortEngagementCommand(slug="test-abort-typed")
        result = bus.dispatch(cmd)
        assert isinstance(result, CommandResult)

    def test_unknown_typed_command(self):
        """Unknown typed command raises UnknownCommandError."""
        reset_shared_bus()
        bus = get_shared_bus()

        class UnknownCmd:
            pass

        cmd = UnknownCmd()
        with pytest.raises(UnknownCommandError):
            bus.dispatch(cmd)


class TestSharedBusDispatch:
    """Tests for dispatch through the shared CommandBus."""

    @pytest.mark.skip(reason="NextCommand dead handler - removed in Wave 4")
    def test_shared_bus_dispatch(self):
        """The shared bus dispatches a typed command."""
        reset_shared_bus()
        cmd = NextCommand(slug="test-dispatch-typed")
        result = get_shared_bus().dispatch(cmd)
        assert isinstance(result, CommandResult)


class TestTypedCommandConstruction:
    """Tests for direct typed command construction."""

    def test_agent_list_command(self):
        """AgentListCommand created directly."""
        cmd = AgentListCommand()
        assert isinstance(cmd, AgentListCommand)

    def test_team_list_command(self):
        """TeamListCommand created directly."""
        cmd = TeamListCommand()
        assert isinstance(cmd, TeamListCommand)

    def test_consult_command(self):
        """ConsultCommand created directly with question."""
        cmd = ConsultCommand(question="architecture review")
        assert isinstance(cmd, ConsultCommand)
        assert cmd.question == "architecture review"
