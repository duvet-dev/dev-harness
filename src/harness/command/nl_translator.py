"""NLTranslator — natural language to command translation — V7 §5.21.

Stub interface for translating free-text user input into
CommandBus commands. Full implementation deferred to Wave 8b.

Three-tier confidence flow (W4):
- confidence >= threshold (default 0.75) → auto-dispatch
- 0 < confidence < threshold → user confirm
- confidence == 0 → conversation (no command detected)

The NL translator is a **tool** invoked by the chat agent (W1),
not a router. The CommandRouter handles /-prefixed commands
directly.

Usage::

    translator = NLTranslator()
    result = translator.translate("please abort the engagement")
    # -> TranslationResult with confidence, command, message
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.command.types import Command


# ── Default confidence threshold (W4) ────────────────────────────────────

DEFAULT_CONFIDENCE_THRESHOLD: float = 0.75


@dataclass
class TranslationResult:
    """Result of NL-to-command translation.

    Attributes:
        command: The translated Command, or None if no command
            was detected (confidence == 0).
        confidence: The translation confidence score. 0.0 = no
            command detected, 1.0 = perfect match.
        threshold: The confidence threshold used.
        auto_dispatch: True if confidence >= threshold (should
            auto-dispatch).
        needs_confirmation: True if 0 < confidence < threshold
            (user should confirm before dispatch).
        is_conversation: True if confidence == 0 (no command
            detected — route to conversation).
        message: Human-readable description of the translation.
        suggested_command: The suggested command string for user
            confirmation display.
    """

    command: Command | None = None
    confidence: float = 0.0
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    auto_dispatch: bool = False
    needs_confirmation: bool = False
    is_conversation: bool = True
    message: str = ""
    suggested_command: str = ""


class NLTranslator:
    """Translates free-text user input into CommandBus commands.

    Wave 6 stub implementation: always returns confidence 0.0,
    routing all free text to conversation. Full implementation
    with NL understanding deferred to Wave 8b.

    The translator is stateless; all state is managed by the
    caller (CommandBus / chat agent).

    Attributes:
        confidence_threshold: The minimum confidence score for
            auto-dispatch. Configurable in settings.
    """

    def __init__(
        self,
        confidence_threshold: float | None = None,
    ) -> None:
        """Initialise the NLTranslator.

        Args:
            confidence_threshold: Confidence threshold for
                auto-dispatch (W4). Defaults to 0.75 if None.
                Configurable via .harness/settings.yaml.
        """
        self.confidence_threshold = (
            confidence_threshold if confidence_threshold is not None
            else DEFAULT_CONFIDENCE_THRESHOLD
        )

    def translate(
        self,
        text: str,
        slug: str = "",
    ) -> TranslationResult:
        """Translate free-text input into a Command.

        Wave 6 stub: always returns confidence 0.0, indicating
        conversation mode. No actual NL understanding.

        Args:
            text: The free-text user input.
            slug: Optional engagement slug for the command.

        Returns:
            TranslationResult with confidence 0.0 (conversation).
        """
        # Validate input
        if not text or not text.strip():
            return TranslationResult(
                command=None,
                confidence=0.0,
                threshold=self.confidence_threshold,
                auto_dispatch=False,
                needs_confirmation=False,
                is_conversation=True,
                message="Empty input — no command detected.",
                suggested_command="",
            )

        # Wave 6 stub: always conversation mode
        # Real implementation runs:
        #   1. Tokenise input
        #   2. Match against known command patterns
        #   3. Compute confidence score
        #   4. Apply three-tier flow based on threshold
        return TranslationResult(
            command=None,
            confidence=0.0,
            threshold=self.confidence_threshold,
            auto_dispatch=False,
            needs_confirmation=False,
            is_conversation=True,
            message="No command detected. Routing to conversation.",
            suggested_command="",
        )

    def set_threshold(self, threshold: float) -> None:
        """Update the confidence threshold at runtime.

        Args:
            threshold: New confidence threshold value (0.0–1.0).
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(
                f"Confidence threshold must be between 0.0 and 1.0, "
                f"got {threshold}"
            )
        self.confidence_threshold = threshold
