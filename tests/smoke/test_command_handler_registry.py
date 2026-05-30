"""CommandBus handler registry smoke tests.

Validates the complete CommandBus handler registration:

- All handler classes are importable and instantiable
- Each handler type is registered in the CommandRegistry
- All CLI command factory functions are importable
- All handlers implement the CommandHandler interface
- All registered handler types can be looked up by name
"""

from __future__ import annotations

import pytest

from harness.command.handlers import (
    AnnotateChangelogHandler,
    AssessHandler,
    ChatHandler,
    CreateWaveFromFindingHandler,
    CreateWavesFromAssessmentHandler,
    FixEngagementHandler,
    GenerateDocsHandler,
    InspectHandler,
    ListWavesHandler,
    RefreshAgentsHandler,
    RenameEngagementHandler,
    RunWaveHandler,
    SessionHandler,
    SetBranchHandler,
    SetGovernanceHandler,
    SummaryHandler,
    WaveStatusHandler,
    register_all_handlers,
)
from harness.command.registry import CommandRegistry
from harness.command.types import CommandHandler

smoke = pytest.mark.smoke

ENGAGEMENT_HANDLERS = (
    RenameEngagementHandler,
    SetBranchHandler,
    FixEngagementHandler,
    RefreshAgentsHandler,
    SetGovernanceHandler,
)
SESSION_HANDLERS = (RunWaveHandler, SessionHandler, ChatHandler)
ANALYSIS_HANDLERS = (SummaryHandler, InspectHandler, AssessHandler)
BATCH_HANDLERS = (
    CreateWavesFromAssessmentHandler,
    CreateWaveFromFindingHandler,
    ListWavesHandler,
    WaveStatusHandler,
    GenerateDocsHandler,
    AnnotateChangelogHandler,
)
ALL_HANDLER_CLASSES = (
    SESSION_HANDLERS + ANALYSIS_HANDLERS + BATCH_HANDLERS + ENGAGEMENT_HANDLERS
)


class TestHandlerImportability:
    """Every handler class is importable and instantiable."""

    @smoke
    @pytest.mark.parametrize("handler_cls", ALL_HANDLER_CLASSES, ids=lambda c: c.__name__)
    def test_handler_importable_and_instantiable(self, handler_cls):
        instance = handler_cls()
        assert instance is not None
        assert hasattr(instance, "handle")


class TestHandlerTypeRegistration:
    """Each handler's command_type is registered in the CommandRegistry."""

    @smoke
    def test_session_handlers_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        types = registry.list_registered()
        for expected in ("run_wave", "session", "chat"):
            assert expected in types, f"Missing {expected}"

    @smoke
    def test_analysis_handlers_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        types = registry.list_registered()
        for expected in ("summary", "inspect", "assess"):
            assert expected in types, f"Missing {expected}"

    @smoke
    def test_batch_handlers_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        types = registry.list_registered()
        for expected in (
            "create_waves_from_assessment",
            "create_wave_from_finding",
            "list_waves",
            "wave_status",
            "generate_docs",
            "annotate_changelog",
        ):
            assert expected in types, f"Missing {expected}"

    @smoke
    def test_engagement_handlers_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        types = registry.list_registered()
        for expected in (
            "rename_engagement", "set_branch", "fix_engagement",
            "refresh_agents", "set_governance",
        ):
            assert expected in types, f"Missing {expected}"


class TestFactoryImportability:
    """All CLI command factory functions are importable."""

    FACTORY_NAMES = [
        "run_wave_command",
        "session_command",
        "chat_command",
        "summary_command",
        "inspect_command",
        "assess_command",
        "create_waves_from_assessment_command",
        "create_wave_from_finding_command",
        "list_waves_command",
        "wave_status_command",
        "generate_docs_command",
        "annotate_changelog_command",
        "rename_engagement_command",
        "set_branch_command",
        "fix_engagement_command",
        "refresh_agents_command",
        "set_governance_command",
    ]

    @smoke
    @pytest.mark.parametrize("name", FACTORY_NAMES, ids=str)
    def test_factory_importable(self, name):
        import importlib
        module = importlib.import_module("harness.cli.commands")
        assert hasattr(module, name), f"Factory {name} not found in harness.cli.commands"


class TestHandlerInterface:
    """All handlers implement the CommandHandler interface."""

    @smoke
    def test_all_handlers_are_commandhandler_subclass(self):
        for cls in ALL_HANDLER_CLASSES:
            assert issubclass(cls, CommandHandler), f"{cls.__name__} is not a CommandHandler"

    @smoke
    def test_handler_lookup_from_registry(self):
        """All registered handler types can be looked up by name."""
        registry = CommandRegistry()
        register_all_handlers(registry)
        types = registry.list_registered()
        for t in types:
            handler = registry.get_handler(t)
            assert handler is not None, f"Handler {t} registered but not found"

    @smoke
    def test_dispatch_run_wave_returns_handler(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        handler = registry.get_handler("run_wave")
        assert isinstance(handler, RunWaveHandler)

    @smoke
    def test_dispatch_summary_returns_handler(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        handler = registry.get_handler("summary")
        assert isinstance(handler, SummaryHandler)

    @smoke
    def test_dispatch_set_governance_returns_handler(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        handler = registry.get_handler("set_governance")
        assert isinstance(handler, SetGovernanceHandler)
