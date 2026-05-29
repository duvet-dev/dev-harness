"""Tests for CommandRouter — parse user input into Command instances.

Covers:
- CommandRouter.parse() with /-prefixed commands
- Command mapping to correct command_type
- Free text returns None (routes to NLTranslator/chat)
- Parameterised commands (abort with mode, phase with name, wave with title)
- Unknown commands → mapped as-is
- Empty input and edge cases
"""

from __future__ import annotations

import pytest

from harness.command.router import CommandRouter
from harness.command.types import Command


class TestCommandRouter:
    """CommandRouter — parse user input."""

    def setup_method(self):
        self.router = CommandRouter()

    def test_parse_next(self):
        """/next → next command."""
        result = self.router.parse("/next")
        assert result is not None
        assert result.command_type == "next"

    def test_parse_abort_graceful(self):
        """/abort graceful → abort_engagement with mode=graceful."""
        result = self.router.parse("/abort graceful")
        assert result is not None
        assert result.command_type == "abort_engagement"
        assert result.data.get("mode") == "graceful"

    def test_parse_abort_hard(self):
        """/abort hard → abort_engagement with mode=hard."""
        result = self.router.parse("/abort hard")
        assert result is not None
        assert result.command_type == "abort_engagement"
        assert result.data.get("mode") == "hard"

    def test_parse_abort_default_mode(self):
        """/abort (no mode) → default graceful."""
        result = self.router.parse("/abort")
        assert result is not None
        assert result.data.get("mode") == "graceful"

    def test_parse_stop(self):
        """/stop → hard abort."""
        result = self.router.parse("/stop")
        assert result is not None
        assert result.command_type == "abort_engagement"
        assert result.data.get("mode") == "hard"

    def test_parse_status(self):
        """/status → query_status."""
        result = self.router.parse("/status")
        assert result is not None
        assert result.command_type == "query_status"

    def test_parse_health(self):
        """/health → query_status (alias)."""
        result = self.router.parse("/health")
        assert result is not None
        assert result.command_type == "query_status"

    def test_parse_whatsnext(self):
        """/whatsnext → query_whats_next."""
        result = self.router.parse("/whatsnext")
        assert result is not None
        assert result.command_type == "query_whats_next"

    def test_parse_phase(self):
        """/phase design → enter_phase with phase_name."""
        result = self.router.parse("/phase design")
        assert result is not None
        assert result.command_type == "enter_phase"
        assert result.data.get("phase_name") == "design"

    def test_parse_phase_empty(self):
        """/phase (no name) → enter_phase with empty phase_name."""
        result = self.router.parse("/phase")
        assert result is not None
        assert result.command_type == "enter_phase"
        assert result.data.get("phase_name") == ""

    def test_parse_create(self):
        """/create → create_engagement."""
        result = self.router.parse("/create")
        assert result is not None
        assert result.command_type == "create_engagement"

    def test_parse_resume(self):
        """/resume → resume_engagement."""
        result = self.router.parse("/resume")
        assert result is not None
        assert result.command_type == "resume_engagement"

    def test_parse_wave(self):
        """/wave My Wave → create_wave with title."""
        result = self.router.parse("/wave My Wave")
        assert result is not None
        assert result.command_type == "create_wave"
        assert result.data.get("title") == "My Wave"

    def test_parse_step(self):
        """/step {...} → execute_step with step spec."""
        result = self.router.parse("/step {}")
        assert result is not None
        assert result.command_type == "execute_step"
        assert result.data.get("step") == "{}"

    def test_parse_help(self):
        """/help → help command (special case)."""
        result = self.router.parse("/help")
        assert result is not None
        assert result.command_type == "help"
        assert result.data.get("text") == ""

    def test_parse_help_with_args(self):
        """/help phases → help command with args."""
        result = self.router.parse("/help phases")
        assert result is not None
        assert result.command_type == "help"
        assert result.data.get("text") == "phases"

    def test_parse_free_text(self):
        """Free text input → None (routes to NL translator / chat)."""
        result = self.router.parse("Tell me a joke")
        assert result is None

    def test_parse_empty_input(self):
        """Empty input → None."""
        result = self.router.parse("")
        assert result is None

    def test_parse_whitespace_input(self):
        """Whitespace-only input → None."""
        result = self.router.parse("   ")
        assert result is None

    def test_parse_slash_only(self):
        """Just / → None."""
        result = self.router.parse("/")
        assert result is None

    def test_parse_unknown_command(self):
        """Unknown /-command → mapped as-is with raw text."""
        result = self.router.parse("/unknown_cmd")
        assert result is not None
        assert result.command_type == "unknown_cmd"
        assert result.data.get("raw") == "unknown_cmd"

    def test_parse_with_slug(self):
        """parse() with slug attaches it to Command."""
        result = self.router.parse("/status", slug="my-eng")
        assert result is not None
        assert result.slug == "my-eng"
        assert result.command_type == "query_status"

    def test_parse_invalid_mode_fallback(self):
        """Invalid abort mode → fallback to graceful."""
        result = self.router.parse("/abort invalid_mode")
        assert result is not None
        assert result.data.get("mode") == "graceful"

    def test_all_standard_commands_map(self):
        """All standard /-commands map to correct types."""
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
