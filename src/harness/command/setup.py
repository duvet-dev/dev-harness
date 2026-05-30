"""Command subsystem setup — bus factory and handler registration.

Provides a single ``create_bus()`` factory function that creates a fully
configured CommandBus with all handlers registered. This is the entry
point for CLI, REPL, and session integration.

As handlers are migrated to typed commands (Waves 2-6), they are
registered via ``bus.register_type()`` instead of the legacy
``bus.register()``.
"""

from __future__ import annotations

from harness.command.bus import CommandBus
from harness.command.registry import CommandRegistry


def create_bus() -> CommandBus:
    """Create a fully configured CommandBus with all typed handlers.

    Returns:
        A CommandBus instance with all typed handlers registered.
    """
    registry = CommandRegistry()
    bus = CommandBus(registry=registry)

    # ── Register typed handlers (all 33 commands) ───────────────────────
    from harness.command.handlers.engagement_handlers import (
        AbortEngagementTypedHandler,
        CreateEngagementHandler,
        ResumeEngagementHandler,
    )
    from harness.command.handlers.phase_handlers import (
        EnterPhaseTypedHandler,
        PhaseManagementTypedHandler,
    )
    from harness.command.handlers.project_handlers import InitProjectTypedHandler
    from harness.command.handlers.session_handlers import (
        ChatTypedHandler,
        SessionTypedHandler,
    )
    from harness.command.handlers.wave_handlers import (
        CreateWaveTypedHandler,
        ExecuteStepTypedHandler,
        RunWaveTypedHandler,
    )
    from harness.command.handlers.review_handlers import (
        FinishEngagementTypedHandler,
        ReviewEngagementTypedHandler,
    )
    from harness.command.handlers.misc_handlers import (
        NextTypedHandler,
        QueryStatusTypedHandler,
        QueryWhatsNextTypedHandler,
    )
    from harness.command.commands.engagement import (
        AbortEngagementCommand,
        CreateEngagementCommand,
        ResumeEngagementCommand,
    )
    from harness.command.commands.phase import EnterPhaseCommand, ManagePhaseCommand
    from harness.command.commands.project import InitProjectCommand
    from harness.command.commands.session import ChatCommand, SessionCommand
    from harness.command.commands.wave import (
        CreateWaveCommand,
        ExecuteStepCommand,
        RunWaveCommand,
    )
    from harness.command.commands.review import (
        FinishEngagementCommand,
        ReviewEngagementCommand,
    )
    from harness.command.commands.misc import (
        NextCommand,
        QueryStatusCommand,
        QueryWhatsNextCommand,
    )

    bus.register_type(CreateEngagementHandler(), CreateEngagementCommand, legacy_alias="create_engagement")
    bus.register_type(ResumeEngagementHandler(), ResumeEngagementCommand, legacy_alias="resume_engagement")
    bus.register_type(AbortEngagementTypedHandler(), AbortEngagementCommand, legacy_alias="abort_engagement")
    bus.register_type(EnterPhaseTypedHandler(), EnterPhaseCommand, legacy_alias="enter_phase")
    bus.register_type(PhaseManagementTypedHandler(), ManagePhaseCommand, legacy_alias="manage_phase")
    bus.register_type(InitProjectTypedHandler(), InitProjectCommand, legacy_alias="init_project")
    bus.register_type(NextTypedHandler(), NextCommand, legacy_alias="next")
    bus.register_type(CreateWaveTypedHandler(), CreateWaveCommand, legacy_alias="create_wave")
    bus.register_type(ExecuteStepTypedHandler(), ExecuteStepCommand, legacy_alias="execute_step")
    bus.register_type(QueryStatusTypedHandler(), QueryStatusCommand, legacy_alias="query_status")
    bus.register_type(QueryWhatsNextTypedHandler(), QueryWhatsNextCommand, legacy_alias="query_whats_next")
    bus.register_type(FinishEngagementTypedHandler(), FinishEngagementCommand, legacy_alias="finish_engagement")
    bus.register_type(ReviewEngagementTypedHandler(), ReviewEngagementCommand, legacy_alias="review_engagement")
    bus.register_type(RunWaveTypedHandler(), RunWaveCommand, legacy_alias="run_wave")
    bus.register_type(SessionTypedHandler(), SessionCommand, legacy_alias="session")
    bus.register_type(ChatTypedHandler(), ChatCommand, legacy_alias="chat")

    # ── Register Wave 4 typed handlers (analysis, batch, mgmt) ──────────
    from harness.command.handlers.analysis_handlers import (
        AssessTypedHandler,
        InspectTypedHandler,
        SummaryTypedHandler,
    )
    from harness.command.handlers.batch_handlers import (
        AnnotateChangelogTypedHandler,
        CreateWaveFromFindingTypedHandler,
        CreateWavesFromAssessmentTypedHandler,
        GenerateDocsTypedHandler,
        ListWavesTypedHandler,
        WaveStatusTypedHandler,
    )
    from harness.command.handlers.mgmt_handlers import (
        AgentListTypedHandler,
        ConsultTypedHandler,
        FixEngagementTypedHandler,
        FleetListTypedHandler,
        RefreshAgentsTypedHandler,
        RenameEngagementTypedHandler,
        SetBranchTypedHandler,
        SetGovernanceTypedHandler,
    )
    from harness.command.commands.analysis import (
        AssessCommand,
        InspectCommand,
        SummaryCommand,
    )
    from harness.command.commands.batch import (
        AnnotateChangelogCommand,
        CreateWaveFromFindingCommand,
        CreateWavesFromAssessmentCommand,
        GenerateDocsCommand,
        ListWavesCommand,
        WaveStatusCommand,
    )
    from harness.command.commands.mgmt import (
        AgentListCommand,
        ConsultCommand,
        FixEngagementCommand,
        FleetListCommand,
        RefreshAgentsCommand,
        RenameEngagementCommand,
        SetBranchCommand,
        SetGovernanceCommand,
    )

    bus.register_type(SummaryTypedHandler(), SummaryCommand, legacy_alias="summary")
    bus.register_type(InspectTypedHandler(), InspectCommand, legacy_alias="inspect")
    bus.register_type(AssessTypedHandler(), AssessCommand, legacy_alias="assess")
    bus.register_type(CreateWavesFromAssessmentTypedHandler(), CreateWavesFromAssessmentCommand, legacy_alias="create_waves_from_assessment")
    bus.register_type(CreateWaveFromFindingTypedHandler(), CreateWaveFromFindingCommand, legacy_alias="create_wave_from_finding")
    bus.register_type(ListWavesTypedHandler(), ListWavesCommand, legacy_alias="list_waves")
    bus.register_type(WaveStatusTypedHandler(), WaveStatusCommand, legacy_alias="wave_status")
    bus.register_type(GenerateDocsTypedHandler(), GenerateDocsCommand, legacy_alias="generate_docs")
    bus.register_type(AnnotateChangelogTypedHandler(), AnnotateChangelogCommand, legacy_alias="annotate_changelog")
    bus.register_type(RenameEngagementTypedHandler(), RenameEngagementCommand, legacy_alias="rename_engagement")
    bus.register_type(SetBranchTypedHandler(), SetBranchCommand, legacy_alias="set_branch")
    bus.register_type(FixEngagementTypedHandler(), FixEngagementCommand, legacy_alias="fix_engagement")
    bus.register_type(RefreshAgentsTypedHandler(), RefreshAgentsCommand, legacy_alias="refresh_agents")
    bus.register_type(SetGovernanceTypedHandler(), SetGovernanceCommand, legacy_alias="set_governance")
    bus.register_type(AgentListTypedHandler(), AgentListCommand, legacy_alias="agent_list")
    bus.register_type(FleetListTypedHandler(), FleetListCommand, legacy_alias="fleet_list")
    bus.register_type(ConsultTypedHandler(), ConsultCommand, legacy_alias="consult")

    return bus



__all__ = [
    "create_bus",
]
