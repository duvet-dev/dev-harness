"""CliPresenter and ReplPresenter — output formatting for command results.

Pattern-matches on result type and formats for CLI (Click) or REPL (ANSI) display.
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
    TeamListResult,
    RefreshAgentsResult,
    RenameEngagementResult,
    SetBranchResult,
    SetGovernanceResult,
)
from harness.command.types import CommandResult, TypedResult


class CliPresenter:
    """Presenter for Click CLI output.

    Formats typed results for display using Click-friendly styled output.
    Handles both TypedResult and CommandResult (legacy wrapped).
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
        if not result.success:
            return f"Error: {result.error or result.message}"

        # Engagement lifecycle
        if isinstance(result, CreateEngagementResult):
            return self._format_create_engagement(result)
        if isinstance(result, ResumeEngagementResult):
            return self._format_simple(result, "Engagement resumed")
        if isinstance(result, AbortEngagementResult):
            return self._format_abort_engagement(result)
        # Phase
        if isinstance(result, EnterPhaseResult):
            return self._format_enter_phase(result)
        if isinstance(result, ManagePhaseResult):
            return self._format_manage_phase(result)
        # Project
        if isinstance(result, InitProjectResult):
            return self._format_init_project(result)
        # Session / Chat
        if isinstance(result, SessionResult):
            return self._format_session(result)
        if isinstance(result, ChatResult):
            return self._format_simple(result, "Chat opened")
        # Review
        if isinstance(result, ReviewEngagementResult):
            return self._format_review(result)
        if isinstance(result, FinishEngagementResult):
            return self._format_finish(result)
        # Wave
        if isinstance(result, CreateWaveResult):
            return self._format_simple(result, f"Wave created: {result.wave_title}")
        if isinstance(result, RunWaveResult):
            return self._format_run_wave(result)
        if isinstance(result, ExecuteStepResult):
            return self._format_simple(result, "Step executed")
        # Misc
        if isinstance(result, NextResult):
            return self._format_simple(result, "Advanced")
        if isinstance(result, QueryStatusResult):
            return self._format_query_status(result)
        if isinstance(result, QueryWhatsNextResult):
            return self._format_query_whats_next(result)
        # Analysis
        if isinstance(result, SummaryResult):
            return result.report or result.message
        if isinstance(result, InspectResult):
            return result.report or result.message
        if isinstance(result, AssessResult):
            return result.report or result.message
        # Batch
        if isinstance(result, CreateWavesFromAssessmentResult):
            return f"Created {result.created} waves from assessment"
        if isinstance(result, CreateWaveFromFindingResult):
            return self._format_create_wave_from_finding(result)
        if isinstance(result, ListWavesResult):
            return self._format_list_waves(result)
        if isinstance(result, WaveStatusResult):
            return result.summary or result.message
        if isinstance(result, GenerateDocsResult):
            return self._format_generate_docs(result)
        if isinstance(result, AnnotateChangelogResult):
            return f"Annotation added: {result.path}"
        # Mgmt
        if isinstance(result, RenameEngagementResult):
            return self._format_rename(result)
        if isinstance(result, SetBranchResult):
            return f"Branch updated: {result.old_branch} -> {result.new_branch}"
        if isinstance(result, FixEngagementResult):
            return self._format_fix(result)
        if isinstance(result, RefreshAgentsResult):
            return self._format_refresh_agents(result)
        if isinstance(result, SetGovernanceResult):
            return f"Governance set to '{result.level}' on {result.scope}"
        if isinstance(result, AgentListResult):
            return self._format_agent_list(result)
        if isinstance(result, TeamListResult):
            return self._format_team_list(result)
        if isinstance(result, ConsultResult):
            return self._format_consult(result)

        return result.message

    # ── Type-specific formatters ─────────────────────────────────────────

    def _format_simple(self, result: TypedResult, fallback: str) -> str:
        return result.message or fallback

    def _format_create_engagement(self, result: CreateEngagementResult) -> str:
        lines = [result.message]
        lines.append(f"  Slug:   {result.slug}")
        lines.append(f"  Status: {result.status}")
        if result.current_phase:
            lines.append(f"  Phase:  {result.current_phase}")
        if result.target_branch:
            lines.append(f"  Branch: {result.target_branch}")
        for w in result.warnings:
            lines.append(f"  \u26a0 {w.get('message', w)}")
        return "\n".join(lines)

    def _format_abort_engagement(self, result: AbortEngagementResult) -> str:
        lines = [result.message]
        if result.previous_status:
            lines.append(f"  Previous status: {result.previous_status}")
        if result.completed_phases:
            lines.append(f"  Completed phases: {', '.join(result.completed_phases)}")
        return "\n".join(lines)

    def _format_enter_phase(self, result: EnterPhaseResult) -> str:
        if result.success:
            return result.message
        return f"Error: {result.error}"

    def _format_manage_phase(self, result: ManagePhaseResult) -> str:
        lines = [result.message]
        if result.phases:
            lines.append("  Phases:")
            for p in result.phases:
                marker = "*" if p.get("active") else " "
                lines.append(f"    {marker} {p.get('name', '?')}: {p.get('status', '?')}")
        return "\n".join(lines)

    def _format_init_project(self, result: InitProjectResult) -> str:
        lines = [result.message]
        lines.append(f"  Project:  {result.project}")
        tpl = result.template or "(none)"
        lines.append(f"  Template: {tpl}")
        lines.append(f"  Path:     {result.path}")
        if result.git_initted:
            lines.append("  Git:      initialised")
        return "\n".join(lines)

    def _format_session(self, result: SessionResult) -> str:
        lines = [result.message]
        lines.append(f"  Phase: {result.phase}")
        if result.session_type:
            lines.append(f"  Type:  {result.session_type}")
        return "\n".join(lines)

    def _format_review(self, result: ReviewEngagementResult) -> str:
        lines = [result.message]
        lines.append(f"  Decision: {result.decision}")
        return "\n".join(lines)

    def _format_finish(self, result: FinishEngagementResult) -> str:
        lines = [result.message]
        if result.head_sha:
            lines.append(f"  Commit: {result.head_sha[:8]}")
        if result.branch:
            lines.append(f"  Branch: {result.branch}")
        return "\n".join(lines)

    def _format_run_wave(self, result: RunWaveResult) -> str:
        lines = [result.message]
        if result.iteration_count:
            lines.append(f"  Iterations: {result.iteration_count}")
        return "\n".join(lines)

    def _format_query_status(self, result: QueryStatusResult) -> str:
        lines = [result.message]
        if result.warnings:
            for w in result.warnings:
                lines.append(f"  \u26a0 {w.get('message', w)}")
        return "\n".join(lines)

    def _format_query_whats_next(self, result: QueryWhatsNextResult) -> str:
        lines = [result.message]
        lines.append(f"  Status:        {result.status}")
        lines.append(f"  Current phase: {result.current_phase or '-'}")
        if result.pending_phases:
            lines.append(f"  Pending:       {', '.join(result.pending_phases)}")
        if result.completed_phases:
            lines.append(f"  Completed:     {', '.join(result.completed_phases)}")
        if result.available_commands:
            lines.append(f"  Commands:      {', '.join(result.available_commands)}")
        if result.blocked:
            lines.append(f"  \u26a0 Blocked: {result.block_reason}")
        return "\n".join(lines)

    def _format_create_wave_from_finding(self, result: CreateWaveFromFindingResult) -> str:
        lines = [result.message]
        lines.append(f"  Wave ID:  {result.wave_id}")
        if result.title:
            lines.append(f"  Title:    {result.title}")
        lines.append(f"  Severity: {result.severity}")
        lines.append(f"  Category: {result.category}")
        return "\n".join(lines)

    def _format_list_waves(self, result: ListWavesResult) -> str:
        lines = [result.message]
        for w in result.waves:
            marker = "*" if w.get("is_modifiable") and not w.get("is_committed") else " "
            lines.append(
                f"  {marker} {w.get('id', '?'):<10} {w.get('title', ''):<34} "
                f"{w.get('type', ''):<12} {w.get('state', ''):<14}"
            )
        return "\n".join(lines)

    def _format_generate_docs(self, result: GenerateDocsResult) -> str:
        lines = [result.message or f"Generated {len(result.generated)} document(s)"]
        for p in result.generated:
            lines.append(f"  * {p}")
        return "\n".join(lines)

    def _format_rename(self, result: RenameEngagementResult) -> str:
        lines = [result.message]
        for w in result.warnings:
            lines.append(f"  Warning: {w}")
        return "\n".join(lines)

    def _format_fix(self, result: FixEngagementResult) -> str:
        lines = [result.message]
        for msg in result.messages:
            lines.append(f"  {msg}")
        return "\n".join(lines)

    def _format_refresh_agents(self, result: RefreshAgentsResult) -> str:
        lines = [result.message]
        if result.created:
            lines.append(f"  Created: {len(result.created)}")
            for name in result.created:
                lines.append(f"    - {name}")
        if result.updated:
            lines.append(f"  Updated: {len(result.updated)}")
            for name in result.updated:
                lines.append(f"    - {name}")
        if result.existing:
            lines.append(f"  Already up-to-date: {len(result.existing)}")
        return "\n".join(lines)

    def _format_agent_list(self, result: AgentListResult) -> str:
        lines = []
        if result.count == 0:
            return "No agents registered."
        for a in result.agents:
            lines.append(f"  {a.get('role', '?')} — {a.get('description', '')[:60]}")
        return "\n".join(lines)

    def _format_team_list(self, result: TeamListResult) -> str:
        lines = []
        if result.count == 0:
            return "No teams registered."
        for t in result.teams:
            lines.append(f"  {t.get('name', '?')} ({t.get('agent_count', 0)} agents)")
        return "\n".join(lines)

    def _format_consult(self, result: ConsultResult) -> str:
        lines = [result.message]
        lines.append(f"  Team:   {result.team_name}")
        lines.append(f"  Mode:   {result.mode}")
        if result.response:
            lines.append(f"  Response: {result.response[:200]}")
        return "\n".join(lines)


