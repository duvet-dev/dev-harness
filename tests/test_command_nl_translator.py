"""Tests for NLTranslator — natural language to command translation.

Covers:
- NLTranslator.translate() returns conversation mode (confidence 0.0) for Wave 6 stub
- Default confidence threshold (0.75)
- Custom confidence threshold
- Input validation (empty, whitespace)
- set_threshold() validation
"""

from __future__ import annotations

import pytest

from harness.command.nl_translator import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    NLTranslator,
    TranslationResult,
)


class TestNLTranslator:
    """NLTranslator — free-text to command translation (Wave 6 stub)."""

    def setup_method(self):
        self.translator = NLTranslator()

    def test_translate_conversation_mode(self):
        """All text returns confidence 0.0 (conversation mode) in Wave 6 stub."""
        result = self.translator.translate("hello")

        assert result.command is None
        assert result.confidence == 0.0
        assert result.auto_dispatch is False
        assert result.needs_confirmation is False
        assert result.is_conversation is True
        assert result.message != ""

    def test_default_threshold(self):
        """Default confidence threshold is 0.75."""
        assert self.translator.confidence_threshold == DEFAULT_CONFIDENCE_THRESHOLD
        assert DEFAULT_CONFIDENCE_THRESHOLD == 0.75

    def test_custom_threshold(self):
        """Custom threshold is used instead of default."""
        translator = NLTranslator(confidence_threshold=0.9)
        assert translator.confidence_threshold == 0.9

    def test_threshold_zero(self):
        """Threshold of 0.0 is valid (no auto-dispatch)."""
        translator = NLTranslator(confidence_threshold=0.0)
        assert translator.confidence_threshold == 0.0

    def test_threshold_one(self):
        """Threshold of 1.0 is valid (only perfect matches auto-dispatch)."""
        translator = NLTranslator(confidence_threshold=1.0)
        assert translator.confidence_threshold == 1.0

    def test_translate_with_slug(self):
        """Slug passed through to result."""
        result = self.translator.translate("hello", slug="my-eng")
        assert result.is_conversation is True

    def test_translate_empty_input(self):
        """Empty input → conversation mode with message."""
        result = self.translator.translate("")
        assert result.is_conversation is True
        assert result.confidence == 0.0

    def test_translate_whitespace_input(self):
        """Whitespace input → conversation mode with message."""
        result = self.translator.translate("   ")
        assert result.is_conversation is True
        assert result.confidence == 0.0

    def test_set_threshold_valid(self):
        """set_threshold() updates the threshold."""
        self.translator.set_threshold(0.5)
        assert self.translator.confidence_threshold == 0.5

    def test_set_threshold_too_low(self):
        """set_threshold() below 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="0.0 and 1.0"):
            self.translator.set_threshold(-0.1)

    def test_set_threshold_too_high(self):
        """set_threshold() above 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="0.0 and 1.0"):
            self.translator.set_threshold(1.5)

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

    def test_stub_no_command_detection(self):
        """Stub never detects a command (always conversation)."""
        inputs = [
            "abort the engagement",
            "please stop",
            "what's next?",
            "show me the health",
            "create a new engagement",
        ]
        for text in inputs:
            result = self.translator.translate(text)
            assert result.is_conversation is True, (
                f"Stub should route '{text}' to conversation"
            )


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
