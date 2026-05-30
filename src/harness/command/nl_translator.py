"""NLTranslator — natural language to command translation — V7 §5.21.

Full implementation (Wave 8b). Translates free-text user input into
typed CommandBus commands using pattern matching and confidence scoring.

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

import re
from dataclasses import dataclass, field
from typing import Any

from harness.command.types import TypedCommand
from harness.config import NLTranslatorSettings


# ── Default confidence threshold (W4) ────────────────────────────────────

DEFAULT_CONFIDENCE_THRESHOLD: float = 0.75


# ── Pattern definitions ─────────────────────────────────────────────────

# Each pattern is a tuple of (pattern_name, regex, command_type, data_builder, weight)
# weight is the base confidence when the pattern matches
# data_builder takes (matched_groups) and returns a dict of kwargs

_Pattern = tuple[str, re.Pattern, str, Any, float]


def _no_data(groups: tuple[str, ...]) -> dict:
    return {}


def _mode_data(groups: tuple[str, ...]) -> dict:
    mode = "graceful"
    if groups and groups[0]:
        m = groups[0].strip().lower()
        if m in ("hard", "force", "immediately"):
            mode = "hard"
    return {"mode": mode}


def _phase_data(groups: tuple[str, ...]) -> dict:
    phase = groups[0].strip() if groups and groups[0] else ""
    return {"phase": phase}


def _slug_data(groups: tuple[str, ...]) -> dict:
    slug = groups[0].strip() if groups and groups[0] else ""
    return {"slug": slug}


def _step_data(groups: tuple[str, ...]) -> dict:
    step_spec = groups[0].strip() if groups and groups[0] else ""
    return {"step": step_spec}


# ── Build typed command from command_type string and kwargs ──────────────

_TYPED_COMMAND_MAP: dict[str, type] = {}


def _get_typed_command_class(command_type: str) -> type:
    """Lazy-import and cache the typed command class for a command type."""
    if not _TYPED_COMMAND_MAP:
        _build_command_map()
    cls = _TYPED_COMMAND_MAP.get(command_type)
    if cls is None:
        raise ValueError(f"No typed command class for type '{command_type}'")
    return cls


def _build_command_map() -> None:
    """Populate the command type string -> typed command class mapping."""
    from harness.command.commands.engagement import (
        AbortEngagementCommand,
        CreateEngagementCommand,
        ResumeEngagementCommand,
    )
    from harness.command.commands.phase import EnterPhaseCommand
    from harness.command.commands.wave import CreateWaveCommand, ExecuteStepCommand
    from harness.command.commands.misc import (
        NextCommand,
        QueryStatusCommand,
        QueryWhatsNextCommand,
    )
    _TYPED_COMMAND_MAP.update({
        "next": NextCommand,
        "query_whats_next": QueryWhatsNextCommand,
        "abort_engagement": AbortEngagementCommand,
        "create_engagement": CreateEngagementCommand,
        "resume_engagement": ResumeEngagementCommand,
        "query_status": QueryStatusCommand,
        "enter_phase": EnterPhaseCommand,
        "create_wave": CreateWaveCommand,
        "execute_step": ExecuteStepCommand,
    })


def _build_typed_command(command_type: str, data: dict, slug: str) -> TypedCommand:
    """Construct a typed command from command_type string and kwargs.

    Args:
        command_type: The command type string.
        data: Keyword arguments for the typed command constructor.
        slug: The engagement slug.

    Returns:
        A typed command instance.
    """
    cls = _get_typed_command_class(command_type)
    kwargs = dict(data)
    kwargs.setdefault("slug", slug)
    return cls(**kwargs)


# ── NL command patterns (ordered by specificity, descending) ───────────
# The first match wins, so more specific patterns must come first.

_COMMAND_PATTERNS: list[_Pattern] = [
    # ── Next / Advance / Proceed (must come BEFORE whats_next) ─────
    (   "next",
        re.compile(
            r"^(?:please\s+)?(?:next|advance|proceed|continue)\b",
            re.IGNORECASE,
        ),
        "next",
        _no_data,
        0.85,
    ),
    # ── What's next ─────────────────────────────────────────────────
    (   "whats_next",
        re.compile(
            r"^(?:what(?:\'s| is)\s+)?next\b",
            re.IGNORECASE,
        ),
        "query_whats_next",
        _no_data,
        0.90,
    ),
    (   "whats_next_long",
        re.compile(
            r"^(?:what\s+should\s+(?:I|we)\s+do\s+next"
            r"|show\s+(?:me\s+)?(?:what\s+)?next)",
            re.IGNORECASE,
        ),
        "query_whats_next",
        _no_data,
        0.85,
    ),
    # ── Abort / Stop — graceful before hard ─────────────────────────
    (   "abort_graceful",
        re.compile(
            r"^(?:please\s+)?(?:gracefully\s+)?abort\b",
            re.IGNORECASE,
        ),
        "abort_engagement",
        lambda g: {"mode": "graceful"},
        0.90,
    ),
    (   "abort_hard",
        re.compile(
            r"^(?:please\s+)?hard[- ]abort\b",
            re.IGNORECASE,
        ),
        "abort_engagement",
        lambda g: {"mode": "hard"},
        0.95,
    ),
    (   "stop",
        re.compile(
            r"^(?:please\s+)?(?:stop|halt|cancel)\b",
            re.IGNORECASE,
        ),
        "abort_engagement",
        lambda g: {"mode": "hard"},
        0.85,
    ),
    # ── Create / new engagement ─────────────────────────────────────
    (   "create_engagement",
        re.compile(
            r"^(?:please\s+)?(?:create|start|new|initialize)\s+"
            r"(?:a\s+|an\s+|the\s+)?(?:new\s+)?engagement",
            re.IGNORECASE,
        ),
        "create_engagement",
        _no_data,
        0.90,
    ),
    # ── Resume engagement ───────────────────────────────────────────
    (   "resume_engagement",
        re.compile(
            r"^(?:please\s+)?(?:resume|continue|restart)\s+"
            r"(?:the\s+)?(?:engagement\s+)?(\S+)",
            re.IGNORECASE,
        ),
        "resume_engagement",
        lambda g: ({"slug": g[0]} if g and g[0] else {}),
        0.85,
    ),
    # ── Status / Health ──────────────────────────────────────────────
    (   "query_status_exact",
        re.compile(
            r"^(?:what(?:\'s| is)\s+the\s+)?(?:status|health"
            r"|how\s+(?:are|is)\s+(?:we|things|it)\s+going)",
            re.IGNORECASE,
        ),
        "query_status",
        _no_data,
        0.95,
    ),
    (   "query_status_show",
        re.compile(
            r"^(?:show|check|get)\s+(?:me\s+)?(?:the\s+)?"
            r"(?:current\s+)?(?:engagement\s+)?"
            r"(?:status|health)",
            re.IGNORECASE,
        ),
        "query_status",
        _no_data,
        0.85,
    ),
    (   "query_status_short",
        re.compile(
            r"^(?:status|health)\b",
            re.IGNORECASE,
        ),
        "query_status",
        _no_data,
        0.90,
    ),
    # ── Enter / go to phase ─────────────────────────────────────────
    (   "enter_phase",
        re.compile(
            r"^(?:please\s+)?(?:enter|go\s+to|move\s+to|start)\s+"
            r"(?:phase\s+)?(\w+(?:\s+\w+)?)",
            re.IGNORECASE,
        ),
        "enter_phase",
        _phase_data,
        0.85,
    ),
    # Next / advance
    (   "next",
        re.compile(
            r"^(?:please\s+)?(?:next|advance|proceed|continue)\b",
            re.IGNORECASE,
        ),
        "next",
        _no_data,
        0.85,
    ),
    # Create wave
    (   "create_wave",
        re.compile(
            r"^(?:please\s+)?(?:create|add|new)\s+"
            r"(?:a\s+)?(?:new\s+)?wave",
            re.IGNORECASE,
        ),
        "create_wave",
        _no_data,
        0.90,
    ),
    # Execute / run step
    (   "execute_step",
        re.compile(
            r"^(?:please\s+)?(?:execute|run|do|perform)\s+"
            r"(?:step\s+)?(.+)",
            re.IGNORECASE,
        ),
        "execute_step",
        _step_data,
        0.80,
    ),
]


# ── Data types ──────────────────────────────────────────────────────────


@dataclass
class TranslationResult:
    """Result of NL-to-command translation.

    Attributes:
        command: The translated typed command, or None if no command
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

    command: TypedCommand | None = None
    confidence: float = 0.0
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    auto_dispatch: bool = False
    needs_confirmation: bool = False
    is_conversation: bool = True
    message: str = ""
    suggested_command: str = ""


