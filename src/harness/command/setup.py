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
    from harness.command.commands.engagement import (
        AbortEngagementCommand,
        CreateEngagementCommand,
        ResumeEngagementCommand,
    )
    from harness.command.commands.phase import EnterPhaseCommand, ManagePhaseCommand
    from harness.command.commands.project import InitProjectCommand

    bus.register_type(CreateEngagementHandler(), CreateEngagementCommand)
    bus.register_type(ResumeEngagementHandler(), ResumeEngagementCommand)
    bus.register_type(AbortEngagementTypedHandler(), AbortEngagementCommand)
    bus.register_type(EnterPhaseTypedHandler(), EnterPhaseCommand)
    bus.register_type(PhaseManagementTypedHandler(), ManagePhaseCommand)
    bus.register_type(InitProjectTypedHandler(), InitProjectCommand)

    return bus


__all__ = [
    "create_bus",
]
