"""Tests for PromptContextBudget — advisory context budget check.

Covers:
- PromptContextBudget.check() returns False when within budget
- PromptContextBudget.check() returns True when over budget
- Empty prompt and edge cases
- MAX_PROMPT_CHARS default
"""

from __future__ import annotations

import pytest

from harness.phase.pruning import PromptContextBudget


class TestPromptContextBudget:
    """PromptContextBudget — advisory context budget check."""

    def test_check_within_budget(self):
        """Prompt within budget → returns False (no warning)."""
        short_prompt = "Hello, world!"
        result = PromptContextBudget.check(short_prompt)
        assert result is False

    def test_check_at_budget(self):
        """Prompt exactly at budget → returns False."""
        exact_prompt = "A" * PromptContextBudget.MAX_PROMPT_CHARS
        result = PromptContextBudget.check(exact_prompt)
        assert result is False

    def test_check_over_budget(self):
        """Prompt over budget → returns True (logs warning)."""
        long_prompt = "A" * (PromptContextBudget.MAX_PROMPT_CHARS + 1)
        result = PromptContextBudget.check(long_prompt)
        assert result is True

    def test_check_empty_prompt(self):
        """Empty prompt → always within budget."""
        result = PromptContextBudget.check("")
        assert result is False

    def test_check_whitespace(self):
        """Whitespace prompt → within budget."""
        result = PromptContextBudget.check("   ")
        assert result is False

    def test_default_max_prompt_chars(self):
        """Default threshold is 16000."""
        assert PromptContextBudget.MAX_PROMPT_CHARS == 16_000

    def test_check_slightly_over(self):
        """Prompt slightly over budget → returns True."""
        prompt = "X" * (PromptContextBudget.MAX_PROMPT_CHARS + 10)
        result = PromptContextBudget.check(prompt)
        assert result is True

    def test_check_significantly_over(self):
        """Prompt significantly over budget → returns True."""
        prompt = "X" * (PromptContextBudget.MAX_PROMPT_CHARS * 2)
        result = PromptContextBudget.check(prompt)
        assert result is True
