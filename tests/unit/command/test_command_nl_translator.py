"""Tests for NLTranslator — natural language to command translation.

Full implementation tests (Wave 8b):

Confidence tiers (V7 §5.21, W4):
- confidence >= 0.75 → auto-dispatch (auto_dispatch=True)
- 0 < confidence < 0.75 → needs user confirmation (needs_confirmation=True)
- confidence == 0 → conversation (is_conversation=True)

Command patterns tested:
- abort / stop
- create engagement
- resume engagement
- status / health
- what's next
- enter / go to phase
- next / advance / proceed
- create wave
- execute step

Config integration:
- DEFAULT_CONFIDENCE_THRESHOLD
- Custom threshold
- from_settings() factory
- set_threshold() validation
"""

from __future__ import annotations

import pytest

from harness.command.nl_translator import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    NLTranslator,
    TranslationResult,
)
from harness.command.types import TypedCommand
from harness.config import NLTranslatorSettings


# ── Typed command class imports ──────────────────────────────────────────


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


class TestNLTranslatorDefaults:
    """NLTranslator — default configuration."""

    def setup_method(self):
        self.translator = NLTranslator()

    def test_default_threshold(self):
        """Default confidence threshold is 0.75."""
        assert self.translator.confidence_threshold == DEFAULT_CONFIDENCE_THRESHOLD
        assert DEFAULT_CONFIDENCE_THRESHOLD == 0.75

    def test_custom_threshold(self):
        """Custom threshold is used instead of default."""
        translator = NLTranslator(confidence_threshold=0.9)
        assert translator.confidence_threshold == 0.9

    def test_threshold_zero(self):
        """Threshold of 0.0 is valid (all commands need confirmation)."""
        translator = NLTranslator(confidence_threshold=0.0)
        assert translator.confidence_threshold == 0.0

    def test_threshold_one(self):
        """Threshold of 1.0 is valid (only perfect matches auto-dispatch)."""
        translator = NLTranslator(confidence_threshold=1.0)
        assert translator.confidence_threshold == 1.0

    def test_from_settings_default(self):
        """from_settings() with no args creates translator with defaults."""
        translator = NLTranslator.from_settings()
        assert translator.confidence_threshold == DEFAULT_CONFIDENCE_THRESHOLD

    def test_from_settings_custom(self):
        """from_settings() with custom settings uses the provided threshold."""
        settings = NLTranslatorSettings(confidence_threshold=0.5)
        translator = NLTranslator.from_settings(settings)
        assert translator.confidence_threshold == 0.5


class TestNLTranslatorInputValidation:
    """NLTranslator — input validation."""

    def setup_method(self):
        self.translator = NLTranslator()

    def test_empty_input(self):
        """Empty input → conversation mode with message."""
        result = self.translator.translate("")
        assert result.is_conversation is True
        assert result.confidence == 0.0

    def test_whitespace_input(self):
        """Whitespace input → conversation mode with message."""
        result = self.translator.translate("   ")
        assert result.is_conversation is True
        assert result.confidence == 0.0

    def test_translate_returns_consistent_type(self):
        """TranslationResult has all expected fields."""
        result = self.translator.translate("test")
        assert isinstance(result, TranslationResult)
        assert result.command is None
        assert isinstance(result.confidence, float)
        assert isinstance(result.auto_dispatch, bool)
        assert isinstance(result.needs_confirmation, bool)
        assert isinstance(result.is_conversation, bool)
        assert isinstance(result.message, str)
        assert isinstance(result.suggested_command, str)
        assert isinstance(result.threshold, float)


