"""Artifact summariser and context pruning — V7 §5.6.

Contains ArtifactSummariser (truncation heuristic) and ContextPruner
(advisory context budget check).

I2 Resolution (Wave 3): Truncation stub (first N characters).
    LLM-powered version deferred to later wave.

I3 Resolution (Wave 3): Advisory check — logs warning, doesn't
    prevent execution. Full budget enforcement deferred.

See V7 §5.6 for full specification.
"""

from __future__ import annotations

from typing import Any

from harness.tracing import TraceLogger

logger = TraceLogger("harness.phase.pruning")


class ArtifactSummariser:
    """Summarises artifact content using a truncation heuristic.

    Wave 3 implementation: first N characters heuristic.
    LLM-powered version: deferred to later wave (I2 resolution).

    Usage::

        summariser = ArtifactSummariser(max_summary_chars=500)
        summary = await summariser.summarise(artifact)
    """

    def __init__(self, max_summary_chars: int = 500) -> None:
        """Initialise the ArtifactSummariser.

        Args:
            max_summary_chars: Maximum characters for the summary.
                Defaults to 500.
        """
        self._max_summary_chars = max_summary_chars

    @property
    def max_summary_chars(self) -> int:
        """Return the configured maximum summary length."""
        return self._max_summary_chars

    async def summarise(self, artifact: Any) -> str:
        """Summarise an artifact using truncation heuristic.

        Wave 3 implementation: returns the first N characters of
        the artifact content. Future waves will use LLM-powered
        summarisation.

        Args:
            artifact: An object with a `content` attribute (string).
                Compatible with harness.artifact.repository.Artifact.

        Returns:
            Summary string (first max_summary_chars characters of
            content, with "..." suffix if truncated).

        Raises:
            ValueError: If the artifact has no content attribute.
        """
        content = self._get_content(artifact)

        if not content:
            return ""

        if len(content) <= self._max_summary_chars:
            return content

        truncation_point = self._find_truncation_point(content)

        return content[:truncation_point] + "..."

    def _get_content(self, artifact: Any) -> str:
        """Extract content from an artifact object.

        Supports:
        - Objects with a `.content` attribute (Artifact dataclass)
        - Strings (treated as content directly)
        - Dictionaries with a 'content' key

        Args:
            artifact: The artifact to extract content from.

        Returns:
            The content string.

        Raises:
            ValueError: If the artifact type is unsupported.
        """
        if hasattr(artifact, "content"):
            return str(artifact.content)
        if isinstance(artifact, str):
            return artifact
        if isinstance(artifact, dict):
            return str(artifact.get("content", ""))
        raise ValueError(
            f"Cannot extract content from {type(artifact).__name__}"
        )

    def _find_truncation_point(self, content: str) -> int:
        """Find a clean truncation point within the limit.

        Attempts to break at a sentence boundary, paragraph, or
        space. Falls back to exact character limit.

        Args:
            content: The content to truncate.

        Returns:
            The character index to truncate at.
        """
        limit = self._max_summary_chars

        # Try to break at a sentence boundary (period + space or end)
        for sep in ("\n\n", "\n", ". ", "! ", "? "):
            idx = content.rfind(sep, 0, limit)
            if idx > limit * 0.6:  # At least 60% of limit
                return idx + len(sep)

        # Fall back to word boundary
        idx = content.rfind(" ", 0, limit)
        if idx > limit * 0.5:  # At least 50% of limit
            return idx

        return limit


class ContextPruner:
    """Advisory context pruning using ArtifactSummariser.

    I3 Resolution: Checks context budget and logs warnings when
    exceeded. Does NOT prevent execution in Wave 3.

    Usage::

        pruner = ContextPruner(summariser=ArtifactSummariser())
        context = await pruner.prune(context, budget=16_000)
    """

    MAX_PROMPT_CHARS: int = 16_000

    def __init__(
        self,
        summariser: ArtifactSummariser | None = None,
    ) -> None:
        """Initialise the ContextPruner.

        Args:
            summariser: ArtifactSummariser instance. Created with
                defaults if not provided.
        """
        self._summariser = summariser or ArtifactSummariser()

    async def prune(
        self,
        context: str,
        budget: int | None = None,
    ) -> str:
        """Prune context to stay within budget.

        Wave 3: Advisory only — logs a warning if context exceeds
        the budget, but returns the context unchanged.

        Args:
            context: The context string to check.
            budget: Maximum allowed characters. Defaults to
                MAX_PROMPT_CHARS (16000).

        Returns:
            The context string (unchanged in Wave 3 — advisory only).
        """
        budget = budget or self.MAX_PROMPT_CHARS
        current_length = len(context)

        if current_length <= budget:
            return context

        logger.warning(
            "ContextPruner — context exceeds budget (advisory)",
            extra={
                "current_chars": current_length,
                "budget": budget,
                "over_by": current_length - budget,
            },
        )

        # Wave 3: advisory only — no truncation
        return context

    async def prune_artifacts(
        self,
        artifacts: list[Any],
        budget: int = 10_000,
    ) -> list[tuple[Any, str]]:
        """Summarise artifacts to reduce context size.

        Replaces full artifact content with summaries to stay
        within budget.

        Args:
            artifacts: List of artifacts to summarise.
            budget: Total character budget for all summaries.

        Returns:
            List of (artifact, summary) tuples.
        """
        results: list[tuple[Any, str]] = []
        remaining_budget = budget

        for artifact in artifacts:
            summary = await self._summariser.summarise(artifact)
            if len(summary) > remaining_budget:
                # Truncate summary to fit budget
                summary = summary[:max(0, remaining_budget - 3)] + "..."
            results.append((artifact, summary))
            remaining_budget -= len(summary)

        logger.info(
            "ContextPruner — artefacts summarised",
            extra={
                "artifacts": len(artifacts),
                "used_budget": budget - remaining_budget,
                "budget": budget,
            },
        )

        return results


class PromptContextBudget:
    """Advisory context budget check — V7 §5.6, I3 resolution.

    Checks prompt length against a configurable threshold and logs a
    warning if the budget is exceeded. Does NOT prevent execution.

    I3 Resolution (Wave 3 — ContextPruner, Wave 6 — PromptContextBudget):
    Advisory only — logs a warning if the prompt exceeds the budget.
    Full budget enforcement deferred.

    Usage::

        over = PromptContextBudget.check("some long prompt text...")
        if over:
            logger.warning("Prompt exceeds budget")
    """

    MAX_PROMPT_CHARS: int = 16_000
    """Advisory threshold for prompt length. Default 16,000 characters."""

    @staticmethod
    def check(prompt: str) -> bool:
        """Check if a prompt exceeds the context budget.

        Logs a warning if the prompt is over the budget. Does NOT
        prevent execution (advisory only in Wave 6).

        Args:
            prompt: The prompt string to check.

        Returns:
            True if the prompt exceeds the budget (over threshold),
            False if within budget.
        """
        # Import here to avoid circular imports at module level
        from harness.tracing import TraceLogger

        logger = TraceLogger("harness.phase.pruning.budget")

        current_length = len(prompt)
        budget = PromptContextBudget.MAX_PROMPT_CHARS

        if current_length <= budget:
            return False

        logger.warning(
            "PromptContextBudget — prompt exceeds advisory budget",
            extra={
                "current_chars": current_length,
                "budget": budget,
                "over_by": current_length - budget,
            },
        )

        return True
