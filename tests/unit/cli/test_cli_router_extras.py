"""Tests for additional CommandRouter routing entries added in Wave 8.

Covers:
- `/engine` → `query_whats_next`
- `/advance` → `next`
"""

from __future__ import annotations

import pytest

from harness.command.router import CommandRouter


def _command_type_name(cmd) -> str:
    """Helper to extract a readable command type name from a typed command."""
    mapping = {
        "NextCommand": "next",
        "QueryWhatsNextCommand": "query_whats_next",
        "AbortEngagementCommand": "abort_engagement",
        "CreateEngagementCommand": "create_engagement",
        "ResumeEngagementCommand": "resume_engagement",
        "EnterPhaseCommand": "enter_phase",
        "QueryStatusCommand": "query_status",
        "CreateWaveCommand": "create_wave",
        "ExecuteStepCommand": "execute_step",
    }
    name = type(cmd).__name__
    return mapping.get(name, name)


class TestRouterExtras:
    """CommandRouter — new /-prefix commands added in Wave 8."""

    def setup_method(self):
        self.router = CommandRouter()

    def test_parse_engine(self):
        """/engine → query_whats_next."""
        from harness.command.commands.misc import QueryWhatsNextCommand
        result = self.router.parse("/engine")
        assert isinstance(result, QueryWhatsNextCommand)

    def test_parse_advance(self):
        """/advance → next."""
        from harness.command.commands.misc import NextCommand
        result = self.router.parse("/advance")
        assert isinstance(result, NextCommand)

    def test_parse_advance_with_args(self):
        """/advance my-eng → next with slug (args ignored for next)."""
        from harness.command.commands.misc import NextCommand
        result = self.router.parse("/advance my-eng")
        assert isinstance(result, NextCommand)

    def test_all_standard_commands_still_work(self):
        """Existing commands are unaffected."""
        mappings = [
            ("/next", "next"),
            ("/abort", "abort_engagement"),
            ("/stop", "abort_engagement"),
            ("/status", "query_status"),
            ("/health", "query_status"),
            ("/whatsnext", "query_whats_next"),
            ("/phase", "enter_phase"),
            ("/create", "create_engagement"),
            ("/resume", "resume_engagement"),
            ("/wave", "create_wave"),
            ("/step", "execute_step"),
        ]
        for input_text, expected_type in mappings:
            result = self.router.parse(input_text)
            assert result is not None, f"'{input_text}' should parse to a command"
            result_name = _command_type_name(result)
            assert result_name == expected_type, (
                f"'{input_text}' → expected '{expected_type}', got '{result_name}'"
            )

    def test_unknown_prefix_still_works(self):
        """Unknown /-command returns None (no match)."""
        result = self.router.parse("/unknown_cmd")
        assert result is None