class TestNLTranslatorTier1AutoDispatch:
    """NLTranslator — Tier 1: confidence >= threshold → auto-dispatch.

    With default threshold 0.75, any match with confidence >= 0.75
    should auto-dispatch.
    """

    def setup_method(self):
        self.translator = NLTranslator(confidence_threshold=0.75)

    def test_abort_auto_dispatches(self):
        """'abort the engagement' auto-dispatches at high confidence."""
        result = self.translator.translate("abort the engagement")
        assert result.auto_dispatch is True
        assert result.command is not None
        assert _command_type_name(result.command) == "abort_engagement"
        assert result.confidence >= result.threshold
        assert result.is_conversation is False

    def test_status_auto_dispatches(self):
        """'status' auto-dispatches at high confidence."""
        result = self.translator.translate("status")
        assert result.auto_dispatch is True
        assert result.command is not None
        assert _command_type_name(result.command) == "query_status"
        assert result.confidence >= result.threshold

    def test_health_auto_dispatches(self):
        """'health check' auto-dispatches."""
        result = self.translator.translate("health")
        assert result.auto_dispatch is True
        assert _command_type_name(result.command) == "query_status"

    def test_next_auto_dispatches(self):
        """'next' auto-dispatches at high confidence."""
        result = self.translator.translate("next")
        assert result.auto_dispatch is True
        assert _command_type_name(result.command) == "next"

    def test_advance_auto_dispatches(self):
        """'advance' auto-dispatches."""
        result = self.translator.translate("advance")
        assert result.auto_dispatch is True
        assert _command_type_name(result.command) == "next"

    def test_create_engagement_auto_dispatches(self):
        """'create a new engagement' auto-dispatches."""
        result = self.translator.translate("create a new engagement")
        assert result.auto_dispatch is True
        assert _command_type_name(result.command) == "create_engagement"

    def test_stop_auto_dispatches(self):
        """'stop' auto-dispatches as hard abort."""
        result = self.translator.translate("stop")
        assert result.auto_dispatch is True
        assert _command_type_name(result.command) == "abort_engagement"
        assert result.command.mode == "hard"

    def test_hard_abort_auto_dispatches(self):
        """'hard-abort' auto-dispatches with hard mode."""
        result = self.translator.translate("hard-abort")
        assert result.auto_dispatch is True
        assert _command_type_name(result.command) == "abort_engagement"
        assert result.command.mode == "hard"

    def test_whats_next_auto_dispatches(self):
        """'what's next?' auto-dispatches."""
        result = self.translator.translate("what's next")
        assert result.auto_dispatch is True
        assert _command_type_name(result.command) == "query_whats_next"

    def test_create_wave_auto_dispatches(self):
        """'create wave' auto-dispatches."""
        result = self.translator.translate("create a new wave")
        assert result.auto_dispatch is True
        assert _command_type_name(result.command) == "create_wave"

    def test_enter_phase_auto_dispatches(self):
        """'enter phase design' auto-dispatches with phase data."""
        result = self.translator.translate("enter phase design")
        assert result.auto_dispatch is True
        assert _command_type_name(result.command) == "enter_phase"
        assert result.command.phase == "design"

    def test_resume_engagement_auto_dispatches(self):
        """'resume the engagement' auto-dispatches."""
        result = self.translator.translate("resume the engagement")
        assert result.auto_dispatch is True
        assert _command_type_name(result.command) == "resume_engagement"

    def test_proceed_auto_dispatches(self):
        """'proceed' auto-dispatches."""
        result = self.translator.translate("proceed")
        assert result.auto_dispatch is True
        assert _command_type_name(result.command) == "next"

    def test_slug_passed_to_command(self):
        """Slug is passed through to the typed command."""
        result = self.translator.translate("status", slug="my-eng")
        assert result.command is not None
        assert result.command.slug == "my-eng"

    def test_please_prefix_auto_dispatches(self):
        """'please abort' still auto-dispatches correctly."""
        result = self.translator.translate("please abort the engagement")
        assert result.auto_dispatch is True
        assert _command_type_name(result.command) == "abort_engagement"


class TestNLTranslatorTier2NeedsConfirmation:
    """NLTranslator — Tier 2: 0 < confidence < threshold → confirm.

    With default threshold 0.75, lower-confidence matches should
    require user confirmation.
    """

    def setup_method(self):
        # Lower the threshold to test the middle tier
        # With threshold 0.95, most patterns (0.80-0.95) need confirmation
        self.translator = NLTranslator(confidence_threshold=0.95)

    def test_lower_confidence_needs_confirmation(self):
        """Matches below threshold need user confirmation."""
        result = self.translator.translate("run step build")
        # execute_step has weight 0.80, below 0.95
        assert result.confidence > 0
        assert result.confidence < result.threshold
        assert result.needs_confirmation is True
        assert result.auto_dispatch is False
        assert result.is_conversation is False
        assert result.command is not None

    def test_execute_step_confirmation(self):
        """'execute step build' needs confirmation with threshold 0.95."""
        result = self.translator.translate("execute step build")
        assert result.needs_confirmation is True
        assert _command_type_name(result.command) == "execute_step"

    def test_suggested_command_is_formatted(self):
        """Suggested command is displayed for confirmation."""
        result = self.translator.translate("abort")
        assert result.needs_confirmation is True
        assert result.suggested_command != ""
        # Should suggest something like /abort graceful
        assert "/abort" in result.suggested_command
        assert "graceful" in result.suggested_command

    def test_medium_threshold_captures_mid_tier(self):
        """With threshold 0.90, weight 0.85 patterns need confirmation."""
        translator = NLTranslator(confidence_threshold=0.90)
        result = translator.translate("stop")  # weight 0.85
        assert result.needs_confirmation is True
        assert result.auto_dispatch is False

    def test_nearly_high_confidence_needs_confirmation(self):
        """Just below threshold still requires confirmation."""
        translator = NLTranslator(confidence_threshold=0.96)
        # status exact match has weight 0.95
        result = translator.translate("what's the status")
        assert result.needs_confirmation is True
        assert result.confidence < result.threshold

    def test_confirmation_has_command(self):
        """Confirmation-tier results still include the command."""
        result = self.translator.translate("create engagement")
        assert result.command is not None
        assert _command_type_name(result.command) == "create_engagement"
        assert result.needs_confirmation is True

    def test_confirm_message_includes_confidence(self):
        """Confirmation message includes confidence value."""
        result = self.translator.translate("create engagement")
        assert "confidence" in result.message.lower()


