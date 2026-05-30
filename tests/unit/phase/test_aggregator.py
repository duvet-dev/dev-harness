"""Tests for phase/aggregator.py: LeadAggregator.

Tests cover safety-first aggregation, critic flag detection,
dissenting notes, technical failure handling, and artifact
type inference.
"""

from __future__ import annotations

import pytest

from harness.artifact.types import ArtifactType
from harness.errors import AggregatorError
from harness.phase.aggregator import (
    CRITIC_FLAG_PHRASES,
    LeadAggregator,
)
from harness.phase.dispatch_utility import (
    DispatchResult,
    ParallelDispatchResult,
)


class TestLeadAggregator:
    """LeadAggregator tests."""

    def test_all_clean(self) -> None:
        """All agents succeed without flagging issues."""
        aggregator = LeadAggregator()
        results = ParallelDispatchResult(
            completed=[
                DispatchResult(
                    agent_name="architect",
                    success=True,
                    output="Design looks solid. Good separation of concerns.",
                ),
                DispatchResult(
                    agent_name="tester",
                    success=True,
                    output="Tests all pass. Coverage is adequate.",
                ),
            ],
        )

        aggregated = aggregator._do_aggregate(results, step=None)
        assert aggregated.success is True
        assert len(aggregated.artifacts) == 2
        assert aggregated.dissenting_notes is None
        assert aggregated.error is None

    def test_critic_flags_issue(self) -> None:
        """Safety-first: any critic flagging = issue."""
        aggregator = LeadAggregator()
        results = ParallelDispatchResult(
            completed=[
                DispatchResult(
                    agent_name="architect",
                    success=True,
                    output="Design looks good.",
                ),
                DispatchResult(
                    agent_name="architecture-critic",
                    success=True,
                    output="CRITICAL ISSUE: The caching layer "
                    "violates SOLID principles.",
                ),
            ],
        )

        aggregated = aggregator._do_aggregate(results, step=None)
        assert aggregated.success is False
        assert aggregated.dissenting_notes is not None
        assert len(aggregated.dissenting_notes) == 1
        assert "architecture-critic" in aggregated.dissenting_notes[0]
        assert "CRITICAL ISSUE" in aggregated.dissenting_notes[0]

    def test_multiple_dissents(self) -> None:
        """Multiple critics flagging = multiple dissenting notes."""
        aggregator = LeadAggregator()
        results = ParallelDispatchResult(
            completed=[
                DispatchResult(
                    agent_name="security-critic",
                    success=True,
                    output="Security concern: no input validation.",
                ),
                DispatchResult(
                    agent_name="code-critic",
                    success=True,
                    output="Bug found in error handling path.",
                ),
            ],
        )

        aggregated = aggregator._do_aggregate(results, step=None)
        assert aggregated.success is False
        assert aggregated.dissenting_notes is not None
        assert len(aggregated.dissenting_notes) == 2

    def test_failed_agents_are_dissents(self) -> None:
        """Failed agents should appear as dissenting notes."""
        aggregator = LeadAggregator()
        results = ParallelDispatchResult(
            completed=[
                DispatchResult(
                    agent_name="architect",
                    success=True,
                    output="All good.",
                ),
            ],
            failed=[
                DispatchResult(
                    agent_name="tester",
                    success=False,
                    error="Test runner crashed",
                ),
            ],
        )

        aggregated = aggregator._do_aggregate(results, step=None)
        assert aggregated.success is False
        assert aggregated.dissenting_notes is not None
        assert len(aggregated.dissenting_notes) == 1
        assert "tester" in aggregated.dissenting_notes[0]
        assert "Test runner crashed" in aggregated.dissenting_notes[0]

    def test_timed_out_agents_are_dissents(self) -> None:
        """Timed-out agents should appear as dissenting notes."""
        aggregator = LeadAggregator()
        results = ParallelDispatchResult(
            completed=[
                DispatchResult(
                    agent_name="architect",
                    success=True,
                    output="All good.",
                ),
            ],
            timed_out=["slow-agent"],
        )

        aggregated = aggregator._do_aggregate(results, step=None)
        assert aggregated.success is False
        assert aggregated.dissenting_notes is not None
        assert len(aggregated.dissenting_notes) == 1
        assert "slow-agent" in aggregated.dissenting_notes[0]
        assert "timed out" in aggregated.dissenting_notes[0]

    def test_all_failed_no_completed(self) -> None:
        """All agents fail — no partial flag, all dissents."""
        aggregator = LeadAggregator()
        results = ParallelDispatchResult(
            failed=[
                DispatchResult(
                    agent_name="a",
                    success=False,
                    error="Error A",
                ),
                DispatchResult(
                    agent_name="b",
                    success=False,
                    error="Error B",
                ),
            ],
        )

        aggregated = aggregator._do_aggregate(results, step=None)
        assert aggregated.success is False
        assert len(aggregated.dissenting_notes) == 2
        assert len(aggregated.artifacts) == 0

    def test_empty_results(self) -> None:
        """Empty result set."""
        aggregator = LeadAggregator()
        results = ParallelDispatchResult()

        aggregated = aggregator._do_aggregate(results, step=None)
        assert aggregated.success is True
        assert aggregated.artifacts == []
        assert aggregated.dissenting_notes is None

    def test_flag_phrases_detection(self) -> None:
        """Various critic flag phrases should be detected."""
        aggregator = LeadAggregator()

        test_cases = [
            ("This is an issue", True),
            ("Major concern here", True),
            ("security vulnerability found", True),
            ("Everything looks great", False),
            ("Reject this approach", True),
            ("This implementation is unacceptable", True),
            ("Minor suggestion", False),
            ("Potential risk in error handling", True),
        ]

        for output, should_flag in test_cases:
            result = aggregator._is_dissenting(output, "critic")
            assert result is should_flag, (
                f"Expected flag={should_flag} for: {output}"
            )

    def test_custom_flag_phrases(self) -> None:
        """Custom flag phrases should override defaults."""
        aggregator = LeadAggregator(flag_phrases=["my-custom-flag"])

        assert aggregator._is_dissenting("has my-custom-flag word", "a")
        assert not aggregator._is_dissenting("regular output", "a")

    def test_artifact_type_inference(self) -> None:
        """Agent names should map to appropriate artifact types."""
        aggregator = LeadAggregator()
        results = ParallelDispatchResult(
            completed=[
                DispatchResult(
                    agent_name="architect",
                    success=True,
                    output="Design doc",
                ),
                DispatchResult(
                    agent_name="testing-agent",
                    success=True,
                    output="Test report",
                ),
                DispatchResult(
                    agent_name="security-critic",
                    success=True,
                    output="Security review",
                ),
            ],
        )

        aggregated = aggregator._do_aggregate(results, step=None)
        assert len(aggregated.artifacts) == 3

        types = [a.type for a in aggregated.artifacts]
        assert ArtifactType.ARCHITECTURAL_OVERVIEW in types
        assert ArtifactType.TEST_RESULTS in types
        assert ArtifactType.SECURITY_REPORT in types

    def test_summary_stub(self) -> None:
        """Summary should truncate at max_chars."""
        aggregator = LeadAggregator()
        summary = aggregator._make_summary("A" * 1000, max_chars=50)
        assert len(summary) == 53  # 50 chars + "..."
        assert summary.endswith("...")

    def test_summary_short(self) -> None:
        """Short content should not be truncated."""
        aggregator = LeadAggregator()
        summary = aggregator._make_summary("Hello", max_chars=100)
        assert summary == "Hello"

    def test_summary_empty(self) -> None:
        """Empty content should return empty string."""
        aggregator = LeadAggregator()
        assert aggregator._make_summary("") == ""

    @pytest.mark.asyncio
    async def test_aggregate_technical_failure(self) -> None:
        """AggregatorError should be raised on technical failure."""
        class BrokenAggregator(LeadAggregator):
            def _do_aggregate(self, results, step=None):
                raise ValueError("Database connection lost")

        aggregator = BrokenAggregator()
        results = ParallelDispatchResult(
            completed=[DispatchResult("a", True, output="ok")],
        )

        with pytest.raises(AggregatorError) as exc:
            await aggregator.aggregate(results)
        assert "Database connection lost" in str(exc.value)

    @pytest.mark.asyncio
    async def test_aggregator_error_re_raised(self) -> None:
        """AggregatorError is re-raised directly (line 131)."""
        class RaisesAggregatorError(LeadAggregator):
            def _do_aggregate(self, results, step=None):
                raise AggregatorError("Already an aggregator error")

        aggregator = RaisesAggregatorError()
        results = ParallelDispatchResult(
            completed=[DispatchResult("a", True, output="ok")],
        )

        with pytest.raises(AggregatorError) as exc:
            await aggregator.aggregate(results)
        assert "Already an aggregator error" in str(exc.value)

    @pytest.mark.asyncio
    async def test_critique_phrases_list(self) -> None:
        """Ensure CRITIC_FLAG_PHRASES is reasonably comprehensive."""
        assert len(CRITIC_FLAG_PHRASES) >= 15
        essential = ["issue", "concern", "warning", "blocker",
                     "critical", "error", "bug"]
        for phrase in essential:
            assert phrase in CRITIC_FLAG_PHRASES, (
                f"Missing essential flag phrase: {phrase}"
            )
