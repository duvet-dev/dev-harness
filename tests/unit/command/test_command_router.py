"""Tests for CommandRouter — parse user input into typed Command instances.

Covers:
- CommandRouter.parse() with /-prefixed commands
- Command mapping to correct typed command class
- Free text returns None (routes to NLTranslator/chat)
- Parameterised commands (abort with mode, phase with name, wave with title)
- Unknown commands → returned as-is
- Empty input and edge cases
"""

from __future__ import annotations

import pytest

from harness.command.router import CommandRouter
from harness.command.types import TypedCommand
from harness.command.commands.misc import (
    NextCommand,
    QueryWhatsNextCommand,
)
from harness.command.commands.engagement import (
    AbortEngagementCommand,
    CreateEngagementCommand,
    ResumeEngagementCommand,
)
from harness.command.commands.phase import EnterPhaseCommand
from harness.command.commands.wave import CreateWaveCommand, ExecuteStepCommand


def _command_type_name(cmd) -> str:
    """Helper to extract a readable command type name from a typed command."""
    mapping = {
        "AbortEngagementCommand": "abort_engagement",
        "CreateEngagementCommand": "create_engagement",
        "ResumeEngagementCommand": "resume_engagement",
        "EnterPhaseCommand": "enter_phase",
        "NextCommand": "next",
        "QueryStatusCommand": "query_status",
        "QueryWhatsNextCommand": "query_whats_next",
        "CreateWaveCommand": "create_wave",
        "ExecuteStepCommand": "execute_step",
    }
    name = type(cmd).__name__
    return mapping.get(name, name)


class TestCommandRouter:
    """CommandRouter — parse user input."""

    def setup_method(self):
        self.router = CommandRouter()

    def test_parse_next(self):
        """/next → NextCommand."""
        result = self.router.parse("/next")
        assert isinstance(result, NextCommand)

    def test_parse_abort_graceful(self):
        """/abort graceful → AbortEngagementCommand with mode=graceful."""
        result = self.router.parse("/abort graceful")
        assert isinstance(result, AbortEngagementCommand)
        assert result.mode == "graceful"

    def test_parse_abort_hard(self):
        """/abort hard → AbortEngagementCommand with mode=hard."""
        result = self.router.parse("/abort hard")
        assert isinstance(result, AbortEngagementCommand)
        assert result.mode == "hard"

    def test_parse_abort_default_mode(self):
        """/abort (no mode) → default graceful."""
        result = self.router.parse("/abort")
        assert isinstance(result, AbortEngagementCommand)
        assert result.mode == "graceful"

    def test_parse_stop(self):
        """/stop → hard abort."""
        result = self.router.parse("/stop")
        assert isinstance(result, AbortEngagementCommand)
        assert result.mode == "hard"

    def test_parse_status(self):
        """/status → QueryStatusCommand."""
        from harness.command.commands.misc import QueryStatusCommand
        result = self.router.parse("/status")
        assert isinstance(result, QueryStatusCommand)

    def test_parse_health(self):
        """/health → QueryStatusCommand (alias)."""
        from harness.command.commands.misc import QueryStatusCommand
        result = self.router.parse("/health")
        assert isinstance(result, QueryStatusCommand)

    def test_parse_whatsnext(self):
        """/whatsnext → QueryWhatsNextCommand."""
        result = self.router.parse("/whatsnext")
        assert isinstance(result, QueryWhatsNextCommand)

    def test_parse_phase(self):
        """/phase design → EnterPhaseCommand with phase."""
        result = self.router.parse("/phase design")
        assert isinstance(result, EnterPhaseCommand)
        assert result.phase == "design"

    def test_parse_phase_empty(self):
        """/phase (no name) → EnterPhaseCommand with empty phase."""
        result = self.router.parse("/phase")
        assert isinstance(result, EnterPhaseCommand)
        assert result.phase == ""

    def test_parse_create(self):
        """/create → CreateEngagementCommand."""
        result = self.router.parse("/create")
        assert isinstance(result, CreateEngagementCommand)

    def test_parse_resume(self):
        """/resume → ResumeEngagementCommand."""
        result = self.router.parse("/resume")
        assert isinstance(result, ResumeEngagementCommand)

    def test_parse_wave(self):
        """/wave My Wave → CreateWaveCommand with title."""
        result = self.router.parse("/wave My Wave")
        assert isinstance(result, CreateWaveCommand)
        assert result.title == "My Wave"

    def test_parse_step(self):
        """/step {} → ExecuteStepCommand with step spec."""
        result = self.router.parse("/step {}")
        assert isinstance(result, ExecuteStepCommand)
        assert result.step == "{}"

    def test_parse_help(self):
        """/help → None (special case, no dispatch)."""
        result = self.router.parse("/help")
        assert result is None

    def test_parse_help_with_args(self):
        """/help phases → None (special case)."""
        result = self.router.parse("/help phases")
        assert result is None

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
        """Unknown /-command → None (consumed but no match)."""
        result = self.router.parse("/unknown_cmd")
        assert result is None

    def test_parse_with_slug(self):
        """parse() with slug attaches it to typed command."""
        result = self.router.parse("/status", slug="my-eng")
        from harness.command.commands.misc import QueryStatusCommand
        assert isinstance(result, QueryStatusCommand)
        assert result.slug == "my-eng"

    def test_parse_invalid_mode_fallback(self):
        """Invalid abort mode → fallback to graceful."""
        result = self.router.parse("/abort invalid_mode")
        assert isinstance(result, AbortEngagementCommand)
        assert result.mode == "graceful"

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
        ]
        for input_text, expected_type in mappings:
            result = self.router.parse(input_text)
            assert result is not None, f"'{input_text}' should parse to a command"
            assert _command_type_name(result) == expected_type, (
                f"'{input_text}' → expected '{expected_type}', got '{_command_type_name(result)}'"
            )
