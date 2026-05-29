"""Lead aggregator — safety-first aggregation protocol — V7 §5.7.

Aggregates the results of parallel agent dispatch. Safety-first
principle: any critic flagging an issue = issue. Dissenting notes
are attached to the aggregate result.

If the aggregator itself fails (technical error), auto mode is broken
and reported to the user. See V7 §5.7 and §5.8 (escalation chain).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.artifact.repository import Artifact
from harness.errors import AggregatorError
from harness.phase.dispatch_utility import (
    DispatchResult,
    ParallelDispatchResult,
)
from harness.tracing import TraceLogger

logger = TraceLogger("harness.phase.aggregator")


@dataclass
class AggregateResult:
    """Result of aggregating parallel dispatch outputs.

    Attributes:
        success: True if aggregation passed (no critical dissents).
        artifacts: List of aggregated artifacts.
        error: Error message if aggregation failed technically.
        dissenting_notes: List of dissenting/critical outputs from
            critics. Safety-first: any critic flagging = issue.
    """

    success: bool
    artifacts: list[Artifact] = field(default_factory=list)
    error: str | None = None
    dissenting_notes: list[str] = field(default_factory=list)


# Keywords/phrases that indicate a critic is flagging an issue.
# Safety-first: any match = issue attached.
CRITIC_FLAG_PHRASES = [
    "issue",
    "concern",
    "problem",
    "warning",
    "blocker",
    "critical",
    "violation",
    "not safe",
    "must fix",
    "should not",
    "fails",
    "incorrect",
    "vulnerability",
    "risk",
    "unacceptable",
    "reject",
    "rejected",
    "fails to meet",
    "non-compliant",
    "error",
    "bug",
    "regression",
]


class LeadAggregator:
    """Safety-first aggregation of parallel agent outputs.

    Collects all agent outputs and applies lead judgement. If any
    critic flags an issue, it's treated as an issue with dissenting
    notes attached.

    Usage::

        aggregator = LeadAggregator()
        result = await aggregator.aggregate(
            results=parallel_result,
            step=step,
        )
        if result.dissenting_notes:
            # Handle flagged issues
            ...
    """

    def __init__(
        self,
        flag_phrases: list[str] | None = None,
    ) -> None:
        """Initialise the LeadAggregator.

        Args:
            flag_phrases: Custom list of flag phrases. Defaults to
                CRITIC_FLAG_PHRASES.
        """
        self._flag_phrases = flag_phrases or CRITIC_FLAG_PHRASES

    async def aggregate(
        self,
        results: ParallelDispatchResult,
        step: Any | None = None,
    ) -> AggregateResult:
        """Aggregate parallel dispatch results.

        Safety-first: any critic flagging an issue = issue with
        dissenting notes. If the aggregator itself encounters a
        technical error, it raises AggregatorError to break auto
        mode.

        Args:
            results: The ParallelDispatchResult to aggregate.
            step: Optional step context for the aggregation.

        Returns:
            AggregateResult with success status, artifacts, and
            dissenting notes.

        Raises:
            AggregatorError: If a technical error prevents
                aggregation (triggers auto mode break per V7 §5.7).
        """
        try:
            return self._do_aggregate(results, step)
        except AggregatorError:
            raise
        except Exception as e:
            logger.error(
                "LeadAggregator.aggregate — technical failure",
                extra={"error": str(e)},
            )
            raise AggregatorError(
                f"LeadAggregator technical failure: {e}"
            ) from e

    def _do_aggregate(
        self,
        results: ParallelDispatchResult,
        step: Any | None,
    ) -> AggregateResult:
        """Internal aggregation logic."""
        dissenting_notes: list[str] = []
        artifacts: list[Artifact] = []

        for result in results.completed:
            output = result.output or ""
            artifacts.append(
                Artifact(
                    type=self._infer_type(result),
                    content=output,
                    summary=self._make_summary(output),
                    path=f"step_{result.agent_name}.md",
                )
            )

            if self._is_dissenting(output, result.agent_name):
                dissenting_notes.append(
                    f"[{result.agent_name}] flagged: {output[:200]}"
                )

        for result in results.failed:
            error = result.error or "unknown error"
            dissenting_notes.append(
                f"[{result.agent_name}] failed: {error}"
            )

        for agent in results.timed_out:
            dissenting_notes.append(
                f"[{agent}] timed out"
            )

        success = len(dissenting_notes) == 0

        logger.info(
            "LeadAggregator.aggregate",
            extra={
                "success": success,
                "dissenting_notes": len(dissenting_notes),
                "artifacts": len(artifacts),
            },
        )

        return AggregateResult(
            success=success,
            artifacts=artifacts,
            dissenting_notes=dissenting_notes if dissenting_notes else None,
        )

    def _is_dissenting(self, output: str, agent_name: str) -> bool:
        """Check if an agent's output contains critic flags.

        Uses word-boundary matching to avoid false positives where a
        flag phrase appears as a substring of a non-flag word
        (e.g. "concern" should not match "concerns" or
        "separation of concerns" in general discussion).
        """
        lower_output = output.lower()
        for phrase in self._flag_phrases:
            if phrase in lower_output:
                # Word boundary check: ensure the phrase appears as
                # a standalone word or at word boundaries
                idx = lower_output.find(phrase)
                while idx != -1:
                    before = idx == 0 or not lower_output[idx - 1].isalnum()
                    after = (idx + len(phrase) >= len(lower_output)
                             or not lower_output[idx + len(phrase)].isalnum())
                    if before and after:
                        logger.debug(
                            "LeadAggregator — dissenting flag",
                            extra={
                                "agent": agent_name,
                                "matched_phrase": phrase,
                            },
                        )
                        return True
                    idx = lower_output.find(phrase, idx + 1)
        return False

    def _make_summary(self, content: str, max_chars: int = 100) -> str:
        """Produce a summary stub for an artifact.

        Wave 3 will use ArtifactSummariser truncation heuristic.
        This is a simple first-N-chars stub (D28).
        """
        if not content:
            return ""
        if len(content) <= max_chars:
            return content
        return content[:max_chars] + "..."

    def _infer_type(self, result: DispatchResult) -> Any:
        """Infer artifact type from agent name.

        Maps agent names to likely ArtifactType values for
        sensible defaults.
        """
        from harness.artifact.types import ArtifactType

        name_lower = result.agent_name.lower()
        type_map: dict[str, ArtifactType] = {
            "architect": ArtifactType.ARCHITECTURAL_OVERVIEW,
            "architecture-critic": ArtifactType.CONSOLIDATED_REVIEW,
            "coding-agent": ArtifactType.IMPLEMENTATION,
            "testing-agent": ArtifactType.TEST_RESULTS,
            "review": ArtifactType.REVIEW_REPORT,
            "security": ArtifactType.SECURITY_REPORT,
            "validation": ArtifactType.VALIDATION_REPORT,
            "planning": ArtifactType.PLAN,
            "discovery": ArtifactType.PLANNING_DOC,
        }

        for key, artifact_type in type_map.items():
            if key in name_lower:
                return artifact_type

        return ArtifactType.SUMMARY
