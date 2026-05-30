"""Coverage tests for Sprint 3 CommandBus handlers.

Exercises every handler's handle() method with empty/invalid data to
verify the delegation-thin pattern works and catches errors gracefully.

For handlers that call into real I/O (analysis, assessment), we mock
the pipeline functions to return fast. All handlers should return a
CommandResult even with missing or invalid data.
"""
from __future__ import annotations

import unittest.mock
from pathlib import Path

import pytest

from harness.command.handlers import (
    AnnotateChangelogHandler,
    AssessHandler,
    ChatHandler,
    CreateWaveFromFindingHandler,
    CreateWavesFromAssessmentHandler,
    GenerateDocsHandler,
    InspectHandler,
    ListWavesHandler,
    RefreshAgentsHandler,
    RenameEngagementHandler,
    RunWaveHandler,
    SessionHandler,
    SetBranchHandler,
    SetGovernanceHandler,
    FixEngagementHandler,
    SummaryHandler,
    WaveStatusHandler,
    register_all_handlers,
)
from harness.command.registry import CommandRegistry
from harness.command.types import Command, CommandResult

smoke = pytest.mark.smoke

# ── Quick-return handlers (empty data → immediate error) ──────────────────


class TestQuickReturnHandlers:
    """Handlers that return quickly with empty or nonexistent data."""

    HANDLERS: list[tuple[str, object, dict]] = [
        ("run_wave", RunWaveHandler(), {"data": {}}),
        ("session", SessionHandler(), {"data": {}}),
        ("chat", ChatHandler(), {"data": {}}),
        ("list_waves", ListWavesHandler(), {"data": {}}),
        ("wave_status", WaveStatusHandler(), {"data": {}}),
        ("set_governance", SetGovernanceHandler(), {"data": {}}),
        ("generate_docs", GenerateDocsHandler(), {"data": {}}),
        ("rename_engagement", RenameEngagementHandler(), {"data": {}}),
        ("set_branch", SetBranchHandler(), {"data": {}}),
        ("fix_engagement", FixEngagementHandler(), {"data": {}}),
        ("refresh_agents", RefreshAgentsHandler(), {"data": {}}),
        ("annotate_changelog", AnnotateChangelogHandler(), {"data": {}}),
    ]

    @pytest.mark.parametrize(
        ("name", "handler", "cmd_kwargs"),
        [(n, h, k) for n, h, k in HANDLERS],
        ids=[n for n, h, k in HANDLERS],
    )
    def test_returns_command_result(self, name, handler, cmd_kwargs):
        cmd = Command(slug="no-such-slug", command_type=name, **cmd_kwargs)
        # Handlers that write to .harness config need protection
        if name == "set_governance":
            with unittest.mock.patch(
                "harness.agents.governance.set_project_governance"
            ), unittest.mock.patch(
                "harness.agents.governance.get_project_governance"
            ):
                result = handler.handle(cmd)
        else:
            result = handler.handle(cmd)
        assert isinstance(result, CommandResult), f"{name} did not return CommandResult"

    @pytest.mark.parametrize(
        ("name", "handler", "cmd_kwargs"),
        [(n, h, k) for n, h, k in HANDLERS],
        ids=[n for n, h, k in HANDLERS],
    )
    def test_is_commandhandler_subclass(self, name, handler, cmd_kwargs):
        from harness.command.types import CommandHandler
        h_cls = type(handler)
        assert issubclass(h_cls, CommandHandler), f"{name} is not a CommandHandler"


# ── Handlers that need I/O mocking ─────────────────────────────────────────


class TestSummaryHandler:
    """SummaryHandler — mocks analysis pipeline to avoid slow I/O."""

    @smoke
    def test_summary_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "summary" in registry.list_registered()

    def test_returns_command_result(self):
        from harness.analysis import fast as fast_module
        from harness.analysis import summary as summary_module

        handler = SummaryHandler()
        cmd = Command(slug="", command_type="summary", data={})

        with unittest.mock.patch.object(fast_module, "scan_structure",
                                          return_value=[{"type": "structure", "files": []}]):
            with unittest.mock.patch.object(fast_module, "scan_git_diff",
                                              return_value=[{"type": "diff", "changes": []}]):
                with unittest.mock.patch.object(summary_module, "format_report",
                                                  return_value="# Summary"):
                    result = handler.handle(cmd)

        assert isinstance(result, CommandResult), "SummaryHandler did not return CommandResult"


class TestInspectHandler:
    """InspectHandler — mocks observer analysis."""

    @smoke
    def test_inspect_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "inspect" in registry.list_registered()

    def test_returns_command_result(self):
        from harness.analysis import observer

        handler = InspectHandler()
        cmd = Command(slug="", command_type="inspect", data={"root": str(Path.cwd())})

        with unittest.mock.patch.object(observer, "analyse",
                                          return_value={"status": "success", "findings": []}):
            result = handler.handle(cmd)

        assert isinstance(result, CommandResult), "InspectHandler did not return CommandResult"


class TestAssessHandler:
    """AssessHandler — mocks assessment pipeline."""

    @smoke
    def test_assess_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "assess" in registry.list_registered()

    def test_returns_command_result(self):
        from harness.analysis import assessment

        handler = AssessHandler()
        cmd = Command(slug="", command_type="assess", data={"root": str(Path.cwd())})

        with unittest.mock.patch.object(assessment, "assess",
                                          return_value=None):
            result = handler.handle(cmd)

        assert isinstance(result, CommandResult), "AssessHandler did not return CommandResult"


class TestCreateWavesFromAssessmentHandler:
    """CreateWavesFromAssessmentHandler — returns quickly with nonexistent slug."""

    @smoke
    def test_create_waves_from_assessment_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "create_waves_from_assessment" in registry.list_registered()

    def test_returns_command_result(self):
        handler = CreateWavesFromAssessmentHandler()
        cmd = Command(slug="no-such-engagement", command_type="create_waves_from_assessment",
                      data={"focus": "high-risk"})
        result = handler.handle(cmd)
        assert isinstance(result, CommandResult), "handler did not return CommandResult"


class TestCreateWaveFromFindingHandler:
    """CreateWaveFromFindingHandler — returns quickly with nonexistent slug."""

    @smoke
    def test_create_wave_from_finding_registered(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert "create_wave_from_finding" in registry.list_registered()

    def test_returns_command_result(self):
        handler = CreateWaveFromFindingHandler()
        cmd = Command(slug="no-such-engagement", command_type="create_wave_from_finding",
                      data={"finding_id": "f1"})
        result = handler.handle(cmd)
        assert isinstance(result, CommandResult), "handler did not return CommandResult"
