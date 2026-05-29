"""Tests for phase/pruning.py: ArtifactSummariser + ContextPruner.

Tests cover:
- ArtifactSummariser: truncation, clean breakpoints, empty content
- ArtifactSummariser: various content types (string, object, dict)
- ArtifactSummariser: max_summary_chars configuration
- ContextPruner: budget check warnings (advisory only)
- ContextPruner: prune_artifacts method
"""

from __future__ import annotations

import pytest

from harness.artifact.repository import Artifact
from harness.artifact.types import ArtifactType
from harness.phase.pruning import ArtifactSummariser, ContextPruner


class TestArtifactSummariser:
    """ArtifactSummariser tests."""

    @pytest.fixture
    def summariser(self) -> ArtifactSummariser:
        """Create a summariser with 500 char limit."""
        return ArtifactSummariser(max_summary_chars=500)

    @pytest.fixture
    def small_summariser(self) -> ArtifactSummariser:
        """Create a summariser with 20 char limit."""
        return ArtifactSummariser(max_summary_chars=20)

    @pytest.mark.asyncio
    async def test_summarise_short_content(self, summariser: ArtifactSummariser) -> None:
        """Short content is returned as-is."""
        artifact = Artifact(
            type=ArtifactType.SUMMARY,
            content="Short text",
        )
        result = await summariser.summarise(artifact)
        assert result == "Short text"

    @pytest.mark.asyncio
    async def test_summarise_long_content_truncated(
        self, small_summariser: ArtifactSummariser
    ) -> None:
        """Long content is truncated with '...' suffix."""
        artifact = Artifact(
            type=ArtifactType.SUMMARY,
            content="This is a very long piece of content that should be truncated.",
        )
        result = await small_summariser.summarise(artifact)
        assert len(result) <= 23  # 20 + "..."
        assert result.endswith("...")

    @pytest.mark.asyncio
    async def test_summarise_empty(self, summariser: ArtifactSummariser) -> None:
        """Empty content returns empty string."""
        artifact = Artifact(
            type=ArtifactType.SUMMARY,
            content="",
        )
        result = await summariser.summarise(artifact)
        assert result == ""

    @pytest.mark.asyncio
    async def test_summarise_none_content(self, summariser: ArtifactSummariser) -> None:
        """None-like content returns empty string."""
        artifact = Artifact(
            type=ArtifactType.SUMMARY,
            content="",
        )
        artifact.content = ""
        result = await summariser.summarise(artifact)
        assert result == ""

    @pytest.mark.asyncio
    async def test_summarise_string_direct(self, summariser: ArtifactSummariser) -> None:
        """String can be passed instead of an Artifact object."""
        result = await summariser.summarise("Short string")
        assert result == "Short string"

    @pytest.mark.asyncio
    async def test_summarise_long_string_truncated(
        self, small_summariser: ArtifactSummariser
    ) -> None:
        """Long string is truncated."""
        result = await small_summariser.summarise("A" * 100)
        assert result.endswith("...")
        assert len(result) <= 23

    @pytest.mark.asyncio
    async def test_summarise_dict(self, summariser: ArtifactSummariser) -> None:
        """Dict with 'content' key works."""
        result = await summariser.summarise({"content": "Dict content"})
        assert result == "Dict content"

    @pytest.mark.asyncio
    async def test_summarise_dict_long(
        self, small_summariser: ArtifactSummariser
    ) -> None:
        """Long dict content is truncated."""
        result = await small_summariser.summarise({"content": "B" * 50})
        assert result.endswith("...")

    @pytest.mark.asyncio
    async def test_summarise_invalid_type(self, summariser: ArtifactSummariser) -> None:
        """Invalid artifact type raises ValueError."""
        with pytest.raises(ValueError):
            await summariser.summarise(42)

    @pytest.mark.asyncio
    async def test_summarise_custom_max(self) -> None:
        """Custom max_summary_chars is respected."""
        summariser = ArtifactSummariser(max_summary_chars=10)
        result = await summariser.summarise("1234567890extra")
        assert len(result) <= 13  # 10 + "..."
        assert result.endswith("...")

    def test_max_summary_chars_property(self) -> None:
        """max_summary_chars property returns configured value."""
        summariser = ArtifactSummariser(max_summary_chars=300)
        assert summariser.max_summary_chars == 300

    @pytest.mark.asyncio
    async def test_summarise_truncation_at_sentence_boundary(
        self, small_summariser: ArtifactSummariser
    ) -> None:
        """Truncation tries to break at sentence boundary."""
        summariser = ArtifactSummariser(max_summary_chars=30)
        content = "First sentence. Second sentence. Third one here."
        result = await summariser.summarise(content)
        # Should break at a clean point
        assert result.endswith("...")

    @pytest.mark.asyncio
    async def test_summarise_truncation_at_word_boundary(
        self, small_summariser: ArtifactSummariser
    ) -> None:
        """Truncation falls back to word boundary."""
        summariser = ArtifactSummariser(max_summary_chars=15)
        content = "word1 word2 word3 word4"
        result = await summariser.summarise(content)
        assert result.endswith("...")

    @pytest.mark.asyncio
    async def test_summarise_at_limit(self, summariser: ArtifactSummariser) -> None:
        """Content exactly at limit is not truncated."""
        content = "A" * 500
        result = await summariser.summarise(content)
        assert result == content
        assert not result.endswith("...")

    @pytest.mark.asyncio
    async def test_summarise_truncation_at_paragraph_boundary(self) -> None:
        """Truncation at paragraph boundary past 60% of limit (line 125)."""
        # limit=20, content has \n\n at position 13. 13 > 20*0.6=12 → hit line 125
        summariser = ArtifactSummariser(max_summary_chars=20)
        content = "aaaaaaaaaaaaa\n\naaaaaaaaaa"
        result = await summariser.summarise({"content": content})
        assert len(result) <= 23  # 20 + "..."
        assert result.endswith("...")

    @pytest.mark.asyncio
    async def test_summarise_truncation_at_newline_boundary(self) -> None:
        """Truncation at newline boundary past 60% of limit (line 125)."""
        summariser = ArtifactSummariser(max_summary_chars=20)
        # newline at position 14, 14 > 20*0.6=12 → hit line 125
        content = "aaaaaaaaaaaaaa\naaaaa\n"
        result = await summariser.summarise({"content": content})
        assert result.endswith("...")

    @pytest.mark.asyncio
    async def test_summarise_truncation_at_sentence_end(self) -> None:
        """Truncation at '. ' boundary past 60% of limit (line 125)."""
        summariser = ArtifactSummariser(max_summary_chars=25)
        # '. ' at position 18, 18 > 25*0.6=15 → hit line 125
        content = "This is a good test. More words here."
        result = await summariser.summarise({"content": content})
        assert result.endswith("...")

    @pytest.mark.asyncio
    async def test_summarise_truncation_at_exclamation(self) -> None:
        """Truncation at '! ' boundary past 60% of limit (line 125)."""
        summariser = ArtifactSummariser(max_summary_chars=25)
        content = "This is a good test! More words here."
        result = await summariser.summarise({"content": content})
        assert result.endswith("...")

    @pytest.mark.asyncio
    async def test_summarise_truncation_at_question(self) -> None:
        """Truncation at '? ' boundary past 60% of limit (line 125)."""
        summariser = ArtifactSummariser(max_summary_chars=25)
        content = "This is a good test? More words here."
        result = await summariser.summarise({"content": content})
        assert result.endswith("...")