class TestNLTranslatorTier3Conversation:
    """NLTranslator — Tier 3: confidence == 0 → conversation."""

    def setup_method(self):
        self.translator = NLTranslator()

    def test_greeting_is_conversation(self):
        """Simple greeting does not match any command pattern."""
        result = self.translator.translate("hello")
        assert result.is_conversation is True
        assert result.command is None
        assert result.confidence == 0.0

    def test_question_is_conversation(self):
        """General question does not match any command pattern."""
        result = self.translator.translate("how does this work?")
        assert result.is_conversation is True
        assert result.confidence == 0.0

    def test_random_text_is_conversation(self):
        """Non-command text routes to conversation."""
        texts = [
            "that's interesting",
            "what do you think",
            "tell me more",
            "ok thanks",
            "let me think about this",
        ]
        for text in texts:
            result = self.translator.translate(text)
            assert result.is_conversation is True, (
                f"'{text}' should route to conversation"
            )
            assert result.confidence == 0.0

    def test_conversation_has_no_command(self):
        """Conversation results have no command."""
        result = self.translator.translate("what do you think?")
        assert result.command is None

    def test_conversation_has_message(self):
        """Conversation results include a descriptive message."""
        result = self.translator.translate("hello")
        assert result.message != ""
        assert "conversation" in result.message.lower() or "command" in result.message.lower()

    def test_empty_suggested_command(self):
        """Conversation-tier results have empty suggested_command."""
        result = self.translator.translate("hello")
        assert result.suggested_command == ""


class TestNLTranslatorThresholdEdgeCases:
    """NLTranslator — threshold edge cases and boundary testing."""

    def test_set_threshold_valid(self):
        """set_threshold() updates the threshold."""
        translator = NLTranslator()
        translator.set_threshold(0.5)
        assert translator.confidence_threshold == 0.5

    def test_set_threshold_too_low(self):
        """set_threshold() below 0.0 raises ValueError."""
        translator = NLTranslator()
        with pytest.raises(ValueError, match="0.0 and 1.0"):
            translator.set_threshold(-0.1)

    def test_set_threshold_too_high(self):
        """set_threshold() above 1.0 raises ValueError."""
        translator = NLTranslator()
        with pytest.raises(ValueError, match="0.0 and 1.0"):
            translator.set_threshold(1.5)

    def test_threshold_zero_all_auto_dispatch(self):
        """With threshold 0.0, all matches auto-dispatch."""
        translator = NLTranslator(confidence_threshold=0.0)
        result = translator.translate("status")
        # All positive confidences are >= 0.0, so auto-dispatch
        assert result.confidence > 0
        assert result.auto_dispatch is True
        assert result.needs_confirmation is False

    def test_threshold_one_none_auto_dispatch(self):
        """With threshold 1.0, nothing auto-dispatches."""
        translator = NLTranslator(confidence_threshold=1.0)
        result = translator.translate("status")
        assert result.confidence < 1.0
        assert result.needs_confirmation is True
        assert result.auto_dispatch is False

    def test_tier2_and_tier3_threshold_boundary(self):
        """Non-matching text is always conversation regardless of threshold."""
        translator = NLTranslator(confidence_threshold=0.0)
        # Non-matching text: confidence 0, so still conversation
        result = translator.translate("hello")
        assert result.confidence == 0.0
        assert result.is_conversation is True


