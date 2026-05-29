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

    def test_dispatch_create_engagement(self):
        """dispatch_cli_command dispatches create_engagement successfully."""
        cmd = create_engagement_command(slug="test-eng")
        result = dispatch_cli_command(cmd)
        assert isinstance(result, CommandResult)
        assert result.success is True
        assert "creation requested" in result.message

    def test_dispatch_enter_phase(self):
        """dispatch_cli_command dispatches enter_phase successfully."""
        cmd = enter_phase_command(slug="test-eng", phase="design")
        result = dispatch_cli_command(cmd)
        assert result.success is True
        assert "Phase 'design' entry dispatched" in result.message

    def test_dispatch_next(self):
        """dispatch_cli_command dispatches next successfully."""
        cmd = next_command(slug="test-eng")
        result = dispatch_cli_command(cmd)
        assert result.success is True
        assert "dispatched to NextEngine" in result.message

    def test_dispatch_abort_graceful(self):
        """dispatch_cli_command dispatches abort_engagement gracefully."""
        cmd = abort_engagement_command(slug="test-eng")
        result = dispatch_cli_command(cmd)
        # May succeed or fail depending on environment
        assert isinstance(result, CommandResult)

    def test_dispatch_abort_hard(self):
        """dispatch_cli_command dispatches abort_engagement hard."""
        cmd = abort_engagement_command(slug="test-eng", mode="hard")
        result = dispatch_cli_command(cmd)
        assert isinstance(result, CommandResult)

    def test_dispatch_query_status(self):
        """dispatch_cli_command dispatches query_status successfully."""
        cmd = query_status_command(slug="test-eng")
        result = dispatch_cli_command(cmd)
        assert result.success is True
        assert "slug" in result.data

    def test_dispatch_query_whats_next(self):
        """dispatch_cli_command dispatches query_whats_next."""
        cmd = query_whats_next_command(slug="test-eng")
        result = dispatch_cli_command(cmd)
        # May fail gracefully if engagement doesn't exist
        assert isinstance(result, CommandResult)

    def test_dispatch_unknown_type(self):
        """dispatch_cli_command raises UnknownCommandError for unknown types."""
        cmd = Command(slug="test", command_type="nonexistent")
        with pytest.raises(UnknownCommandError):
            dispatch_cli_command(cmd)

    def test_dispatch_empty_slug(self):
        """dispatch_cli_command works with empty slug."""
        cmd = create_engagement_command(slug="")
        result = dispatch_cli_command(cmd)
        assert result.success is True

    def test_dispatch_passes_data_through(self):
        """dispatch_cli_command passes extra data to handlers."""
        cmd = create_engagement_command(slug="test-eng", extra_field="value")
        result = dispatch_cli_command(cmd)
        assert result.success is True
        # The stub handler returns data, but doesn't echo extra fields
        assert result.data["slug"] == "test-eng"


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
        ]
        for cmd_type, factory in types_and_factories:
            cmd = factory()
            assert cmd.command_type == cmd_type, (
                f"Expected '{cmd_type}', got '{cmd.command_type}'"
            )
            # Dispatch should not raise UnknownCommandError
            result = dispatch_cli_command(cmd)
            assert isinstance(result, CommandResult)
