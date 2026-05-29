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
    register_all_handlers,
)
from harness.command.registry import CommandRegistry
from harness.command.types import Command, CommandHandler, CommandResult


class TestCreateEngagementHandler:
    """Delegates to StartupResumeFlow.create() — stubbed."""

    def test_returns_success_stub(self):
        handler = CreateEngagementHandler()
        cmd = Command(slug="my-eng", command_type="create_engagement")
        result = handler.handle(cmd)
        assert result.success is True
        assert "creation requested" in result.message
        assert result.data["slug"] == "my-eng"
        assert result.data["status"] == "stub"

    def test_with_extra_data(self):
        handler = CreateEngagementHandler()
        cmd = Command(
            slug="my-eng", command_type="create_engagement",
            data={"workflow": "standard"},
        )
        result = handler.handle(cmd)
        assert result.success is True


class TestResumeEngagementHandler:
    """Delegates to StartupResumeFlow.resume() — stubbed."""

    def test_returns_success_stub(self):
        handler = ResumeEngagementHandler()
        cmd = Command(slug="my-eng", command_type="resume_engagement")
        result = handler.handle(cmd)
        assert result.success is True
        assert "resume requested" in result.message
        assert result.data["status"] == "stub"


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
    """Delegates to NextEngine.advance() — stubbed."""

    def test_returns_success_stub(self):
        handler = NextHandler()
        cmd = Command(slug="my-eng", command_type="next")
        result = handler.handle(cmd)
        assert result.success is True
        assert "advance requested" in result.message
        assert result.data["status"] == "stub"


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
    """Delegates to AbortHandler — stubbed."""

    def test_returns_success_stub_graceful(self):
        handler = AbortEngagementHandler()
        cmd = Command(
            slug="my-eng", command_type="abort_engagement",
            data={"mode": "graceful"},
        )
        result = handler.handle(cmd)
        assert result.success is True
        assert "Abort ('graceful') requested" in result.message

    def test_returns_success_stub_hard(self):
        handler = AbortEngagementHandler()
        cmd = Command(
            slug="my-eng", command_type="abort_engagement",
            data={"mode": "hard"},
        )
        result = handler.handle(cmd)
        assert result.success is True
        assert "Abort ('hard') requested" in result.message

    def test_default_mode_is_graceful(self):
        handler = AbortEngagementHandler()
        cmd = Command(slug="my-eng", command_type="abort_engagement", data={})
        result = handler.handle(cmd)
        assert result.data["mode"] == "graceful"


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
    """Delegates to WhatsNextEngine.query() — stubbed."""

    def test_returns_success_stub(self):
        handler = QueryWhatsNextHandler()
        cmd = Command(slug="my-eng", command_type="query_whats_next")
        result = handler.handle(cmd)
        assert result.success is True
        assert "Next-steps query" in result.message
        assert result.data["status"] == "stub"


class TestRegisterAllHandlers:
    """Tests for the register_all_handlers convenience function."""

    def test_registers_all_nine_handlers(self):
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
        assert len(types) == 9

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


class TestCommandHandlerAbstractBody:
    """Coverage for CommandHandler.handle() abstract body (line 66)."""

    def test_abstract_handle_body_via_super(self):
        """Calling the abstract handle body via super() returns None."""
        class _DirectHandler(CommandHandler):  # type: ignore[misc]
            def handle(self, command: Command) -> CommandResult:
                return super().handle(command)  # type: ignore[return-value]

        result = _DirectHandler().handle(Command(slug="test"))
        assert result is None
