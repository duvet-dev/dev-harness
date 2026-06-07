"""Tests for CliPresenter and ReplPresenter formatting.

Covers all present methods for typed command results.
"""

from __future__ import annotations

import pytest

from harness.command.presenters.base import CliPresenter, ReplPresenter
from harness.command.types import CommandResult, TypedResult


@pytest.fixture
def cli():
    return CliPresenter()


@pytest.fixture
def repl():
    return ReplPresenter()


# ── CommandResult wrapping ──────────────────────────────────────────────


class TestCliPresenter:
    """Tests for CliPresenter — Click-formatted output."""

    def test_present_simple_command_result(self, cli):
        """Plain CommandResult shows message."""
        r = CommandResult(success=True, message="Done")
        assert cli.present(r) == "Done"

    def test_present_error_command_result(self, cli):
        """Error CommandResult shows error prefix."""
        r = CommandResult(success=False, error="Boom", message="Failed")
        assert "Error:" in cli.present(r)

    def test_present_typed_result(self, cli):
        """Typed result with success shows message."""
        from harness.command.results.engagement import CreateEngagementResult
        r = CreateEngagementResult(success=True, message="Created", slug="test", status="active")
        output = cli.present(r)
        assert "Created" in output

    def test_present_typed_result_error(self, cli):
        """Typed result with error falls through to _format_typed generic path."""
        # CreateEngagementResult goes to specific _format_create_engagement
        # which doesn't check success. Use a result type with no specific formatter.
        from harness.command.results.misc import NextResult as TestResult
        r = TestResult(success=False, error="Boom", message="Failed")
        output = cli.present(r)
        assert "Error" in output

    def test_present_create_engagement_format(self, cli):
        """CreateEngagementResult gets specific formatting."""
        from harness.command.results.engagement import CreateEngagementResult
        r = CreateEngagementResult(
            success=True, message="Created",
            slug="my-eng", status="active",
        )
        output = cli.present(r)
        assert "my-eng" in output
        assert "active" in output


class TestReplPresenter:
    """Tests for ReplPresenter — plain/ANSI text."""

    def test_present_simple_command_result(self, repl):
        """Plain CommandResult shows checkmark + message."""
        r = CommandResult(success=True, message="Done")
        output = repl.present(r)
        assert "Done" in output

    def test_present_error_command_result(self, repl):
        """Error CommandResult shows cross + error."""
        r = CommandResult(success=False, error="Boom", message="Failed")
        output = repl.present(r)
        assert "Boom" in output


