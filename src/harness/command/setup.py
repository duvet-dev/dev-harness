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
from harness.command.legacy_handlers import register_all_handlers
from harness.command.registry import CommandRegistry


def create_bus() -> CommandBus:
    """Create a fully configured CommandBus with all handlers.

    Registers both legacy (string-based) and typed (type-based) handlers.

    Returns:
        A CommandBus instance with all current handlers registered.
    """
    registry = CommandRegistry()
    register_all_handlers(registry)
    bus = CommandBus(registry=registry)

    # ── Register typed handlers (Waves 2+) ──────────────────────────────
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

    bus.register_type(CreateEngagementHandler(), CreateEngagementCommand)
    bus.register_type(ResumeEngagementHandler(), ResumeEngagementCommand)
    bus.register_type(AbortEngagementTypedHandler(), AbortEngagementCommand)
    bus.register_type(EnterPhaseTypedHandler(), EnterPhaseCommand)
    bus.register_type(PhaseManagementTypedHandler(), ManagePhaseCommand)
    bus.register_type(InitProjectTypedHandler(), InitProjectCommand)
    bus.register_type(NextTypedHandler(), NextCommand)
    bus.register_type(CreateWaveTypedHandler(), CreateWaveCommand)
    bus.register_type(ExecuteStepTypedHandler(), ExecuteStepCommand)
    bus.register_type(QueryStatusTypedHandler(), QueryStatusCommand)
    bus.register_type(QueryWhatsNextTypedHandler(), QueryWhatsNextCommand)
    bus.register_type(FinishEngagementTypedHandler(), FinishEngagementCommand)
    bus.register_type(ReviewEngagementTypedHandler(), ReviewEngagementCommand)
    bus.register_type(RunWaveTypedHandler(), RunWaveCommand)
    bus.register_type(SessionTypedHandler(), SessionCommand)
    bus.register_type(ChatTypedHandler(), ChatCommand)

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

    bus.register_type(SummaryTypedHandler(), SummaryCommand)
    bus.register_type(InspectTypedHandler(), InspectCommand)
    bus.register_type(AssessTypedHandler(), AssessCommand)
    bus.register_type(CreateWavesFromAssessmentTypedHandler(), CreateWavesFromAssessmentCommand)
    bus.register_type(CreateWaveFromFindingTypedHandler(), CreateWaveFromFindingCommand)
    bus.register_type(ListWavesTypedHandler(), ListWavesCommand)
    bus.register_type(WaveStatusTypedHandler(), WaveStatusCommand)
    bus.register_type(GenerateDocsTypedHandler(), GenerateDocsCommand)
    bus.register_type(AnnotateChangelogTypedHandler(), AnnotateChangelogCommand)
    bus.register_type(RenameEngagementTypedHandler(), RenameEngagementCommand)
    bus.register_type(SetBranchTypedHandler(), SetBranchCommand)
    bus.register_type(FixEngagementTypedHandler(), FixEngagementCommand)
    bus.register_type(RefreshAgentsTypedHandler(), RefreshAgentsCommand)
    bus.register_type(SetGovernanceTypedHandler(), SetGovernanceCommand)
    bus.register_type(AgentListTypedHandler(), AgentListCommand)
    bus.register_type(FleetListTypedHandler(), FleetListCommand)
    bus.register_type(ConsultTypedHandler(), ConsultCommand)

    return bus


__all__ = [
    "create_bus",
]