class NLTranslator:
    """Translates free-text user input into typed CommandBus commands.

    Full implementation (Wave 8b) with pattern matching and
    three-tier confidence flow.

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

    @classmethod
    def from_settings(
        cls,
        settings: NLTranslatorSettings | None = None,
    ) -> NLTranslator:
        """Create an NLTranslator configured from settings.

        Args:
            settings: NLTranslatorSettings instance. If None,
                uses defaults.

        Returns:
            A configured NLTranslator instance.
        """
        if settings is None:
            settings = NLTranslatorSettings()
        return cls(confidence_threshold=settings.confidence_threshold)

    def translate(
        self,
        text: str,
        slug: str = "",
    ) -> TranslationResult:
        """Translate free-text input into a typed Command.

        Runs pattern matching against known command patterns and
        applies the three-tier confidence flow (V7 §5.21, W4):

        - confidence >= threshold → auto-dispatch
        - 0 < confidence < threshold → user confirmation
        - confidence == 0 → conversation (no command detected)

        Args:
            text: The free-text user input.
            slug: Optional engagement slug for the command.

        Returns:
            TranslationResult with confidence, command, and
            decision fields.
        """
        # Validate input
        if not text or not text.strip():
            return self._conversation_result(
                "Empty input — no command detected.",
            )

        clean_text = text.strip()

        # Run pattern matching against known command patterns
        matched_pattern, command_type, data, confidence = self._match_pattern(
            clean_text
        )

        if matched_pattern is None:
            # No pattern matched — conversation mode
            return self._conversation_result(
                "No command detected. Routing to conversation.",
            )

        # Build the typed command
        if slug:
            data.setdefault("slug", slug)
        try:
            command = _build_typed_command(command_type, data, slug)
        except (ValueError, TypeError, AttributeError) as exc:
            return TranslationResult(
                command=None,
                confidence=0.0,
                threshold=self.confidence_threshold,
                auto_dispatch=False,
                needs_confirmation=False,
                is_conversation=True,
                message=f"Failed to build command: {exc}",
                suggested_command="",
            )

        # Build human-readable suggested command string
        suggested = self._format_suggested_command(command_type, data)

        # Apply three-tier confidence flow
        threshold = self.confidence_threshold

        if confidence >= threshold:
            # Tier 1: auto-dispatch
            return TranslationResult(
                command=command,
                confidence=confidence,
                threshold=threshold,
                auto_dispatch=True,
                needs_confirmation=False,
                is_conversation=False,
                message=(
                    f"Auto-dispatching command '{command_type}' "
                    f"(confidence {confidence:.2f})"
                ),
                suggested_command=suggested,
            )

        if confidence > 0:
            # Tier 2: needs user confirmation
            return TranslationResult(
                command=command,
                confidence=confidence,
                threshold=threshold,
                auto_dispatch=False,
                needs_confirmation=True,
                is_conversation=False,
                message=(
                    f"Needs confirmation: '{suggested}' "
                    f"(confidence {confidence:.2f})"
                ),
                suggested_command=suggested,
            )

        # Tier 3: conversation (confidence == 0)
        return self._conversation_result(
            "No command detected. Routing to conversation.",
        )

    def _match_pattern(
        self,
        text: str,
    ) -> tuple[str | None, str, dict, float]:
        """Match text against known command patterns.

        Returns:
            Tuple of (pattern_name, command_type, data, confidence)
            or (None, "", {}, 0.0) if no pattern matched.
        """
        for pattern_name, regex, command_type, data_builder, weight in _COMMAND_PATTERNS:
            match = regex.search(text)
            if match:
                groups = match.groups()
                data = data_builder(groups)
                # Slight adjustment if the match isn't anchored at start
                confidence = weight
                if not text.lower().startswith(match.group().lower().split()[0]):
                    confidence *= 0.9  # Slight penalty for trailing context
                return pattern_name, command_type, data, confidence

        return None, "", {}, 0.0

    def _format_suggested_command(self, command_type: str, data: dict) -> str:
        """Format a human-readable suggested command string.

        Args:
            command_type: The command type string.
            data: The command data dict.

        Returns:
            A human-readable string like "/status" or "/abort hard".
        """
        routing_map = {
            "abort_engagement": "/abort",
            "create_engagement": "/create",
            "resume_engagement": "/resume",
            "enter_phase": "/phase",
            "next": "/next",
            "create_wave": "/wave",
            "execute_step": "/step",
            "query_status": "/status",
            "query_whats_next": "/whatsnext",
        }

        base = routing_map.get(command_type, f"/{command_type}")

        if command_type == "abort_engagement":
            mode = data.get("mode", "graceful")
            return f"{base} {mode}"
        if command_type == "enter_phase":
            phase = data.get("phase", "")
            return f"{base} {phase}" if phase else base
        if command_type == "create_wave":
            title = data.get("title", "")
            return f"{base} {title}" if title else base
        if command_type == "execute_step":
            step = data.get("step", "")
            return f"{base} {step}" if step else base

        return base

    def _conversation_result(
        self,
        message: str,
    ) -> TranslationResult:
        """Build a conversation-mode TranslationResult.

        Args:
            message: Human-readable description.

        Returns:
            TranslationResult with confidence 0.0 (conversation).
        """
        return TranslationResult(
            command=None,
            confidence=0.0,
            threshold=self.confidence_threshold,
            auto_dispatch=False,
            needs_confirmation=False,
            is_conversation=True,
            message=message,
            suggested_command="",
        )

    def set_threshold(self, threshold: float) -> None:
        """Update the confidence threshold at runtime.

        Args:
            threshold: New confidence threshold value (0.0–1.0).

        Raises:
            ValueError: If threshold is outside 0.0–1.0.
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(
                f"Confidence threshold must be between 0.0 and 1.0, "
                f"got {threshold}"
            )
        self.confidence_threshold = threshold
