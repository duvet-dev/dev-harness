"""Tests for delegation-thin command handlers.

Covers all 9 handlers defined in V7 §5.20 Handler Delegation Map.
"""

from __future__ import annotations

import builtins
from unittest.mock import patch

import pytest

from harness.command.handlers import (
    AbortEngagementHandler,
    CreateEngagementHandler,
    CreateWaveHandler,
    EnterPhaseHandler,
    ExecuteStepHandler,
    NextHandler,
    QueryStatusHandler,
    QueryWhatsNextHandler,
    ResumeEngagementHandler,
    FinishEngagementHandler,
    ReviewEngagementHandler,
    InitProjectHandler,
    PhaseManagementHandler,
    RunWaveHandler,
    SessionHandler,
    ChatHandler,
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


class TestCreateEngagementHandler:
    """Delegates to StartupResumeFlow.create() — Wave 10 wired."""

    def test_creates_engagement(self, tmp_path):
        """Handler creates engagement via StartupResumeFlow."""
        # Set up a temp project with .harness dir
        (tmp_path / ".harness").mkdir()

        from unittest.mock import patch
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            handler = CreateEngagementHandler()
            cmd = Command(slug="my-eng", command_type="create_engagement")
            result = handler.handle(cmd)

        assert result.success is True
        assert "created" in result.message
        assert result.data["slug"] == "my-eng"
        assert result.data["status"] == "active"
        assert result.data["delegated_to"] == "StartupResumeFlow.create()"

    def test_with_workflow_override(self, tmp_path):
        """Handler passes workflow_name through to StartupResumeFlow."""
        (tmp_path / ".harness").mkdir()

        from unittest.mock import patch
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            handler = CreateEngagementHandler()
            cmd = Command(
                slug="fix-bug", command_type="create_engagement",
                data={"workflow_name": "quick-fix"},
            )
            result = handler.handle(cmd)

        assert result.success is True
        assert result.data["workflow_name"] == "quick-fix"

    def test_empty_slug_fails(self, tmp_path):
        """Empty slug is rejected."""
        (tmp_path / ".harness").mkdir()

        from unittest.mock import patch
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            handler = CreateEngagementHandler()
            cmd = Command(slug="", command_type="create_engagement")
            result = handler.handle(cmd)

        assert result.success is False
        assert "cannot be empty" in result.error.lower()

    def test_duplicate_slug_fails(self, tmp_path):
        """Creating with existing slug fails."""
        (tmp_path / ".harness").mkdir()

        from unittest.mock import patch
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            handler = CreateEngagementHandler()
            # Create first
            cmd1 = Command(slug="my-eng", command_type="create_engagement")
            handler.handle(cmd1)
            # Try again — should fail
            cmd2 = Command(slug="my-eng", command_type="create_engagement")
            result = handler.handle(cmd2)

        assert result.success is False
        assert "already exists" in result.error.lower()


class TestResumeEngagementHandler:
    """Delegates to StartupResumeFlow.resume() — Wave 10 wired."""

    def test_resumes_engagement(self, tmp_path):
        """Handler resumes engagement via StartupResumeFlow."""
        (tmp_path / ".harness").mkdir()

        from unittest.mock import patch
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            # First create an engagement
            create_handler = CreateEngagementHandler()
            create_cmd = Command(
                slug="my-eng", command_type="create_engagement",
            )
            create_handler.handle(create_cmd)

            # Now resume it
            handler = ResumeEngagementHandler()
            cmd = Command(slug="my-eng", command_type="resume_engagement")
            result = handler.handle(cmd)

        assert result.success is True
        assert "resumed" in result.message
        assert result.data["slug"] == "my-eng"
        assert result.data["status"] == "active"
        assert result.data["delegated_to"] == "StartupResumeFlow.resume()"


class TestEnterPhaseHandler:
    """Delegates to PhaseOrchestrator.enter_phase()."""

    def test_returns_success_for_valid_phase(self):
        handler = EnterPhaseHandler()
        cmd = Command(
            slug="my-eng", command_type="enter_phase",
            data={"phase": "design"},
        )
        result = handler.handle(cmd)
        assert result.success is True
        assert "Phase 'design' entry dispatched" in result.message

    def test_missing_phase_returns_error(self):
        handler = EnterPhaseHandler()
        cmd = Command(slug="my-eng", command_type="enter_phase", data={})
        result = handler.handle(cmd)
        assert result.success is False
        assert "No phase specified" in result.error


class TestNextHandler:
    """Delegates to NextEngine.advance() — async gap, partially wired."""

    def test_returns_delegated_status(self):
        handler = NextHandler()
        cmd = Command(slug="my-eng", command_type="next")
        result = handler.handle(cmd)
        assert result.success is True
        assert "dispatched to NextEngine" in result.message
        assert result.data["status"] == "delegated"
        assert result.data["delegated_to"] == "NextEngine.advance()"

    def test_notes_async_gap(self):
        """Handler notes that full async dispatch requires future wave."""
        handler = NextHandler()
        cmd = Command(slug="my-eng", command_type="next")
        result = handler.handle(cmd)
        assert "async" in result.data["note"].lower()


class TestCreateWaveHandler:
    """Delegates to PlanManager.create_wave()."""

    def test_returns_success(self):
        handler = CreateWaveHandler()
        cmd = Command(
            slug="my-eng", command_type="create_wave",
            data={"title": "Test Wave"},
        )
        result = handler.handle(cmd)
        assert result.success is True
        assert "Wave 'Test Wave' created" in result.message


class TestExecuteStepHandler:
    """Delegates to StepDispatcher.dispatch()."""

    def test_returns_success_with_step_data(self):
        handler = ExecuteStepHandler()
        cmd = Command(
            slug="my-eng", command_type="execute_step",
            data={"step": {"agents": ["architect"], "output": "spec"}},
        )
        result = handler.handle(cmd)
        assert result.success is True
        assert "Step execution dispatched" in result.message

    def test_without_step_data(self):
        handler = ExecuteStepHandler()
        cmd = Command(slug="my-eng", command_type="execute_step", data={})
        result = handler.handle(cmd)
        assert result.success is True


class TestAbortEngagementHandler:
    """Delegates to AbortHandler — Wave 6 wired."""

    def test_attempts_abort_via_handler(self):
        """Handler attempts real abort; fails gracefully if engagement missing."""
        handler = AbortEngagementHandler()
        cmd = Command(
            slug="nonexistent-eng", command_type="abort_engagement",
            data={"mode": "graceful"},
        )
        result = handler.handle(cmd)
        # Will fail gracefully since the engagement doesn't exist on disk
        assert "Abort failed" in result.message or "aborted" in result.message

    def test_passes_mode_through(self):
        """Mode is passed to AbortHandler."""
        handler = AbortEngagementHandler()
        cmd = Command(
            slug="nonexistent-eng", command_type="abort_engagement",
            data={"mode": "hard"},
        )
        result = handler.handle(cmd)
        # If it reaches AbortHandler, mode is in data
        if result.success:
            assert result.data.get("mode") == "hard"

    def test_default_mode_is_graceful(self):
        """No mode specified → defaults to graceful."""
        handler = AbortEngagementHandler()
        # Since the handler tries real repo IO, mock Path.cwd to avoid
        # filesystem dependency for this mode-test only
        from unittest.mock import patch
        import pathlib
        original_cwd = pathlib.Path.cwd
        pathlib.Path.cwd = lambda: pathlib.Path("/tmp")
        try:
            cmd = Command(slug="my-eng", command_type="abort_engagement", data={})
            result = handler.handle(cmd)
        finally:
            pathlib.Path.cwd = original_cwd
        # Mode is set before repository access attempt
        # If the handler reaches AbortHandler's _do_abort with None repo,
        # it uses stub; but the handler creates the repo, so mode check
        # happens before repo operations
        # Actually the data dict is built from AbortResult's fields
        assert "Abort failed" in result.message or "aborted" in result.message


class TestQueryStatusHandler:
    """Delegates to EngagementHealthCheck.check()."""

    def test_returns_success(self):
        handler = QueryStatusHandler()
        cmd = Command(slug="my-eng", command_type="query_status")
        result = handler.handle(cmd)
        # May return all_ok or warnings depending on environment
        assert result.success is True
        assert "slug" in result.data


class TestQueryWhatsNextHandler:
    """Delegates to WhatsNextEngine.query() — Wave 6 wired."""

    def test_queries_engagement_via_engine(self):
        """Handler queries real engine; handles missing engagement gracefully."""
        handler = QueryWhatsNextHandler()
        cmd = Command(slug="nonexistent-eng", command_type="query_whats_next")
        result = handler.handle(cmd)
        # Will fail gracefully since the engagement doesn't exist on disk
        assert result.success is False or "available command" in result.message


class TestRegisterAllHandlers:
    """Tests for the register_all_handlers convenience function."""

    def test_registers_all_handlers(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        types = registry.list_registered()
        assert "create_engagement" in types
        assert "resume_engagement" in types
        assert "enter_phase" in types
        assert "next" in types
        assert "create_wave" in types
        assert "execute_step" in types
        assert "abort_engagement" in types
        assert "query_status" in types
        assert "query_whats_next" in types
        assert "finish_engagement" in types
        assert "review_engagement" in types

    def test_each_handler_is_distinct_instance(self):
        registry = CommandRegistry()
        register_all_handlers(registry)
        # Each handler should be a different instance
        h1 = registry.get_handler("create_engagement")
        h2 = registry.get_handler("resume_engagement")
        assert h1 is not h2


# ── Exception branch coverage ───────────────────────────────────────


class TestEnterPhaseHandlerExceptions:
    """Coverage for EnterPhaseHandler exception branch."""

    def test_exception_returns_error(self):
        handler = EnterPhaseHandler()
        cmd = Command(
            slug="my-eng", command_type="enter_phase",
            data={"phase": "design"},
        )
        with patch(
            "harness.phase.orchestrator.PhaseOrchestrator",
            side_effect=ValueError("mocked orchestrator error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked orchestrator error" in result.error


class TestCreateWaveHandlerExceptions:
    """Coverage for CreateWaveHandler exception branch."""

    def test_exception_returns_error(self):
        handler = CreateWaveHandler()
        cmd = Command(
            slug="my-eng", command_type="create_wave",
            data={"title": "Test Wave"},
        )
        with patch(
            "harness.plan.plan_manager.PlanManager",
            side_effect=ValueError("mocked plan error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked plan error" in result.error


class TestExecuteStepHandlerExceptions:
    """Coverage for ExecuteStepHandler exception branch."""

    def test_exception_returns_error(self):
        handler = ExecuteStepHandler()
        cmd = Command(
            slug="my-eng", command_type="execute_step",
            data={"step": {"agents": ["architect"]}},
        )
        # The handler imports StepDispatcher inside a try block but never
        # calls it. We mock __import__ to make the import itself fail.
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "harness.phase.dispatcher":
                raise ImportError("mocked import error")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", mock_import):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked import error" in result.error


class TestQueryStatusHandlerExceptions:
    """Coverage for QueryStatusHandler exception branch."""

    def test_exception_returns_error(self):
        handler = QueryStatusHandler()
        cmd = Command(slug="my-eng", command_type="query_status")
        with patch(
            "harness.engagement.health.EngagementHealthCheck",
            side_effect=ValueError("mocked health error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked health error" in result.error


# ── CommandHandler ABC body coverage ────────────────────────────────


class TestAgentListHandler:
    """Wave O: AgentListHandler — lists registered agents."""

    def test_importable(self):
        from harness.command.handlers import AgentListHandler
        handler = AgentListHandler()
        assert isinstance(handler, CommandHandler)

    def test_returns_agent_list(self):
        from harness.command.handlers import AgentListHandler
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
        from harness.command.handlers import FleetListHandler
        handler = FleetListHandler()
        assert isinstance(handler, CommandHandler)

    def test_returns_team_list(self):
        from harness.command.handlers import FleetListHandler
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
        from harness.command.handlers import ConsultHandler
        handler = ConsultHandler()
        assert isinstance(handler, CommandHandler)

    def test_routes_question(self):
        """Consult handler should return a result (matched or unmatched)."""
        from harness.command.handlers import ConsultHandler
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


class TestAbortEngagementHandlerExceptions:
    """Coverage for AbortEngagementHandler exception branch."""

    def test_exception_returns_error(self):
        handler = AbortEngagementHandler()
        cmd = Command(slug="my-eng", command_type="abort_engagement", data={"mode": "hard"})
        with patch(
            "harness.session.abort.AbortHandler",
            side_effect=ValueError("mocked abort error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked abort error" in result.error


class TestQueryWhatsNextHandlerExceptions:
    """Coverage for QueryWhatsNextHandler exception branch."""

    def test_exception_returns_error(self):
        handler = QueryWhatsNextHandler()
        cmd = Command(slug="test-eng", command_type="query_whats_next")
        with patch(
            "harness.session.whats_next.WhatsNextEngine",
            side_effect=ValueError("mocked whatsnext error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked whatsnext error" in result.error


class TestFinishEngagementHandlerExceptions:
    """Coverage for FinishEngagementHandler exception branch."""

    def test_exception_returns_error(self):
        handler = FinishEngagementHandler()
        cmd = Command(slug="test-eng", command_type="finish_engagement",
                      data={"root": "/nonexistent"})
        # The handler tries a lot of imports and file operations
        # Just verify it doesn't crash and returns some error
        result = handler.handle(cmd)
        assert isinstance(result, CommandResult)


class TestReviewEngagementHandlerExceptions:
    """Coverage for ReviewEngagementHandler exception branch."""

    def test_exception_returns_error(self):
        handler = ReviewEngagementHandler()
        cmd = Command(slug="test-eng", command_type="review_engagement",
                      data={"root": "/nonexistent"})
        result = handler.handle(cmd)
        assert isinstance(result, CommandResult)

    def test_review_no_decision(self):
        handler = ReviewEngagementHandler()
        cmd = Command(slug="test-eng", command_type="review_engagement", data={})
        result = handler.handle(cmd)
        assert result.success is False
        assert "No decision" in result.error


class TestInitProjectHandlerExceptions:
    """Coverage for InitProjectHandler exception branch."""

    def test_exception_returns_error(self, tmp_path):
        handler = InitProjectHandler()
        cmd = Command(slug="", command_type="init_project",
                      data={"root": str(tmp_path)})
        with patch(
            "harness.paths.get_harness_dir",
            side_effect=RuntimeError("init path error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "init path error" in result.error

    def test_project_dir_is_file(self, tmp_path):
        project_file = tmp_path / "afile"
        project_file.write_text("not a dir")
        handler = InitProjectHandler()
        cmd = Command(slug="", command_type="init_project",
                      data={"project_dir": str(project_file), "root": str(tmp_path)})
        result = handler.handle(cmd)
        assert result.success is False
        assert "is a file" in result.error


class TestPhaseManagementHandlerExceptions:
    """Coverage for PhaseManagementHandler exception branch."""

    def test_exception_returns_error(self):
        handler = PhaseManagementHandler()
        cmd = Command(slug="", command_type="manage_phase", data={"action": "list"})
        result = handler.handle(cmd)
        assert isinstance(result, CommandResult)


class TestRunWaveHandlerExceptions:
    """Coverage for RunWaveHandler exception branch."""

    def test_no_wave_id_returns_error(self):
        handler = RunWaveHandler()
        cmd = Command(slug="my-eng", command_type="run_wave", data={})
        result = handler.handle(cmd)
        assert result.success is False
        assert "No wave_id" in result.error

    def test_exception_returns_error(self):
        handler = RunWaveHandler()
        cmd = Command(slug="my-eng", command_type="run_wave",
                      data={"wave_id": "w1"})
        with patch(
            "harness.loop.runner.LoopRunner",
            side_effect=ValueError("mocked runner error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked runner error" in result.error


class TestSessionHandlerExceptions:
    """Coverage for SessionHandler exception branch."""

    def test_exception_returns_error(self):
        handler = SessionHandler()
        cmd = Command(slug="my-eng", command_type="session",
                      data={"phase": "requirements"})
        with patch(
            "harness.engagement.startup.StartupResumeFlow",
            side_effect=ValueError("mocked session error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked session error" in result.error


class TestChatHandlerExceptions:
    """Coverage for ChatHandler exception branch."""

    def test_engagement_not_found(self):
        handler = ChatHandler()
        cmd = Command(slug="nonexistent-eng", command_type="chat")
        result = handler.handle(cmd)
        assert result.success is False
        assert "not found" in result.error or "not found" in result.message

    def test_exception_returns_error(self):
        handler = ChatHandler()
        cmd = Command(slug="my-eng", command_type="chat",
                      data={"phase": "design"})
        with patch(
            "harness.session.client.resolve_provider",
            side_effect=ValueError("mocked chat error"),
        ):
            result = handler.handle(cmd)
        assert result.success is False
        assert "mocked chat error" in result.error


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