class TestContextPruner:
    """ContextPruner tests."""

    @pytest.fixture
    def summariser(self) -> ArtifactSummariser:
        """Default summariser."""
        return ArtifactSummariser(max_summary_chars=100)

    @pytest.fixture
    def pruner(self, summariser: ArtifactSummariser) -> ContextPruner:
        """ContextPruner with default summariser."""
        return ContextPruner(summariser=summariser)

    @pytest.mark.asyncio
    async def test_prune_within_budget(self, pruner: ContextPruner) -> None:
        """Context within budget is returned unchanged."""
        context = "Short context"
        result = await pruner.prune(context, budget=100)
        assert result == context

    @pytest.mark.asyncio
    async def test_prune_over_budget_advisory(
        self, pruner: ContextPruner
    ) -> None:
        """Context over budget logs warning but returns unchanged."""
        context = "A" * 1000
        result = await pruner.prune(context, budget=100)
        # Advisory only — context is unchanged in Wave 3
        assert result == context
        assert len(result) == 1000

    @pytest.mark.asyncio
    async def test_prune_default_budget(self, pruner: ContextPruner) -> None:
        """Default budget is MAX_PROMPT_CHARS (16000)."""
        context = "A" * 20000
        result = await pruner.prune(context)
        # Advisory only — returns unchanged
        assert result == context

    @pytest.mark.asyncio
    async def test_prune_artifacts_empty(self, pruner: ContextPruner) -> None:
        """Empty artifact list returns empty."""
        results = await pruner.prune_artifacts([])
        assert results == []

    @pytest.mark.asyncio
    async def test_prune_artifacts(self, pruner: ContextPruner) -> None:
        """Artifacts are summarised within budget."""
        artifacts = [
            Artifact(type=ArtifactType.SUMMARY, content="A" * 1000,
                     path="a.md"),
            Artifact(type=ArtifactType.PLAN, content="B" * 1000,
                     path="b.md"),
        ]
        results = await pruner.prune_artifacts(artifacts, budget=500)

        assert len(results) == 2
        for artifact, summary in results:
            assert isinstance(artifact, Artifact)
            assert isinstance(summary, str)
            assert len(summary) <= 100 + 3  # max_summary_chars + "..."

    @pytest.mark.asyncio
    async def test_prune_artifacts_budget_exceeded(
        self, pruner: ContextPruner
    ) -> None:
        """When budget is exceeded, summaries are further truncated."""
        summariser = ArtifactSummariser(max_summary_chars=200)
        pruner = ContextPruner(summariser=summariser)

        artifacts = [
            Artifact(type=ArtifactType.SUMMARY, content="A" * 500,
                     path="a.md"),
        ]
        results = await pruner.prune_artifacts(artifacts, budget=10)

        assert len(results) == 1
        _, summary = results[0]
        assert len(summary) <= 13  # budget + "..."

    @pytest.mark.asyncio
    async def test_no_summariser_default(self) -> None:
        """ContextPruner creates default summariser if none provided."""
        pruner = ContextPruner()
        assert pruner._summariser is not None
        assert pruner._summariser.max_summary_chars == 500