class TestNLTranslatorConfidenceThreshold:
    """NLTranslator — threshold boundary transitions.

    Test the behaviour at the confidence-threshold boundary:
    - confidence == threshold → auto-dispatch (tier 1)
    - confidence just below threshold → needs confirmation (tier 2)
    """

    def test_auto_dispatch_threshold_exact(self):
        """Confidence >= threshold triggers auto-dispatch."""
        # 'status' short form has weight 0.90, matches exactly
        translator = NLTranslator(confidence_threshold=0.90)
        result = translator.translate("status")
        assert result.auto_dispatch is True
        assert result.confidence >= result.threshold

    def test_confirmation_below_threshold(self):
        """Confidence just below threshold needs confirmation."""
        translator = NLTranslator(confidence_threshold=0.91)
        result = translator.translate("execute step test")
        # execute_step weight 0.80, well below 0.91
        assert result.needs_confirmation is True
        assert result.confidence < result.threshold


class TestNLTranslatorConfigIntegration:
    """NLTranslator — config integration via from_settings()."""

    def test_from_settings_with_path(self):
        """from_settings() creates translator from settings data."""
        settings = NLTranslatorSettings(confidence_threshold=0.8)
        translator = NLTranslator.from_settings(settings)
        assert translator.confidence_threshold == 0.8

    def test_translate_with_custom_threshold(self):
        """Translation respects custom threshold from settings."""
        settings = NLTranslatorSettings(confidence_threshold=0.5)
        translator = NLTranslator.from_settings(settings)
        # Most patterns have weight >= 0.80, so auto-dispatch at 0.5
        result = translator.translate("create engagement")
        assert result.auto_dispatch is True

    def test_translate_high_threshold_from_settings(self):
        """With high threshold, patterns need confirmation."""
        settings = NLTranslatorSettings(confidence_threshold=0.99)
        translator = NLTranslator.from_settings(settings)
        result = translator.translate("status")
        assert result.needs_confirmation is True
        assert result.auto_dispatch is False


class TestNLTranslatorEdgeCases:
    """NLTranslator — edge cases for pattern matching."""

    def setup_method(self):
        self.translator = NLTranslator()

    def test_trailing_text_lower_confidence(self):
        """Trailing text after command slightly reduces confidence."""
        result1 = self.translator.translate("status")
        result2 = self.translator.translate("status of the current thing")
        # Both should still auto-dispatch
        assert result1.auto_dispatch is True
        assert result2.auto_dispatch is True
        assert result1.confidence >= result1.threshold
        assert result2.confidence >= result2.threshold

    def test_command_with_data(self):
        """Parameterised commands have data populated."""
        result = self.translator.translate("enter phase build")
        assert result.command is not None
        assert result.command.phase == "build"

    def test_abort_mode_graceful(self):
        """Graceful abort mode is set correctly."""
        result = self.translator.translate("gracefully abort the engagement")
        assert result.command is not None
        assert result.command.mode == "graceful"

    def test_hard_abort_mode(self):
        """Hard abort mode is set for 'hard-abort'."""
        result = self.translator.translate("hard-abort")
        assert result.command is not None
        assert result.command.mode == "hard"

    def test_suggested_command_format(self):
        """Suggested command string is well-formatted."""
        result = self.translator.translate("status")
        assert result.suggested_command == "/status"

        result = self.translator.translate("abort the engagement")
        assert "/abort" in result.suggested_command

        result = self.translator.translate("enter phase design")
        assert "/phase" in result.suggested_command

    def test_case_insensitive_matching(self):
        """Patterns match case-insensitively."""
        result1 = self.translator.translate("STATUS")
        result2 = self.translator.translate("Create Engagement")
        result3 = self.translator.translate("Abort The Engagement")
        assert result1.auto_dispatch is True
        assert result2.auto_dispatch is True
        assert result3.auto_dispatch is True

    def test_partial_word_no_false_positive(self):
        """Partial word should not false-positive match."""
        result = self.translator.translate("statistics")
        # Should not match 'status' pattern
        assert result.is_conversation is True

    def test_execute_run_step(self):
        """'run step X' matches execute_step."""
        result = self.translator.translate("run step build")
        assert result.command is not None
        assert _command_type_name(result.command) == "execute_step"

    def test_create_wave_with_title(self):
        """'create wave testing' matches create_wave."""
        result = self.translator.translate("create a wave testing")
        assert result.command is not None
        assert _command_type_name(result.command) == "create_wave"


