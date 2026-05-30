"""Integration tests for create_bus() real handler dispatch.

Tests that specific typed commands work through the real create_bus()
with their real handlers. Focuses on commands that don't require
persistent project state or filesystem side effects.
"""

from __future__ import annotations

import pytest

from harness.command.setup import create_bus
from harness.command.types import CommandResult


@pytest.fixture
def bus():
    return create_bus()


class TestQueryCommands:
    """Tests for query-style commands that work without project state."""

    def test_query_status_dispatches(self, bus):
        from harness.command.commands.misc import QueryStatusCommand
        result = bus.dispatch(QueryStatusCommand(slug=""))
        assert isinstance(result, CommandResult)

    def test_query_whats_next_dispatches(self, bus):
        from harness.command.commands.misc import QueryWhatsNextCommand
        result = bus.dispatch(QueryWhatsNextCommand(slug=""))
        assert isinstance(result, CommandResult)

    def test_next_dispatches(self, bus):
        from harness.command.commands.misc import NextCommand
        result = bus.dispatch(NextCommand(slug=""))
        assert isinstance(result, CommandResult)

    def test_agent_list_dispatches(self, bus):
        from harness.command.commands.mgmt import AgentListCommand
        result = bus.dispatch(AgentListCommand(slug=""))
        assert isinstance(result, CommandResult)

    def test_fleet_list_dispatches(self, bus):
        from harness.command.commands.mgmt import FleetListCommand
        result = bus.dispatch(FleetListCommand(slug=""))
        assert isinstance(result, CommandResult)

    def test_consult_dispatches(self, bus):
        from harness.command.commands.mgmt import ConsultCommand
        result = bus.dispatch(ConsultCommand(slug="", question="test"))
        assert isinstance(result, CommandResult)

    def test_set_branch_dispatches(self, bus):
        from harness.command.commands.mgmt import SetBranchCommand
        result = bus.dispatch(SetBranchCommand(slug="test", branch="main"))
        assert isinstance(result, CommandResult)

    def test_manage_phase_list_dispatches(self, bus):
        from harness.command.commands.phase import ManagePhaseCommand
        result = bus.dispatch(ManagePhaseCommand(slug="test", action="list"))
        assert isinstance(result, CommandResult)

    def test_enter_phase_dispatches(self, bus):
        from harness.command.commands.phase import EnterPhaseCommand
        result = bus.dispatch(EnterPhaseCommand(slug="test", phase="design"))
        assert isinstance(result, CommandResult)


class TestErrorHandling:
    """Tests for error handling from real handlers."""

    def test_manage_phase_empty_action(self, bus):
        from harness.command.commands.phase import ManagePhaseCommand
        result = bus.dispatch(ManagePhaseCommand(slug="test", action=""))
        assert result.success is False

    def test_enter_phase_empty_slug(self, bus):
        from harness.command.commands.phase import EnterPhaseCommand
        result = bus.dispatch(EnterPhaseCommand(slug="", phase=""))
        assert result.success is False

    def test_set_branch_empty(self, bus):
        from harness.command.commands.mgmt import SetBranchCommand
        result = bus.dispatch(SetBranchCommand(slug="test", branch=""))
        assert result.success is False

    def test_consult_empty_question(self, bus):
        from harness.command.commands.mgmt import ConsultCommand
        result = bus.dispatch(ConsultCommand(slug="", question=""))
        assert result.success is False

    def test_review_no_decision(self, bus):
        from harness.command.commands.review import ReviewEngagementCommand
        result = bus.dispatch(ReviewEngagementCommand(slug="test", decision=""))
        assert result.success is False

    def test_finish_nonexistent(self, bus):
        from harness.command.commands.review import FinishEngagementCommand
        result = bus.dispatch(FinishEngagementCommand(slug="nonexistent"))
        assert result.success is False


class TestSessionCommands:
    """Tests for session/chat commands."""

    def test_chat_empty_prompt(self, bus):
        from harness.command.commands.session import ChatCommand
        result = bus.dispatch(ChatCommand(slug="test", prompt=""))
        assert result.success is False

    def test_session_empty_phase(self, bus):
        from harness.command.commands.session import SessionCommand
        result = bus.dispatch(SessionCommand(slug="test", phase=""))
        assert result.success is False


class TestBatchCommands:
    """Tests for batch commands."""

    def test_annotate_changelog_empty(self, bus):
        from harness.command.commands.batch import AnnotateChangelogCommand
        result = bus.dispatch(AnnotateChangelogCommand(slug="test", wave="", text=""))
        assert result.success is False

    def test_create_wave_from_finding_empty(self, bus):
        from harness.command.commands.batch import CreateWaveFromFindingCommand
        result = bus.dispatch(CreateWaveFromFindingCommand(slug="test"))
        assert result.success is False


class TestMgmtCommands:
    """Tests for mgmt commands."""

    def test_rename_empty_slugs(self, bus):
        from harness.command.commands.mgmt import RenameEngagementCommand
        result = bus.dispatch(RenameEngagementCommand(slug="", new_slug=""))
        assert result.success is False

    def test_set_governance_invalid(self, bus):
        from harness.command.commands.mgmt import SetGovernanceCommand
        result = bus.dispatch(SetGovernanceCommand(slug="test", level="bad"))
        assert result.success is False
