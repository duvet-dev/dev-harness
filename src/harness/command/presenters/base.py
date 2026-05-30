"""CliPresenter — Click-formatted output for all typed command results.

Pattern-matches on result type and formats for CLI display.
"""

from __future__ import annotations

from harness.command.results.engagement import (
    AbortEngagementResult,
    CreateEngagementResult,
    ResumeEngagementResult,
)
from harness.command.results.phase import EnterPhaseResult, ManagePhaseResult
from harness.command.results.project import InitProjectResult
from harness.command.results.misc import (
    NextResult,
    QueryStatusResult,
    QueryWhatsNextResult,
)
from harness.command.results.review import (
    FinishEngagementResult,
    ReviewEngagementResult,
)
from harness.command.results.session import ChatResult, SessionResult
from harness.command.results.wave import (
    CreateWaveResult,
    ExecuteStepResult,
    RunWaveResult,
)
from harness.command.results.analysis import (
    AssessResult,
    InspectResult,
    SummaryResult,
)
from harness.command.results.batch import (
    AnnotateChangelogResult,
    CreateWaveFromFindingResult,
    CreateWavesFromAssessmentResult,
    GenerateDocsResult,
    ListWavesResult,
    WaveStatusResult,
)
from harness.command.results.mgmt import (
    AgentListResult,
    ConsultResult,
    FixEngagementResult,
    FleetListResult,
    RefreshAgentsResult,
    RenameEngagementResult,
    SetBranchResult,
    SetGovernanceResult,
)
from harness.command.types import CommandResult, TypedResult


class CliPresenter:
    """Presenter for Click CLI output.

    Formats typed results for display. Handles both TypedResult and
    CommandResult (legacy wrapped).
    """

    def present(self, result: CommandResult | TypedResult) -> str:
        """Format a result for CLI display."""
        # Unwrap if wrapped in CommandResult
        if isinstance(result, CommandResult):
            typed = result.data.get("typed_result") if result.data else None
            if typed is not None:
                result = typed
            else:
                # Legacy CommandResult — just show message
                if result.success:
                    return result.message
                return f"Error: {result.error or result.message}"

        return self._format_typed(result)

    def _format_typed(self, result: TypedResult) -> str:
        """Dispatch to type-specific formatting."""
        if isinstance(result, CreateEngagementResult):
            return self._format_create_engagement(result)
        if isinstance(result, EnterPhaseResult):
            return self._format_enter_phase(result)
        if result.success:
            return result.message
        return f"Error: {result.error or result.message}"

    def _format_create_engagement(self, result: CreateEngagementResult) -> str:
        lines = [result.message]
        lines.append(f"  Slug  : {result.slug}")
        lines.append(f"  Status: {result.status}")
        if result.current_phase:
            lines.append(f"  Phase : {result.current_phase}")
        if result.target_branch:
            lines.append(f"  Branch: {result.target_branch}")
        for w in result.warnings:
            lines.append(f"  \u26a0 {w.get('message', w)}")
        return "\n".join(lines)

    def _format_enter_phase(self, result: EnterPhaseResult) -> str:
        if result.success:
            return result.message
        return f"Error: {result.error}"


class ReplPresenter:
    """Presenter for REPL output (plain/ANSI text, no Click formatting)."""

    def present(self, result: CommandResult | TypedResult) -> str:
        """Format a result for REPL display."""
        if isinstance(result, CommandResult):
            typed = result.data.get("typed_result") if result.data else None
            if typed is not None:
                result = typed
            else:
                if result.success:
                    return f"\u2705 {result.message}"
                return f"\u274c {result.error or result.message}"

        return self._format_typed(result)

    def _format_typed(self, result: TypedResult) -> str:
        if result.success:
            return f"\u2705 {result.message}"
        return f"\u274c {result.error or result.message}"