class ReplPresenter:
    """Presenter for REPL output (plain/ANSI text, no Click formatting).

    Uses emoji markers and ANSI formatting for terminal display.
    """

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
        if not result.success:
            return f"\u274c {result.error or result.message}"

        # Engagement lifecycle
        if isinstance(result, CreateEngagementResult):
            return self._format_create_engagement(result)
        if isinstance(result, ResumeEngagementResult):
            return f"\u2705 {result.message}"
        if isinstance(result, AbortEngagementResult):
            return self._format_abort_engagement(result)
        # Phase
        if isinstance(result, EnterPhaseResult):
            return f"\u2705 {result.message}"
        if isinstance(result, ManagePhaseResult):
            return self._format_manage_phase(result)
        # Project
        if isinstance(result, InitProjectResult):
            return self._format_init_project(result)
        # Session / Chat
        if isinstance(result, SessionResult):
            return self._format_session(result)
        if isinstance(result, ChatResult):
            return f"\u2705 {result.message}"
        # Review
        if isinstance(result, ReviewEngagementResult):
            return f"\u2705 {result.message} (decision: {result.decision})"
        if isinstance(result, FinishEngagementResult):
            return self._format_finish(result)
        # Wave
        if isinstance(result, CreateWaveResult):
            return f"\u2705 Wave created: {result.wave_title} (ID: {result.wave_id})"
        if isinstance(result, RunWaveResult):
            return self._format_run_wave(result)
        if isinstance(result, ExecuteStepResult):
            return "\u2705 Step executed"
        # Misc
        if isinstance(result, NextResult):
            return f"\u2705 {result.message}"
        if isinstance(result, QueryStatusResult):
            return self._format_query_status(result)
        if isinstance(result, QueryWhatsNextResult):
            return self._format_query_whats_next(result)
        # Analysis
        if isinstance(result, SummaryResult):
            return f"\u2705 Summary:\n{result.report or result.message}"
        if isinstance(result, InspectResult):
            return f"\u2705 Inspect results:\n{result.report or result.message}"
        if isinstance(result, AssessResult):
            return f"\u2705 Assessment:\n{result.report or result.message}"
        # Batch
        if isinstance(result, CreateWavesFromAssessmentResult):
            return f"\u2705 Created {result.created} waves from assessment"
        if isinstance(result, CreateWaveFromFindingResult):
            return f"\u2705 Wave {result.wave_id} created from finding {result.finding_id}"
        if isinstance(result, ListWavesResult):
            return self._format_list_waves(result)
        if isinstance(result, WaveStatusResult):
            return f"\u2705 {result.summary or result.message}"
        if isinstance(result, GenerateDocsResult):
            return f"\u2705 Generated {len(result.generated)} document(s)"
        if isinstance(result, AnnotateChangelogResult):
            return "\u2705 Annotation added"
        # Mgmt
        if isinstance(result, RenameEngagementResult):
            return f"\u2705 {result.message}"
        if isinstance(result, SetBranchResult):
            return f"\u2705 Branch: {result.old_branch} \u2192 {result.new_branch}"
        if isinstance(result, FixEngagementResult):
            return f"\u2705 Fixed: {', '.join(result.messages) or 'ok'}"
        if isinstance(result, RefreshAgentsResult):
            return self._format_refresh_agents(result)
        if isinstance(result, SetGovernanceResult):
            return f"\u2705 Governance: {result.level}"
        if isinstance(result, AgentListResult):
            return self._format_agent_list(result)
        if isinstance(result, TeamListResult):
            return self._format_team_list(result)
        if isinstance(result, ConsultResult):
            return f"\u2705 {result.message}"

        return f"\u2705 {result.message}"

    # ── Type-specific REPL formatters ────────────────────────────────────

    def _format_create_engagement(self, result: CreateEngagementResult) -> str:
        lines = [f"\u2705 {result.message}"]
        lines.append(f"  \x1b[36mSlug:\x1b[0m   {result.slug}")
        lines.append(f"  \x1b[36mStatus:\x1b[0m {result.status}")
        if result.current_phase:
            lines.append(f"  \x1b[36mPhase:\x1b[0m  {result.current_phase}")
        if result.target_branch:
            lines.append(f"  \x1b[36mBranch:\x1b[0m {result.target_branch}")
        if result.branch_created:
            lines.append("  \x1b[32mBranch created: yes\x1b[0m")
        for w in result.warnings:
            lines.append(f"  \u26a0\ufe0f {w.get('message', w)}")
        return "\n".join(lines)

    def _format_abort_engagement(self, result: AbortEngagementResult) -> str:
        lines = [f"\u2705 {result.message}"]
        if result.previous_status:
            lines.append(f"  \x1b[33mPrevious:\x1b[0m {result.previous_status}")
        if result.completed_phases:
            lines.append(f"  \x1b[34mPhases:\x1b[0m   {', '.join(result.completed_phases)}")
        return "\n".join(lines)

    def _format_manage_phase(self, result: ManagePhaseResult) -> str:
        lines = [f"\u2705 {result.message}"]
        if result.phases:
            lines.append("  \x1b[36mPhases:\x1b[0m")
            for p in result.phases:
                active = p.get("active", False)
                marker = "\u25c9" if active else "\u25cb"
                name = p.get("name", "?")
                status = p.get("status", "?")
                if active:
                    lines.append(f"    {marker} \x1b[1m{name}\x1b[0m: {status}")
                else:
                    lines.append(f"    {marker} {name}: {status}")
        return "\n".join(lines)

    def _format_init_project(self, result: InitProjectResult) -> str:
        lines = [f"\u2705 {result.message}"]
        lines.append(f"  \x1b[36mProject:\x1b[0m  {result.project}")
        lines.append(f"  \x1b[36mPath:\x1b[0m     {result.path}")
        if result.git_initted:
            lines.append("  \x1b[32mGit initted\x1b[0m")
        return "\n".join(lines)

    def _format_session(self, result: SessionResult) -> str:
        lines = ["\u2705 Session started"]
        lines.append(f"  \x1b[36mPhase:\x1b[0m {result.phase}")
        if result.session_type:
            lines.append(f"  \x1b[36mType:\x1b[0m  {result.session_type}")
        return "\n".join(lines)

    def _format_finish(self, result: FinishEngagementResult) -> str:
        lines = [f"\u2705 {result.message}"]
        if result.head_sha:
            lines.append(f"  \x1b[36mCommit:\x1b[0m {result.head_sha[:8]}")
        if result.branch:
            lines.append(f"  \x1b[36mBranch:\x1b[0m {result.branch}")
        return "\n".join(lines)

    def _format_run_wave(self, result: RunWaveResult) -> str:
        lines = [f"\u2705 Wave {result.wave_id} completed"]
        if result.iteration_count:
            lines.append(f"  \x1b[36mIterations:\x1b[0m {result.iteration_count}")
        return "\n".join(lines)

    def _format_query_status(self, result: QueryStatusResult) -> str:
        lines = [f"\u2705 Status: {'OK' if result.all_ok else 'Issues found'}"]
        for w in result.warnings:
            lines.append(f"  \u26a0\ufe0f {w.get('message', w)}")
        return "\n".join(lines)

    def _format_query_whats_next(self, result: QueryWhatsNextResult) -> str:
        lines = [f"\u2705 Engagement: {result.slug}"]
        lines.append(f"  \x1b[36mStatus:\x1b[0m        {result.status}")
        lines.append(f"  \x1b[36mCurrent phase:\x1b[0m {result.current_phase or '-'}")
        if result.pending_phases:
            lines.append(f"  \x1b[36mPending:\x1b[0m       {', '.join(result.pending_phases)}")
        if result.available_commands:
            lines.append(f"  \x1b[36mCommands:\x1b[0m      {', '.join(result.available_commands)}")
        if result.blocked:
            lines.append(f"  \u26a0\ufe0f  Blocked: {result.block_reason}")
        return "\n".join(lines)

    def _format_list_waves(self, result: ListWavesResult) -> str:
        if not result.waves:
            return "\u2705 No waves defined"
        lines = ["\u2705 Waves:"]
        for w in result.waves:
            active = w.get("is_modifiable", False) and not w.get("is_committed", False)
            marker = "\u25c9" if active else "\u25cb"
            lines.append(
                f"  {marker} \x1b[1m{w.get('id', '?')}\x1b[0m: "
                f"{w.get('title', '')} "
                f"[{w.get('type', '')}] \x1b[33m{w.get('state', '')}\x1b[0m"
            )
        return "\n".join(lines)

    def _format_resume_engagement(self, result: ResumeEngagementResult) -> str:
        lines = [f"\u2705 {result.message}"]
        lines.append(f"  \x1b[36mSlug:\x1b[0m   {result.slug}")
        lines.append(f"  \x1b[36mStatus:\x1b[0m {result.status}")
        if result.current_phase:
            lines.append(f"  \x1b[36mPhase:\x1b[0m  {result.current_phase}")
        for w in result.warnings:
            lines.append(f"  \u26a0\ufe0f {w.get('message', w)}")
        return "\n".join(lines)

    def _format_enter_phase(self, result: EnterPhaseResult) -> str:
        lines = [f"\u2705 Entered phase: {result.phase}"]
        lines.append(f"  \x1b[36mSlug:\x1b[0m    {result.slug}")
        lines.append(f"  \x1b[36mStarted:\x1b[0m {'yes' if result.started else 'no'}")
        return "\n".join(lines)

    def _format_chat(self, result: ChatResult) -> str:
        lines = ["\u2705 Chat opened"]
        lines.append(f"  \x1b[36mSlug:\x1b[0m  {result.slug}")
        lines.append(f"  \x1b[36mPhase:\x1b[0m {result.phase}")
        return "\n".join(lines)

    def _format_create_wave(self, result: CreateWaveResult) -> str:
        lines = ["\u2705 Wave created"]
        lines.append(f"  \x1b[36mTitle:\x1b[0m {result.wave_title}")
        lines.append(f"  \x1b[36mID:\x1b[0m    {result.wave_id}")
        return "\n".join(lines)

    def _format_execute_step(self, result: ExecuteStepResult) -> str:
        lines = ["\u2705 Step executed"]
        if hasattr(result, 'slug') and result.slug:
            lines.append(f"  \x1b[36mSlug:\x1b[0m {result.slug}")
        if result.step:
            lines.append(f"  \x1b[36mStep:\x1b[0m {result.step}")
        return "\n".join(lines)

    def _format_review(self, result: ReviewEngagementResult) -> str:
        lines = [f"\u2705 {result.message}"]
        lines.append(f"  \x1b[36mDecision:\x1b[0m {result.decision}")
        if result.slug:
            lines.append(f"  \x1b[36mSlug:\x1b[0m     {result.slug}")
        return "\n".join(lines)

    def _format_rename(self, result: RenameEngagementResult) -> str:
        lines = [f"\u2705 {result.message}"]
        if result.changes_made:
            lines.append("  \x1b[32mChanges made\x1b[0m")
        for w in result.warnings:
            lines.append(f"  \u26a0\ufe0f {w}")
        for e in result.errors:
            lines.append(f"  \u274c {e}")
        return "\n".join(lines)

    def _format_set_branch(self, result: SetBranchResult) -> str:
        return f"\u2705 Branch: {result.old_branch} \u2192 {result.new_branch}"

    def _format_fix(self, result: FixEngagementResult) -> str:
        lines = ["\u2705 Fixed engagement"]
        for msg in result.messages:
            lines.append(f"  \u25b8 {msg}")
        return "\n".join(lines) if result.messages else "\u2705 Fixed engagement (no messages)"

    def _format_set_governance(self, result: SetGovernanceResult) -> str:
        return f"\u2705 Governance set to '{result.level}' on {result.scope}"

    def _format_consult(self, result: ConsultResult) -> str:
        lines = [f"\u2705 {result.message}"]
        lines.append(f"  \x1b[36mTeam:\x1b[0m   {result.team_name}")
        lines.append(f"  \x1b[36mMode:\x1b[0m   {result.mode}")
        if result.response:
            lines.append(f"  \x1b[36mResponse:\x1b[0m {result.response[:200]}")
        return "\n".join(lines)

    def _format_refresh_agents(self, result: RefreshAgentsResult) -> str:
        parts = []
        if result.created:
            parts.append(f"\x1b[32m{len(result.created)} created\x1b[0m")
        if result.updated:
            parts.append(f"\x1b[33m{len(result.updated)} updated\x1b[0m")
        if result.existing:
            parts.append(f"{len(result.existing)} up-to-date")
        summary = ", ".join(parts) if parts else "ok"
        return f"\u2705 Agents refreshed ({summary})"

    def _format_agent_list(self, result: AgentListResult) -> str:
        if result.count == 0:
            return "\u2705 No agents registered"
        lines = [f"\u2705 {result.count} agent(s):"]
        for a in result.agents:
            lines.append(f"  \u25cf \x1b[1m{a.get('role', '?')}\x1b[0m")
        return "\n".join(lines)

    def _format_team_list(self, result: TeamListResult) -> str:
        if result.count == 0:
            return "\u2705 No teams registered"
        lines = [f"\u2705 {result.count} team(s):"]
        for t in result.teams:
            lines.append(f"  \u25cf \x1b[1m{t.get('name', '?')}\x1b[0m ({t.get('agent_count', 0)} agents)")
        return "\n".join(lines)
