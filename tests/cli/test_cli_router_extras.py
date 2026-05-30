"""Tests for additional CommandRouter routing entries added in Wave 8.

Covers:
- `/engine` → `query_whats_next`
- `/advance` → `next`
"""

from __future__ import annotations

import pytest

from harness.command.router import CommandRouter
from harness.command.types import Command


class TestRouterExtras:
    """CommandRouter — new /-prefix commands added in Wave 8."""

    def setup_method(self):
        self.router = CommandRouter()

    def test_parse_engine(self):
        """/engine → query_whats_next."""
        result = self.router.parse("/engine")
        assert result is not None
        assert result.command_type == "query_whats_next"
        assert result.data == {}

    def test_parse_advance(self):
        """/advance → next."""
        result = self.router.parse("/advance")
        assert result is not None
        assert result.command_type == "next"
        assert result.data == {}

    def test_parse_advance_with_args(self):
        """/advance my-eng → next with slug (args ignored for next)."""
        result = self.router.parse("/advance my-eng")
        assert result is not None
        assert result.command_type == "next"

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
            ("/help", "help"),
        ]
        for input_text, expected_type in mappings:
            result = self.router.parse(input_text)
            assert result is not None, f"'{input_text}' should parse to a command"
            assert result.command_type == expected_type, (
                f"'{input_text}' → expected '{expected_type}', got '{result.command_type}'"
            )

    def test_unknown_prefix_still_works(self):
        """Unknown /-command still maps as-is."""
        result = self.router.parse("/unknown_cmd")
        assert result is not None
        assert result.command_type == "unknown_cmd"
