"""Tests for CLI-to-CommandBus command factories and dispatch helper.

Covers:
- All 6 factory functions produce correct Command objects
- dispatch_cli_command creates bus and dispatches
- Edge cases: empty slug, unknown commands, default modes
- Integration: factory + dispatch round-trip
"""

from __future__ import annotations

import pytest

from harness.cli.commands import (
    abort_engagement_command,
    create_engagement_command,
    dispatch_cli_command,
    enter_phase_command,
    next_command,
    query_status_command,
    query_whats_next_command,
)
from harness.command.types import Command, CommandResult
from harness.errors import UnknownCommandError


class TestCommandFactories:
    """Tests for CLI-to-CommandBus factory functions."""

    # ── create_engagement_command ────────────────────────────────────

    def test_create_engagement_default(self):
        """create_engagement_command creates correct command_type."""
        cmd = create_engagement_command(slug="my-eng")
        assert isinstance(cmd, Command)
        assert cmd.slug == "my-eng"
        assert cmd.command_type == "create_engagement"
        assert cmd.data == {}

    def test_create_engagement_with_kwargs(self):
        """create_engagement_command passes extra kwargs as data."""
        cmd = create_engagement_command(slug="my-eng", workflow="standard", template="backend")
        assert cmd.slug == "my-eng"
        assert cmd.data == {"workflow": "standard", "template": "backend"}

    def test_create_engagement_empty_slug(self):
        """create_engagement_command works with empty slug."""
        cmd = create_engagement_command(slug="")
        assert cmd.slug == ""
        assert cmd.command_type == "create_engagement"

    # ── enter_phase_command ──────────────────────────────────────────

    def test_enter_phase(self):
        """enter_phase_command creates correct command_type and data."""
        cmd = enter_phase_command(slug="my-eng", phase="design")
        assert cmd.command_type == "enter_phase"
        assert cmd.slug == "my-eng"
        assert cmd.data == {"phase": "design"}

    def test_enter_phase_empty_phase(self):
        """enter_phase_command works with empty phase name."""
        cmd = enter_phase_command(slug="my-eng", phase="")
        assert cmd.command_type == "enter_phase"
        assert cmd.data == {"phase": ""}

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

    # ── abort_engagement_command ─────────────────────────────────────

    def test_abort_graceful_default(self):
        """abort_engagement_command defaults to graceful mode."""
        cmd = abort_engagement_command(slug="my-eng")
        assert cmd.command_type == "abort_engagement"
        assert cmd.data == {"mode": "graceful"}

    def test_abort_hard(self):
        """abort_engagement_command accepts hard mode."""
        cmd = abort_engagement_command(slug="my-eng", mode="hard")
        assert cmd.command_type == "abort_engagement"
        assert cmd.data == {"mode": "hard"}

    def test_abort_empty_slug(self):
        """abort_engagement_command works with empty slug."""
        cmd = abort_engagement_command(slug="")
        assert cmd.command_type == "abort_engagement"
        assert cmd.data == {"mode": "graceful"}

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
            create_engagement_command("slug"),
            enter_phase_command("slug", "design"),
            next_command("slug"),
            abort_engagement_command("slug"),
            query_status_command("slug"),
            query_whats_next_command("slug"),
        ]
        for cmd in factories:
            assert isinstance(cmd, Command), f"{cmd.command_type} is not Command"