class TestTranslationResult:
    """TranslationResult dataclass."""

    def test_defaults(self):
        result = TranslationResult()
        assert result.command is None
        assert result.confidence == 0.0
        assert result.threshold == DEFAULT_CONFIDENCE_THRESHOLD
        assert result.auto_dispatch is False
        assert result.needs_confirmation is False
        assert result.is_conversation is True
        assert result.message == ""
        assert result.suggested_command == ""

    def test_auto_dispatch_true(self):
        """auto_dispatch True when confidence >= threshold."""
        result = TranslationResult(
            confidence=0.8,
            threshold=0.75,
            auto_dispatch=True,
        )
        assert result.auto_dispatch is True
        assert result.confidence >= result.threshold

    def test_needs_confirmation(self):
        """needs_confirmation True when 0 < confidence < threshold."""
        result = TranslationResult(
            confidence=0.5,
            threshold=0.75,
            needs_confirmation=True,
            is_conversation=False,
        )
        assert result.needs_confirmation is True
        assert result.is_conversation is False

    def test_is_conversation(self):
        """is_conversation True when confidence == 0."""
        result = TranslationResult(
            confidence=0.0,
            is_conversation=True,
        )
        assert result.is_conversation is True
        assert result.auto_dispatch is False
        assert result.needs_confirmation is False


class TestNLTranslatorCommandBusIntegration:
    """NLTranslator — integration with CommandBus.

    Tests that the translator produces typed commands that the CommandBus
    can dispatch.
    """

    def setup_method(self):
        self.translator = NLTranslator()

    def test_translate_creates_valid_command(self):
        """Translated command is a TypedCommand with correct slug."""
        result = self.translator.translate("status", slug="my-eng")
        assert result.auto_dispatch is True
        assert result.command is not None
        assert isinstance(result.command, TypedCommand)
        assert result.command.slug == "my-eng"
        assert _command_type_name(result.command) == "query_status"

    def test_abort_command_data(self):
        """Abort commands produce typed AbortEngagementCommand with correct mode."""
        result = self.translator.translate("stop")
        assert result.command is not None
        assert _command_type_name(result.command) == "abort_engagement"
        assert result.command.mode == "hard"

        # 'abort' defaults to graceful
        result2 = self.translator.translate("abort")
        assert result2.command is not None
        assert _command_type_name(result2.command) == "abort_engagement"
        assert result2.command.mode == "graceful"

    def test_all_known_commands_produce_match(self):
        """All known command types produce a match at some confidence."""
        commands = [
            ("status", "query_status"),
            ("next", "next"),
            ("advance", "next"),
            ("what's next", "query_whats_next"),
            ("what is next", "query_whats_next"),
            ("abort", "abort_engagement"),
            ("hard-abort", "abort_engagement"),
            ("stop", "abort_engagement"),
            ("create a new engagement", "create_engagement"),
            ("resume the engagement", "resume_engagement"),
            ("enter phase design", "enter_phase"),
            ("create a wave", "create_wave"),
            ("execute step build", "execute_step"),
            ("proceed", "next"),
            ("show me the status", "query_status"),
        ]

        for text, expected_type in commands:
            result = self.translator.translate(text)
            assert result.command is not None, (
                f"'{text}' should match a command"
            )
            assert _command_type_name(result.command) == expected_type, (
                f"'{text}' should produce '{expected_type}', "
                f"got '{_command_type_name(result.command)}'"
            )


class TestWebSearchFactory:
    """Tests for create_web_search_provider factory."""

    def test_create_duckduckgo(self):
        """Factory creates DuckDuckGo provider by default."""
        from harness.skills.builtin.web_search import (
            DuckDuckGoProvider,
            create_web_search_provider,
        )

        provider = create_web_search_provider()
        assert isinstance(provider, DuckDuckGoProvider)

    def test_create_searxng(self):
        """Factory creates SearXNG provider when specified."""
        from harness.skills.builtin.web_search import (
            SearXNGProvider,
            create_web_search_provider,
        )

        provider = create_web_search_provider(
            provider_name="searxng",
            searxng_url="http://search.example.com:8888",
        )
        assert isinstance(provider, SearXNGProvider)
        assert "search.example.com" in provider._base_url

    def test_create_invalid_provider(self):
        """Factory raises ValueError for unknown provider."""
        from harness.skills.builtin.web_search import create_web_search_provider

        with pytest.raises(ValueError, match="Unknown web search provider"):
            create_web_search_provider(provider_name="brave")
