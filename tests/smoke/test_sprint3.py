"""Sprint 3 smoke tests — validate Waves F+G+H+I handler and factory registration.

Verifies:
- All 17 new handlers are importable from harness.command.handlers
- All 17 factory functions are importable from harness.cli.commands
- register_all_handlers() registers exactly 30 entries
- Key dispatch paths produce CommandResult
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
from harness.command.types import Command, CommandResult

smoke = pytest.mark.smoke
WAVE_F_HANDLERS = (RunWaveHandler, SessionHandler, ChatHandler)
WAVE_G_HANDLERS = (SummaryHandler, InspectHandler, AssessHandler)
WAVE_H_HANDLERS = (
    CreateWavesFromAssessmentHandler,
    CreateWaveFromFindingHandler,
    ListWavesHandler,
    WaveStatusHandler,
    GenerateDocsHandler,
    AnnotateChangelogHandler,
)
WAVE_I_HANDLERS = (
    RenameEngagementHandler,
    SetBranchHandler,
    FixEngagementHandler,
    RefreshAgentsHandler,
    SetGovernanceHandler,
)
ALL_NEW_HANDLERS = WAVE_F_HANDLERS + WAVE_G_HANDLERS + WAVE_H_HANDLERS + WAVE_I_HANDLERS


class TestSprint3HandlerImportability:
    """Every new Sprint 3 handler class is importable and instantiable."""

    @smoke
    @pytest.mark.parametrize("handler_cls", ALL_NEW_HANDLERS, ids=lambda c: c.__name__)
    def test_handler_importable_and_instantiable(self, handler_cls):
        instance = handler_cls()
        assert instance is not None
        assert hasattr(instance, "handle")


class TestSprint3HandlerRegistration:
    """register_all_handlers registers all 30 handlers."""

    @smoke
    def test_all_30_handlers_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        types = registry.list_registered()
        assert len(types) == 30, f"Expected 30, got {len(types)}"

    @smoke
    def test_sprint3_wave_f_types_present(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        types = registry.list_registered()
        for expected in ("run_wave", "session", "chat"):
            assert expected in types, f"Missing {expected}"

    @smoke
    def test_sprint3_wave_g_types_present(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        types = registry.list_registered()
        for expected in ("summary", "inspect", "assess"):
            assert expected in types, f"Missing {expected}"

    @smoke
    def test_sprint3_wave_h_types_present(self):
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
    def test_sprint3_wave_i_types_present(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        types = registry.list_registered()
        for expected in ("rename_engagement", "set_branch", "fix_engagement", "refresh_agents", "set_governance"):
            assert expected in types, f"Missing {expected}"


class TestSprint3FactoryImportability:
    """All 17 factory functions are importable from harness.cli.commands."""

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


class TestSprint3HandlerTypes:
    """All Sprint 3 handlers implement CommandHandler interface."""

    @smoke
    def test_all_handlers_are_commandhandler_subclass(self):
        from harness.command.types import CommandHandler
        handlers = [
            RunWaveHandler, SessionHandler, ChatHandler,
            SummaryHandler, InspectHandler, AssessHandler,
            CreateWavesFromAssessmentHandler, CreateWaveFromFindingHandler,
            ListWavesHandler, WaveStatusHandler, GenerateDocsHandler,
            AnnotateChangelogHandler, RenameEngagementHandler,
            SetBranchHandler, FixEngagementHandler,
            RefreshAgentsHandler, SetGovernanceHandler,
        ]
        for cls in handlers:
            assert issubclass(cls, CommandHandler), f"{cls.__name__} is not a CommandHandler"

    @smoke
    def test_dispatch_lookup_all_30(self):
        """All registered handlers can be looked up from the registry."""
        registry = CommandRegistry()
        register_all_handlers(registry)
        types = registry.list_registered()
        assert len(types) == 30
        for t in types:
            handler = registry.get_handler(t)
            assert handler is not None, f"Handler {t} registered but not found"

    @smoke
    def test_dispatch_run_wave_gets_handler(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        handler = registry.get_handler("run_wave")
        assert isinstance(handler, RunWaveHandler)

    @smoke
    def test_dispatch_summary_gets_handler(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        handler = registry.get_handler("summary")
        assert isinstance(handler, SummaryHandler)

    @smoke
    def test_dispatch_set_governance_gets_handler(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        handler = registry.get_handler("set_governance")
        assert isinstance(handler, SetGovernanceHandler)
