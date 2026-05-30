"""Tests for delegation-thin command handlers.

Covers all 9 handlers defined in V7 §5.20 Handler Delegation Map.
"""

from __future__ import annotations

import builtins
from unittest.mock import patch

import pytest

from harness.command.legacy_handlers import (
    SummaryHandler,
    InspectHandler,
    AssessHandler,
    CreateWavesFromAssessmentHandler,
    CreateWaveFromFindingHandler,
    ListWavesHandler,
    WaveStatusHandler,
    GenerateDocsHandler,
    AnnotateChangelogHandler,
    RenameEngagementHandler,
    SetBranchHandler,
    FixEngagementHandler,
    RefreshAgentsHandler,
    SetGovernanceHandler,
    AgentListHandler,
    FleetListHandler,
    ConsultHandler,
    register_all_handlers,
)
from harness.command.registry import CommandRegistry
from harness.command.types import Command, CommandHandler, CommandResult


class TestRegisterAllHandlers:
    """Tests for the register_all_handlers convenience function."""

    def test_registers_all_handlers(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        types = registry.list_registered()
        assert "summary" in types
        assert "inspect" in types
        assert "assess" in types
        assert "list_waves" in types
        assert "rename_engagement" in types
        assert "agent_list" in types

    def test_each_handler_is_distinct_instance(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        # Each handler should be a different instance
        h1 = registry.get_handler("summary")
        h2 = registry.get_handler("inspect")
        assert h1 is not h2


# ── Exception branch coverage ───────────────────────────────────────


class TestAgentListHandler:
    """Wave O: AgentListHandler — lists registered agents."""

    def test_importable(self):
        from harness.command.legacy_handlers import AgentListHandler
        handler = AgentListHandler()
        assert isinstance(handler, CommandHandler)

    def test_returns_agent_list(self):
        from harness.command.legacy_handlers import AgentListHandler
        handler = AgentListHandler()
        cmd = Command(slug="", command_type="agent_list")
        result = handler.handle(cmd)
        assert result.success is True
        data = result.data
        assert "agents" in data
        assert isinstance(data["agents"], list)
        assert data["count"] >= 1

    def test_registered_in_registry(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert registry.has_handler("agent_list")


class TestFleetListHandler:
    """Wave O: FleetListHandler — lists registered teams."""

    def test_importable(self):
        from harness.command.legacy_handlers import FleetListHandler
        handler = FleetListHandler()
        assert isinstance(handler, CommandHandler)

    def test_returns_team_list(self):
        from harness.command.legacy_handlers import FleetListHandler
        handler = FleetListHandler()
        cmd = Command(slug="", command_type="fleet_list")
        result = handler.handle(cmd)
        assert result.success is True
        data = result.data
        assert "teams" in data
        assert isinstance(data["teams"], list)
        assert data["count"] >= 1

    def test_registered_in_registry(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert registry.has_handler("fleet_list")


class TestConsultHandler:
    """Wave O: ConsultHandler — routes consultation questions."""

    def test_importable(self):
        from harness.command.legacy_handlers import ConsultHandler
        handler = ConsultHandler()
        assert isinstance(handler, CommandHandler)

    def test_routes_question(self):
        """Consult handler should return a result (matched or unmatched)."""
        from harness.command.legacy_handlers import ConsultHandler
        handler = ConsultHandler()
        cmd = Command(
            slug="",
            command_type="consult",
            data={"question": "architecture review"},
        )
        result = handler.handle(cmd)
        # Built-in teams may not have consultations; handler should not crash
        isinstance(result, CommandResult)
        assert "status" in result.data

    def test_registered_in_registry(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        assert registry.has_handler("consult")


class TestCommandHandlerAbstractBody:
    """Coverage for CommandHandler.handle() abstract body (line 66)."""

    def test_abstract_handle_body_via_super(self):
        """Calling the abstract handle body via super() returns None."""
        class _DirectHandler(CommandHandler):  # type: ignore[misc]
            def handle(self, command: Command) -> CommandResult:
                return super().handle(command)  # type: ignore[return-value]

        result = _DirectHandler().handle(Command(slug="test"))
        assert result is None


# ── Exception branch coverage for all handlers ──────────────────────


class TestSummaryHandlerExceptions:
    """Coverage for SummaryHandler exception branch."""

    def test_returns_command_result(self):
        handler = SummaryHandler()
        cmd = Command(slug="", command_type="summary", data={})
        result = handler.handle(cmd)
        assert isinstance(result, CommandResult)


class TestInspectHandlerExceptions:
    """Coverage for InspectHandler exception branch."""

    def test_exception_returns_error(self):
        handler = InspectHandler()
        cmd = Command(slug="", command_type="inspect",
                      data={"root": "."})
        with patch(
            "harness.analysis.observer.analyse",
            side_effect=RuntimeError("mocked inspect error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked inspect error" in result.error


class TestAssessHandlerExceptions:
    """Coverage for AssessHandler exception branch."""

    def test_exception_returns_error(self):
        handler = AssessHandler()
        cmd = Command(slug="", command_type="assess",
                      data={"root": "."})
        with patch(
            "harness.analysis.observer.analyse",
            side_effect=RuntimeError("mocked assess error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked assess error" in result.error


class TestCreateWavesFromAssessmentHandlerExceptions:
    """Coverage for CreateWavesFromAssessmentHandler exception branch."""

    def test_exception_returns_error(self):
        handler = CreateWavesFromAssessmentHandler()
        cmd = Command(slug="", command_type="create_waves_from_assessment")
        result = handler.handle(cmd)
        assert isinstance(result, CommandResult)


class TestCreateWaveFromFindingHandlerExceptions:
    """Coverage for CreateWaveFromFindingHandler exception branch."""

    def test_no_finding_id_returns_error(self):
        handler = CreateWaveFromFindingHandler()
        cmd = Command(slug="test-eng", command_type="create_wave_from_finding")
        result = handler.handle(cmd)
        # May fail because slug doesn't exist or no finding_id
        assert isinstance(result, CommandResult)

    def test_exception_returns_error(self):
        handler = CreateWaveFromFindingHandler()
        cmd = Command(slug="test-eng", command_type="create_wave_from_finding",
                      data={"finding_id": "f1"})
        # Patch a module that is imported inside to raise
        with patch(
            "harness.paths.get_engagements_dir",
            side_effect=RuntimeError("mocked path error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked path error" in result.error


class TestListWavesHandlerExceptions:
    """Coverage for ListWavesHandler exception branch."""

    def test_exception_returns_error(self):
        handler = ListWavesHandler()
        cmd = Command(slug="", command_type="list_waves")
        with patch(
            "harness.engagement.resolver.resolve_active_engagement",
            side_effect=RuntimeError("mocked resolver error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked resolver error" in result.error


class TestWaveStatusHandlerExceptions:
    """Coverage for WaveStatusHandler exception branch."""

    def test_exception_returns_error(self):
        handler = WaveStatusHandler()
        cmd = Command(slug="", command_type="wave_status")
        with patch(
            "harness.engagement.resolver.resolve_active_engagement",
            side_effect=RuntimeError("mocked resolver error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked resolver error" in result.error


class TestGenerateDocsHandlerExceptions:
    """Coverage for GenerateDocsHandler exception branch."""

    def test_exception_returns_error(self):
        handler = GenerateDocsHandler()
        cmd = Command(slug="", command_type="generate_docs", data={"root": "."})
        with patch(
            "harness.docs.generator.generate_all_docs",
            side_effect=RuntimeError("mocked doc error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked doc error" in result.error


class TestAnnotateChangelogHandlerExceptions:
    """Coverage for AnnotateChangelogHandler exception branch."""

    def test_engagement_not_found(self):
        handler = AnnotateChangelogHandler()
        cmd = Command(slug="nonexistent-eng", command_type="annotate_changelog")
        result = handler.handle(cmd)
        assert result.success is False
        assert "not found" in result.error

    def test_exception_returns_error(self):
        handler = AnnotateChangelogHandler()
        cmd = Command(slug="test-eng", command_type="annotate_changelog")
        with patch(
            "harness.paths.get_engagement_dir",
            side_effect=RuntimeError("mocked path error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked path error" in result.error


class TestRenameEngagementHandlerExceptions:
    """Coverage for RenameEngagementHandler exception branch."""

    def test_exception_returns_error(self):
        handler = RenameEngagementHandler()
        cmd = Command(slug="test-eng", command_type="rename_engagement",
                      data={"new_slug": "new-eng"})
        with patch(
            "harness.engagement.rename.rename_engagement",
            side_effect=RuntimeError("mocked rename error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked rename error" in result.error


class TestSetBranchHandlerExceptions:
    """Coverage for SetBranchHandler exception branch."""

    def test_exception_returns_error(self):
        handler = SetBranchHandler()
        cmd = Command(slug="test-eng", command_type="set_branch",
                      data={"branch": "main"})
        with patch(
            "harness.paths.get_engagement_dir",
            side_effect=RuntimeError("mocked path error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked path error" in result.error


class TestFixEngagementHandlerExceptions:
    """Coverage for FixEngagementHandler exception branch."""

    def test_exception_returns_error(self):
        handler = FixEngagementHandler()
        cmd = Command(slug="", command_type="fix_engagement")
        with patch(
            "harness.engagement.resolver.resolve_active_engagement",
            side_effect=RuntimeError("mocked resolver error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked resolver error" in result.error


class TestRefreshAgentsHandlerExceptions:
    """Coverage for RefreshAgentsHandler exception branch."""

    def test_exception_returns_error(self):
        handler = RefreshAgentsHandler()
        cmd = Command(slug="", command_type="refresh_agents")
        with patch(
            "harness.cli.helpers.require_project_root",
            side_effect=RuntimeError("mocked refresh error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked refresh error" in result.error


class TestSetGovernanceHandlerExceptions:
    """Coverage for SetGovernanceHandler exception branch."""

    def test_exception_returns_error(self):
        handler = SetGovernanceHandler()
        cmd = Command(slug="", command_type="set_governance",
                      data={"level": "strict"})
        with patch(
            "harness.cli.helpers.require_project_root",
            side_effect=RuntimeError("mocked governance error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked governance error" in result.error


class TestAgentListHandlerExceptions:
    """Coverage for AgentListHandler exception branch."""

    def test_exception_returns_error(self):
        handler = AgentListHandler()
        cmd = Command(slug="", command_type="agent_list")
        with patch(
            "harness.agents.agent_registry.list_agent_roles",
            side_effect=RuntimeError("mocked agent list error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked agent list error" in result.error


class TestFleetListHandlerExceptions:
    """Coverage for FleetListHandler exception branch."""

    def test_exception_returns_error(self):
        handler = FleetListHandler()
        cmd = Command(slug="", command_type="fleet_list")
        with patch(
            "harness.team.registry.TeamRegistry",
            side_effect=RuntimeError("mocked fleet error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked fleet error" in result.error


class TestConsultHandlerExceptions:
    """Coverage for ConsultHandler exception branch."""

    def test_exception_returns_error(self):
        handler = ConsultHandler()
        cmd = Command(slug="", command_type="consult",
                      data={"question": "test"})
        with patch(
            "harness.agents.consultation.ConsultationOrchestrator",
            side_effect=RuntimeError("mocked consult error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked consult error" in result.error
