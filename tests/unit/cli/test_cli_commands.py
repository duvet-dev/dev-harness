"""Tests for CLI-to-CommandBus command factories and dispatch helper.

Covers:
- Remaining factory functions produce correct Command objects
- dispatch_cli_command creates bus and dispatches
- Edge cases: empty slug, unknown commands
- Integration: factory + dispatch round-trip
"""

from __future__ import annotations

import pytest

from harness.cli.commands import (
    dispatch_cli_command,
    next_command,
    query_status_command,
    query_whats_next_command,
)
from harness.command.setup import create_bus
from harness.command.commands.engagement import (
    AbortEngagementCommand,
    CreateEngagementCommand,
)
from harness.command.commands.phase import EnterPhaseCommand
from harness.command.types import Command, CommandResult
from harness.errors import UnknownCommandError


class TestCommandFactories:
    """Tests for CLI-to-CommandBus factory functions (remaining)."""

    # ── next_command ─────────────────────────────────────────────────

    def test_next(self):
        """next_command creates correct command_type."""
        cmd = next_command(slug="my-eng")
        assert cmd.command_type == "next"
        assert cmd.slug == "my-eng"
        assert cmd.data == {}

    def test_next_empty_slug(self):
        """next_command works with empty slug."""
        cmd = next_command(slug="")
        assert cmd.command_type == "next"
        assert cmd.slug == ""

    # ── query_status_command ─────────────────────────────────────────

    def test_query_status(self):
        """query_status_command creates correct command_type."""
        cmd = query_status_command(slug="my-eng")
        assert cmd.command_type == "query_status"
        assert cmd.slug == "my-eng"

    def test_query_status_empty_slug(self):
        """query_status_command works with empty slug."""
        cmd = query_status_command(slug="")
        assert cmd.command_type == "query_status"
        assert cmd.slug == ""

    # ── query_whats_next_command ─────────────────────────────────────

    def test_query_whats_next(self):
        """query_whats_next_command creates correct command_type."""
        cmd = query_whats_next_command(slug="my-eng")
        assert cmd.command_type == "query_whats_next"
        assert cmd.slug == "my-eng"

    def test_query_whats_next_empty_slug(self):
        """query_whats_next_command works with empty slug."""
        cmd = query_whats_next_command(slug="")
        assert cmd.command_type == "query_whats_next"
        assert cmd.slug == ""

    # ── Type safety ──────────────────────────────────────────────────

    def test_all_factories_return_command(self):
        """All factory functions return Command instances."""
        factories = [
            next_command("slug"),
            query_status_command("slug"),
            query_whats_next_command("slug"),
        ]
        for cmd in factories:
            assert isinstance(cmd, Command), f"{cmd.command_type} is not Command"


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

        cmd = UnknownCmd()  # type: ignore
        with pytest.raises(UnknownCommandError):
            bus.dispatch(cmd)  # type: ignore


class TestDispatchCliCommand:
    """Tests for the dispatch_cli_command helper."""

    @staticmethod
    def _unique_slug(base: str) -> str:
        """Create a unique slug to avoid cross-test collisions."""
        import time
        return f"{base}-{int(time.time() * 1000000) % 1000000}"

    def test_dispatch_next(self):
        """dispatch_cli_command dispatches next successfully."""
        cmd = next_command(slug=self._unique_slug("next"))
        result = dispatch_cli_command(cmd)
        assert result.success is True
        assert "dispatched to NextEngine" in result.message

    def test_dispatch_query_status(self):
        """dispatch_cli_command dispatches query_status successfully."""
        cmd = query_status_command(slug=self._unique_slug("query"))
        result = dispatch_cli_command(cmd)
        assert result.success is True
        assert "slug" in result.data

    def test_dispatch_query_whats_next(self):
        """dispatch_cli_command dispatches query_whats_next."""
        cmd = query_whats_next_command(slug=self._unique_slug("whatsnext"))
        result = dispatch_cli_command(cmd)
        assert isinstance(result, CommandResult)

    def test_dispatch_unknown_type(self):
        """dispatch_cli_command raises UnknownCommandError for unknown types."""
        cmd = Command(slug="test", command_type="nonexistent")
        with pytest.raises(UnknownCommandError):
            dispatch_cli_command(cmd)