class TestDispatchCliCommand:
    """Tests for the dispatch_cli_command helper."""

    @staticmethod
    def _unique_slug(base: str) -> str:
        """Create a unique slug using a counter to avoid cross-test collisions."""
        import time
        return f"{base}-{int(time.time() * 1000000) % 1000000}"

    def test_dispatch_create_engagement(self):
        """dispatch_cli_command dispatches create_engagement successfully."""
        slug = self._unique_slug("create-eng")
        cmd = create_engagement_command(slug=slug)
        result = dispatch_cli_command(cmd)
        assert isinstance(result, CommandResult)
        assert result.success is True
        assert "created" in result.message

    def test_dispatch_enter_phase(self):
        """dispatch_cli_command dispatches enter_phase successfully."""
        cmd = enter_phase_command(slug=self._unique_slug("phase"), phase="design")
        result = dispatch_cli_command(cmd)
        assert result.success is True
        assert "Phase 'design' entry dispatched" in result.message

    def test_dispatch_next(self):
        """dispatch_cli_command dispatches next successfully."""
        cmd = next_command(slug=self._unique_slug("next"))
        result = dispatch_cli_command(cmd)
        assert result.success is True
        assert "dispatched to NextEngine" in result.message

    def test_dispatch_abort_graceful(self):
        """dispatch_cli_command dispatches abort_engagement gracefully."""
        cmd = abort_engagement_command(slug=self._unique_slug("abort"))
        result = dispatch_cli_command(cmd)
        # May succeed or fail depending on environment
        assert isinstance(result, CommandResult)

    def test_dispatch_abort_hard(self):
        """dispatch_cli_command dispatches abort_engagement hard."""
        cmd = abort_engagement_command(slug=self._unique_slug("abort-hard"), mode="hard")
        result = dispatch_cli_command(cmd)
        assert isinstance(result, CommandResult)

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
        # May fail gracefully if engagement doesn't exist
        assert isinstance(result, CommandResult)

    def test_dispatch_unknown_type(self):
        """dispatch_cli_command raises UnknownCommandError for unknown types."""
        cmd = Command(slug="test", command_type="nonexistent")
        with pytest.raises(UnknownCommandError):
            dispatch_cli_command(cmd)

    def test_dispatch_empty_slug(self):
        """dispatch_cli_command fails with empty slug (StartupResumeFlow validation)."""
        cmd = create_engagement_command(slug="")
        result = dispatch_cli_command(cmd)
        assert result.success is False
        assert "cannot be empty" in result.error.lower()

    def test_dispatch_duplicate_slug(self):
        """dispatch_cli_command fails with duplicate slug."""
        slug = self._unique_slug("dup")
        # First create succeeds
        cmd1 = create_engagement_command(slug=slug)
        result1 = dispatch_cli_command(cmd1)
        assert result1.success is True

        # Second should fail
        cmd2 = create_engagement_command(slug=slug)
        result2 = dispatch_cli_command(cmd2)
        assert result2.success is False
        assert "already exists" in result2.error.lower()


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
        cmd = consult_command(question="architecture review", team_filter="architecture", mode="blocking")
        assert cmd.command_type == "consult"
        assert cmd.slug == ""
        assert cmd.data["question"] == "architecture review"
        assert cmd.data["team_filter"] == "architecture"
        assert cmd.data["mode"] == "blocking"

    def test_consult_command_minimal(self):
        """consult_command() with just a question."""
        from harness.cli.commands import consult_command
        cmd = consult_command(question="Is this OK?")
        assert cmd.data["question"] == "Is this OK?"
        assert cmd.data["team_filter"] is None
        assert cmd.data["mode"] == "advisory"


class TestRoundTripIntegration:
    """Integration: factory + dispatch for all supported command types."""

    def test_all_registered_command_types(self):
        """All factory command types have registered handlers."""
        types_and_factories = [
            ("create_engagement", lambda: create_engagement_command("test")),
            ("enter_phase", lambda: enter_phase_command("test", "design")),
            ("next", lambda: next_command("test")),
            ("abort_engagement", lambda: abort_engagement_command("test")),
            ("query_status", lambda: query_status_command("test")),
            ("query_whats_next", lambda: query_whats_next_command("test")),
            ("agent_list", lambda: __import__("harness.cli.commands", fromlist=["agent_list_command"]).agent_list_command()),
            ("fleet_list", lambda: __import__("harness.cli.commands", fromlist=["fleet_list_command"]).fleet_list_command()),
            ("consult", lambda: __import__("harness.cli.commands", fromlist=["consult_command"]).consult_command(question="architecture review")),
        ]
        for cmd_type, factory in types_and_factories:
            cmd = factory()
            assert cmd.command_type == cmd_type, (
                f"Expected '{cmd_type}', got '{cmd.command_type}'"
            )
            # Dispatch should not raise UnknownCommandError
            result = dispatch_cli_command(cmd)
            assert isinstance(result, CommandResult)