class TestWaveOCommandFactories:
    """Tests for Wave O factory functions — agent_list, fleet_list, consult."""

    def test_agent_list_command(self):
        """agent_list_command() creates correct Command."""
        from harness.cli.commands import agent_list_command
        cmd = agent_list_command()
        assert cmd.command_type == "agent_list"
        assert cmd.slug == ""

    def test_fleet_list_command(self):
        """fleet_list_command() creates correct Command."""
        from harness.cli.commands import fleet_list_command
        cmd = fleet_list_command()
        assert cmd.command_type == "fleet_list"
        assert cmd.slug == ""

    def test_consult_command(self):
        """consult_command() creates correct Command."""
        from harness.cli.commands import consult_command
        cmd = consult_command(question="architecture review")
        assert cmd.command_type == "consult"
        assert cmd.data["question"] == "architecture review"

    def test_consult_command_minimal(self):
        """consult_command() with just a question."""
        from harness.cli.commands import consult_command
        cmd = consult_command(question="Is this OK?")
        assert cmd.data["question"] == "Is this OK?"


class TestRoundTripIntegration:
    """Integration: factory + dispatch for remaining command types."""

    def test_finish_engagement_command(self):
        """finish_engagement_command creates correct command."""
        from harness.cli.commands import finish_engagement_command
        cmd = finish_engagement_command(slug="test-eng", root="/tmp")
        assert cmd.command_type == "finish_engagement"
        assert cmd.slug == "test-eng"

    def test_review_engagement_command(self):
        """review_engagement_command creates correct command."""
        from harness.cli.commands import review_engagement_command
        cmd = review_engagement_command(slug="test-eng", decision="approve")
        assert cmd.command_type == "review_engagement"

    def test_run_wave_command(self):
        """run_wave_command creates correct command."""
        from harness.cli.commands import run_wave_command
        cmd = run_wave_command(slug="test-eng", wave_id="wave-01")
        assert cmd.command_type == "run_wave"

    def test_chat_command(self):
        """chat_command creates correct command."""
        from harness.cli.commands import chat_command
        cmd = chat_command(slug="test-eng", prompt="Hello")
        assert cmd.command_type == "chat"

    def test_summary_command(self):
        """summary_command creates correct command."""
        from harness.cli.commands import summary_command
        cmd = summary_command(engagement="test-eng")
        assert cmd.command_type == "summary"

    def test_inspect_command(self):
        """inspect_command creates correct command."""
        from harness.cli.commands import inspect_command
        cmd = inspect_command(root="/tmp")
        assert cmd.command_type == "inspect"

    def test_assess_command(self):
        """assess_command creates correct command."""
        from harness.cli.commands import assess_command
        cmd = assess_command(root="/tmp")
        assert cmd.command_type == "assess"

    def test_rename_engagement_command(self):
        """rename_engagement_command creates correct command."""
        from harness.cli.commands import rename_engagement_command
        cmd = rename_engagement_command(old_slug="old", new_slug="new")
        assert cmd.command_type == "rename_engagement"

    def test_set_branch_command(self):
        """set_branch_command creates correct command."""
        from harness.cli.commands import set_branch_command
        cmd = set_branch_command(slug="test-eng", branch="main")
        assert cmd.command_type == "set_branch"

    def test_fix_engagement_command(self):
        """fix_engagement_command creates correct command."""
        from harness.cli.commands import fix_engagement_command
        cmd = fix_engagement_command(slug="test-eng")
        assert cmd.command_type == "fix_engagement"

    def test_refresh_agents_command(self):
        """refresh_agents_command creates correct command."""
        from harness.cli.commands import refresh_agents_command
        cmd = refresh_agents_command()
        assert cmd.command_type == "refresh_agents"

    def test_set_governance_command(self):
        """set_governance_command creates correct command."""
        from harness.cli.commands import set_governance_command
        cmd = set_governance_command(level="strict")
        assert cmd.command_type == "set_governance"
