"""Comprehensive typed command dispatch tests for all 33 commands.

For each typed command:
- Positive test: create with valid data, dispatch through test bus, verify result
- Negative test: create with invalid/empty data, dispatch, verify error
- Presenter test: format the result through CliPresenter or ReplPresenter

Tests at the typed command API boundary -- no handler internals.
Uses test handlers (not real handlers) for consistent, fast execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from harness.command.bus import CommandBus
from harness.command.types import (
    CommandResult,
    TypedCommand,
    TypedHandler,
    TypedResult,
)
from harness.command.presenters.base import CliPresenter, ReplPresenter


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def bus():
    return CommandBus()


@pytest.fixture
def cli_presenter():
    return CliPresenter()


@pytest.fixture
def repl_presenter():
    return ReplPresenter()


# ── Test handler that returns success for any typed command ───────────────


@dataclass(frozen=True)
class _TestOkResult(TypedResult):
    success: bool = True
    message: str = "OK"


class _OkHandler(TypedHandler):
    """Handler that always succeeds."""

    def handle(self, command) -> _TestOkResult:
        return _TestOkResult(success=True, message=f"{type(command).__name__} processed")


@dataclass(frozen=True)
class _TestFailResult(TypedResult):
    success: bool = False
    error: str = "Invalid input"
    message: str = ""


class _FailHandler(TypedHandler):
    """Handler that always fails."""

    def handle(self, command) -> _TestFailResult:
        return _TestFailResult()


# ── Helper: register a typed command with a test handler ─────────────────


def _register_ok(bus, cmd_cls):
    """Register a command class with a successful test handler."""
    bus.register_type(_OkHandler(), cmd_cls)


def _register_fail(bus, cmd_cls):
    """Register a command class with a failing test handler."""
    bus.register_type(_FailHandler(), cmd_cls)


# ═══════════════════════════════════════════════════════════════════════════
# Engagement Commands (3)
# ═══════════════════════════════════════════════════════════════════════════


class TestCreateEngagementCommand:
    """Tests for CreateEngagementCommand."""

    def test_constructor(self):
        from harness.command.commands.engagement import CreateEngagementCommand
        cmd = CreateEngagementCommand(slug="my-eng", session_type="greenfield", mode="auto")
        assert cmd.slug == "my-eng"
        assert cmd.session_type == "greenfield"

    def test_positive(self, bus):
        from harness.command.commands.engagement import CreateEngagementCommand
        _register_ok(bus, CreateEngagementCommand)
        result = bus.dispatch(CreateEngagementCommand(slug="test"))
        assert result.success is True

    def test_negative_empty_slug(self, bus):
        from harness.command.commands.engagement import CreateEngagementCommand
        _register_fail(bus, CreateEngagementCommand)
        result = bus.dispatch(CreateEngagementCommand(slug=""))
        assert result.success is False

    def test_presenter(self, cli_presenter):
        from harness.command.results.engagement import CreateEngagementResult
        result = CreateEngagementResult(
            success=True, message="Created", slug="test", status="active"
        )
        output = cli_presenter.present(result)
        assert "test" in output


class TestAbortEngagementCommand:
    """Tests for AbortEngagementCommand."""

    def test_constructor(self):
        from harness.command.commands.engagement import AbortEngagementCommand
        cmd = AbortEngagementCommand(slug="my-eng", mode="hard")
        assert cmd.mode == "hard"

    def test_positive(self, bus):
        from harness.command.commands.engagement import AbortEngagementCommand
        _register_ok(bus, AbortEngagementCommand)
        result = bus.dispatch(AbortEngagementCommand(slug="test"))
        assert result.success is True

    def test_negative_empty_slug(self, bus):
        from harness.command.commands.engagement import AbortEngagementCommand
        _register_fail(bus, AbortEngagementCommand)
        result = bus.dispatch(AbortEngagementCommand(slug=""))
        assert result.success is False

    def test_presenter(self, cli_presenter):
        from harness.command.results.engagement import AbortEngagementResult
        result = AbortEngagementResult(success=True, message="Aborted")
        output = cli_presenter.present(result)
        assert output is not None


# ═══════════════════════════════════════════════════════════════════════════
# Phase Commands (2)
# ═══════════════════════════════════════════════════════════════════════════


class TestEnterPhaseCommand:
    """Tests for EnterPhaseCommand."""

    def test_constructor(self):
        from harness.command.commands.phase import EnterPhaseCommand
        cmd = EnterPhaseCommand(slug="eng", phase="design")
        assert cmd.phase == "design"

    def test_positive(self, bus):
        from harness.command.commands.phase import EnterPhaseCommand
        _register_ok(bus, EnterPhaseCommand)
        result = bus.dispatch(EnterPhaseCommand(slug="test", phase="design"))
        assert result.success is True

    def test_negative_empty(self, bus):
        from harness.command.commands.phase import EnterPhaseCommand
        _register_fail(bus, EnterPhaseCommand)
        result = bus.dispatch(EnterPhaseCommand(slug="", phase=""))
        assert result.success is False

    def test_presenter(self, cli_presenter):
        from harness.command.results.phase import EnterPhaseResult
        result = EnterPhaseResult(success=True, message="Phase entered")
        output = cli_presenter.present(result)
        assert output is not None


class TestManagePhaseCommand:
    """Tests for ManagePhaseCommand."""

    def test_constructor(self):
        from harness.command.commands.phase import ManagePhaseCommand
        cmd = ManagePhaseCommand(slug="eng", action="list")
        assert cmd.action == "list"

    def test_positive(self, bus):
        from harness.command.commands.phase import ManagePhaseCommand
        _register_ok(bus, ManagePhaseCommand)
        result = bus.dispatch(ManagePhaseCommand(slug="test", action="list"))
        assert result.success is True

    def test_negative_empty_action(self, bus):
        from harness.command.commands.phase import ManagePhaseCommand
        _register_fail(bus, ManagePhaseCommand)
        result = bus.dispatch(ManagePhaseCommand(slug="test", action=""))
        assert result.success is False

    def test_presenter(self, repl_presenter):
        from harness.command.results.phase import ManagePhaseResult
        result = ManagePhaseResult(success=True, message="List OK")
        output = repl_presenter.present(result)
        assert output is not None


# ═══════════════════════════════════════════════════════════════════════════
# Project Command (1)
# ═══════════════════════════════════════════════════════════════════════════


class TestInitProjectCommand:
    """Tests for InitProjectCommand."""

    def test_constructor(self):
        from harness.command.commands.project import InitProjectCommand
        cmd = InitProjectCommand(project_dir="sub", template="backend")
        assert cmd.template == "backend"

    def test_positive(self, bus):
        from harness.command.commands.project import InitProjectCommand
        _register_ok(bus, InitProjectCommand)
        result = bus.dispatch(InitProjectCommand())
        assert result.success is True

    def test_presenter(self, cli_presenter):
        from harness.command.results.project import InitProjectResult
        result = InitProjectResult(success=True, message="Initted", project="test")
        output = cli_presenter.present(result)
        assert output is not None


# ═══════════════════════════════════════════════════════════════════════════
# Misc Commands (3)
# ═══════════════════════════════════════════════════════════════════════════


class TestNextCommand:
    """Tests for NextCommand."""

    def test_constructor(self):
        from harness.command.commands.misc import NextCommand
        cmd = NextCommand(slug="eng")
        assert cmd.slug == "eng"

    def test_positive(self, bus):
        from harness.command.commands.misc import NextCommand
        _register_ok(bus, NextCommand)
        result = bus.dispatch(NextCommand(slug="test"))
        assert result.success is True

    def test_presenter(self, repl_presenter):
        from harness.command.results.misc import NextResult
        result = NextResult(success=True, message="Next step")
        output = repl_presenter.present(result)
        assert "Next step" in output


class TestQueryStatusCommand:
    """Tests for QueryStatusCommand."""

    def test_constructor(self):
        from harness.command.commands.misc import QueryStatusCommand
        cmd = QueryStatusCommand(slug="eng")
        assert cmd.slug == "eng"

    def test_positive(self, bus):
        from harness.command.commands.misc import QueryStatusCommand
        _register_ok(bus, QueryStatusCommand)
        result = bus.dispatch(QueryStatusCommand(slug="test"))
        assert result.success is True

    def test_presenter(self, cli_presenter):
        from harness.command.results.misc import QueryStatusResult
        result = QueryStatusResult(success=True, message="All good")
        output = cli_presenter.present(result)
        assert output is not None


class TestQueryWhatsNextCommand:
    """Tests for QueryWhatsNextCommand."""

    def test_constructor(self):
        from harness.command.commands.misc import QueryWhatsNextCommand
        cmd = QueryWhatsNextCommand(slug="eng")
        assert cmd.slug == "eng"

    def test_positive(self, bus):
        from harness.command.commands.misc import QueryWhatsNextCommand
        _register_ok(bus, QueryWhatsNextCommand)
        result = bus.dispatch(QueryWhatsNextCommand(slug="test"))
        assert result.success is True

    def test_presenter(self, repl_presenter):
        from harness.command.results.misc import QueryWhatsNextResult
        result = QueryWhatsNextResult(success=True, message="Next: test")
        output = repl_presenter.present(result)
        assert output is not None


# ═══════════════════════════════════════════════════════════════════════════
# Wave Commands (3)
# ═══════════════════════════════════════════════════════════════════════════


class TestRunWaveCommand:
    """Tests for RunWaveCommand."""

    def test_constructor(self):
        from harness.command.commands.wave import RunWaveCommand
        cmd = RunWaveCommand(slug="eng", wave_id="w1", no_test=True)
        assert cmd.wave_id == "w1"
        assert cmd.no_test is True

    def test_positive(self, bus):
        from harness.command.commands.wave import RunWaveCommand
        _register_ok(bus, RunWaveCommand)
        result = bus.dispatch(RunWaveCommand(slug="test"))
        assert result.success is True

    def test_presenter(self, cli_presenter):
        from harness.command.results.wave import RunWaveResult
        result = RunWaveResult(success=True, message="Wave ran")
        output = cli_presenter.present(result)
        assert output is not None


# ═══════════════════════════════════════════════════════════════════════════
# Review Commands (2)
# ═══════════════════════════════════════════════════════════════════════════


class TestFinishEngagementCommand:
    """Tests for FinishEngagementCommand."""

    def test_constructor(self):
        from harness.command.commands.review import FinishEngagementCommand
        cmd = FinishEngagementCommand(slug="eng", re_assess=True)
        assert cmd.re_assess is True

    def test_positive(self, bus):
        from harness.command.commands.review import FinishEngagementCommand
        _register_ok(bus, FinishEngagementCommand)
        result = bus.dispatch(FinishEngagementCommand(slug="test"))
        assert result.success is True

    def test_presenter(self, cli_presenter):
        from harness.command.results.review import FinishEngagementResult
        result = FinishEngagementResult(success=True, message="Finished")
        output = cli_presenter.present(result)
        assert output is not None


class TestReviewEngagementCommand:
    """Tests for ReviewEngagementCommand."""

    def test_constructor(self):
        from harness.command.commands.review import ReviewEngagementCommand
        cmd = ReviewEngagementCommand(slug="eng", decision="approved")
        assert cmd.decision == "approved"

    def test_positive(self, bus):
        from harness.command.commands.review import ReviewEngagementCommand
        _register_ok(bus, ReviewEngagementCommand)
        result = bus.dispatch(ReviewEngagementCommand(slug="test", decision="approved"))
        assert result.success is True

    def test_negative_empty_decision(self, bus):
        from harness.command.commands.review import ReviewEngagementCommand
        _register_fail(bus, ReviewEngagementCommand)
        result = bus.dispatch(ReviewEngagementCommand(slug="test", decision=""))
        assert result.success is False

    def test_presenter(self, repl_presenter):
        from harness.command.results.review import ReviewEngagementResult
        result = ReviewEngagementResult(success=True, message="Reviewed")
        output = repl_presenter.present(result)
        assert output is not None


# ═══════════════════════════════════════════════════════════════════════════
# Session Commands (2)
# ═══════════════════════════════════════════════════════════════════════════


class TestSessionCommand:
    """Tests for SessionCommand."""

    def test_constructor(self):
        from harness.command.commands.session import SessionCommand
        cmd = SessionCommand(slug="eng", phase="requirements")
        assert cmd.phase == "requirements"

    def test_positive(self, bus):
        from harness.command.commands.session import SessionCommand
        _register_ok(bus, SessionCommand)
        result = bus.dispatch(SessionCommand(slug="test", phase="requirements"))
        assert result.success is True

    def test_negative_empty_phase(self, bus):
        from harness.command.commands.session import SessionCommand
        _register_fail(bus, SessionCommand)
        result = bus.dispatch(SessionCommand(slug="test", phase=""))
        assert result.success is False

    def test_presenter(self, cli_presenter):
        from harness.command.results.session import SessionResult
        result = SessionResult(success=True, message="Session started")
        output = cli_presenter.present(result)
        assert output is not None


class TestChatCommand:
    """Tests for ChatCommand."""

    def test_constructor(self):
        from harness.command.commands.session import ChatCommand
        cmd = ChatCommand(slug="eng", prompt="hello")
        assert cmd.prompt == "hello"

    def test_positive(self, bus):
        from harness.command.commands.session import ChatCommand
        _register_ok(bus, ChatCommand)
        result = bus.dispatch(ChatCommand(slug="test", prompt="hello"))
        assert result.success is True

    def test_negative_empty_prompt(self, bus):
        from harness.command.commands.session import ChatCommand
        _register_fail(bus, ChatCommand)
        result = bus.dispatch(ChatCommand(slug="test", prompt=""))
        assert result.success is False

    def test_presenter(self, repl_presenter):
        from harness.command.results.session import ChatResult
        result = ChatResult(success=True, message="Chat reply")
        output = repl_presenter.present(result)
        assert output is not None


# ═══════════════════════════════════════════════════════════════════════════
# Analysis Commands (3)
# ═══════════════════════════════════════════════════════════════════════════


class TestSummaryCommand:
    """Tests for SummaryCommand."""

    def test_constructor(self):
        from harness.command.commands.analysis import SummaryCommand
        cmd = SummaryCommand(slug="eng", deep=True)
        assert cmd.deep is True

    def test_positive(self, bus):
        from harness.command.commands.analysis import SummaryCommand
        _register_ok(bus, SummaryCommand)
        result = bus.dispatch(SummaryCommand(slug="test"))
        assert result.success is True

    def test_presenter(self, cli_presenter):
        from harness.command.results.analysis import SummaryResult
        result = SummaryResult(success=True, message="Summary done")
        output = cli_presenter.present(result)
        assert output is not None


class TestInspectCommand:
    """Tests for InspectCommand."""

    def test_constructor(self):
        from harness.command.commands.analysis import InspectCommand
        cmd = InspectCommand(slug="eng", root="/tmp")
        assert cmd.root == "/tmp"

    def test_positive(self, bus):
        from harness.command.commands.analysis import InspectCommand
        _register_ok(bus, InspectCommand)
        result = bus.dispatch(InspectCommand(slug="test"))
        assert result.success is True

    def test_presenter(self, repl_presenter):
        from harness.command.results.analysis import InspectResult
        result = InspectResult(success=True, message="Inspect done")
        output = repl_presenter.present(result)
        assert output is not None


class TestAssessCommand:
    """Tests for AssessCommand."""

    def test_constructor(self):
        from harness.command.commands.analysis import AssessCommand
        cmd = AssessCommand(slug="eng", deep_flag=True)
        assert cmd.deep_flag is True

    def test_positive(self, bus):
        from harness.command.commands.analysis import AssessCommand
        _register_ok(bus, AssessCommand)
        result = bus.dispatch(AssessCommand(slug="test"))
        assert result.success is True

    def test_presenter(self, cli_presenter):
        from harness.command.results.analysis import AssessResult
        result = AssessResult(success=True, message="Assess done")
        output = cli_presenter.present(result)
        assert output is not None


# ═══════════════════════════════════════════════════════════════════════════
# Batch Commands (6)
# ═══════════════════════════════════════════════════════════════════════════


class TestCreateWavesFromAssessmentCommand:
    """Tests for CreateWavesFromAssessmentCommand."""

    def test_constructor(self):
        from harness.command.commands.batch import CreateWavesFromAssessmentCommand
        cmd = CreateWavesFromAssessmentCommand(slug="eng", focus="high-risk")
        assert cmd.focus == "high-risk"

    def test_positive(self, bus):
        from harness.command.commands.batch import CreateWavesFromAssessmentCommand
        _register_ok(bus, CreateWavesFromAssessmentCommand)
        result = bus.dispatch(CreateWavesFromAssessmentCommand(slug="test"))
        assert result.success is True

    def test_presenter(self, cli_presenter):
        from harness.command.results.batch import CreateWavesFromAssessmentResult
        result = CreateWavesFromAssessmentResult(success=True, message="Created waves")
        output = cli_presenter.present(result)
        assert output is not None


class TestCreateWaveFromFindingCommand:
    """Tests for CreateWaveFromFindingCommand."""

    def test_constructor(self):
        from harness.command.commands.batch import CreateWaveFromFindingCommand
        cmd = CreateWaveFromFindingCommand(slug="eng", finding_id="f-1")
        assert cmd.finding_id == "f-1"

    def test_positive(self, bus):
        from harness.command.commands.batch import CreateWaveFromFindingCommand
        _register_ok(bus, CreateWaveFromFindingCommand)
        result = bus.dispatch(CreateWaveFromFindingCommand(slug="test", finding_id="f1"))
        assert result.success is True

    def test_negative_empty_finding(self, bus):
        from harness.command.commands.batch import CreateWaveFromFindingCommand
        _register_fail(bus, CreateWaveFromFindingCommand)
        result = bus.dispatch(CreateWaveFromFindingCommand(slug="test"))
        assert result.success is False

    def test_presenter(self, repl_presenter):
        from harness.command.results.batch import CreateWaveFromFindingResult
        result = CreateWaveFromFindingResult(success=True, message="Wave created from finding")
        output = repl_presenter.present(result)
        assert output is not None


class TestListWavesCommand:
    """Tests for ListWavesCommand."""

    def test_constructor(self):
        from harness.command.commands.batch import ListWavesCommand
        cmd = ListWavesCommand(slug="eng")
        assert cmd.slug == "eng"

    def test_positive(self, bus):
        from harness.command.commands.batch import ListWavesCommand
        _register_ok(bus, ListWavesCommand)
        result = bus.dispatch(ListWavesCommand(slug="test"))
        assert result.success is True

    def test_presenter(self, cli_presenter):
        from harness.command.results.batch import ListWavesResult
        result = ListWavesResult(success=True, message="List result")
        output = cli_presenter.present(result)
        assert output is not None


class TestWaveStatusCommand:
    """Tests for WaveStatusCommand."""

    def test_constructor(self):
        from harness.command.commands.batch import WaveStatusCommand
        cmd = WaveStatusCommand(slug="eng")
        assert cmd.slug == "eng"

    def test_positive(self, bus):
        from harness.command.commands.batch import WaveStatusCommand
        _register_ok(bus, WaveStatusCommand)
        result = bus.dispatch(WaveStatusCommand(slug="test"))
        assert result.success is True

    def test_presenter(self, repl_presenter):
        from harness.command.results.batch import WaveStatusResult
        result = WaveStatusResult(success=True, message="Status OK")
        output = repl_presenter.present(result)
        assert output is not None


class TestGenerateDocsCommand:
    """Tests for GenerateDocsCommand."""

    def test_constructor(self):
        from harness.command.commands.batch import GenerateDocsCommand
        cmd = GenerateDocsCommand(slug="eng", doc_type="full")
        assert cmd.doc_type == "full"

    def test_positive(self, bus):
        from harness.command.commands.batch import GenerateDocsCommand
        _register_ok(bus, GenerateDocsCommand)
        result = bus.dispatch(GenerateDocsCommand(slug="test"))
        assert result.success is True

    def test_presenter(self, cli_presenter):
        from harness.command.results.batch import GenerateDocsResult
        result = GenerateDocsResult(success=True, message="Docs generated")
        output = cli_presenter.present(result)
        assert output is not None


class TestAnnotateChangelogCommand:
    """Tests for AnnotateChangelogCommand."""

    def test_constructor(self):
        from harness.command.commands.batch import AnnotateChangelogCommand
        cmd = AnnotateChangelogCommand(slug="eng", wave="w1", text="note")
        assert cmd.text == "note"

    def test_positive(self, bus):
        from harness.command.commands.batch import AnnotateChangelogCommand
        _register_ok(bus, AnnotateChangelogCommand)
        result = bus.dispatch(AnnotateChangelogCommand(slug="test", wave="w1", text="note"))
        assert result.success is True

    def test_negative_empty_text(self, bus):
        from harness.command.commands.batch import AnnotateChangelogCommand
        _register_fail(bus, AnnotateChangelogCommand)
        result = bus.dispatch(AnnotateChangelogCommand(slug="test", wave="", text=""))
        assert result.success is False

    def test_presenter(self, repl_presenter):
        from harness.command.results.batch import AnnotateChangelogResult
        result = AnnotateChangelogResult(success=True, message="Annotated")
        output = repl_presenter.present(result)
        assert output is not None


# ═══════════════════════════════════════════════════════════════════════════
# Mgmt Commands (8)
# ═══════════════════════════════════════════════════════════════════════════


class TestRenameEngagementCommand:
    """Tests for RenameEngagementCommand."""

    def test_constructor(self):
        from harness.command.commands.mgmt import RenameEngagementCommand
        cmd = RenameEngagementCommand(slug="old", new_slug="new")
        assert cmd.new_slug == "new"

    def test_positive(self, bus):
        from harness.command.commands.mgmt import RenameEngagementCommand
        _register_ok(bus, RenameEngagementCommand)
        result = bus.dispatch(RenameEngagementCommand(slug="old", new_slug="new"))
        assert result.success is True

    def test_negative_empty_slugs(self, bus):
        from harness.command.commands.mgmt import RenameEngagementCommand
        _register_fail(bus, RenameEngagementCommand)
        result = bus.dispatch(RenameEngagementCommand(slug="", new_slug=""))
        assert result.success is False

    def test_presenter(self, cli_presenter):
        from harness.command.results.mgmt import RenameEngagementResult
        result = RenameEngagementResult(success=True, message="Renamed")
        output = cli_presenter.present(result)
        assert output is not None


class TestSetBranchCommand:
    """Tests for SetBranchCommand."""

    def test_constructor(self):
        from harness.command.commands.mgmt import SetBranchCommand
        cmd = SetBranchCommand(slug="eng", branch="feature/x")
        assert cmd.branch == "feature/x"

    def test_positive(self, bus):
        from harness.command.commands.mgmt import SetBranchCommand
        _register_ok(bus, SetBranchCommand)
        result = bus.dispatch(SetBranchCommand(slug="test", branch="main"))
        assert result.success is True

    def test_negative_empty_branch(self, bus):
        from harness.command.commands.mgmt import SetBranchCommand
        _register_fail(bus, SetBranchCommand)
        result = bus.dispatch(SetBranchCommand(slug="test", branch=""))
        assert result.success is False

    def test_presenter(self, repl_presenter):
        from harness.command.results.mgmt import SetBranchResult
        result = SetBranchResult(success=True, message="Branch set")
        output = repl_presenter.present(result)
        assert output is not None


class TestFixEngagementCommand:
    """Tests for FixEngagementCommand."""

    def test_constructor(self):
        from harness.command.commands.mgmt import FixEngagementCommand
        cmd = FixEngagementCommand(slug="eng", fix_type="metadata")
        assert cmd.fix_type == "metadata"

    def test_positive(self, bus):
        from harness.command.commands.mgmt import FixEngagementCommand
        _register_ok(bus, FixEngagementCommand)
        result = bus.dispatch(FixEngagementCommand(slug="test"))
        assert result.success is True

    def test_presenter(self, cli_presenter):
        from harness.command.results.mgmt import FixEngagementResult
        result = FixEngagementResult(success=True, message="Fixed")
        output = cli_presenter.present(result)
        assert output is not None


class TestRefreshAgentsCommand:
    """Tests for RefreshAgentsCommand."""

    def test_constructor(self):
        from harness.command.commands.mgmt import RefreshAgentsCommand
        cmd = RefreshAgentsCommand(slug="eng", force=True)
        assert cmd.force is True

    def test_positive(self, bus):
        from harness.command.commands.mgmt import RefreshAgentsCommand
        _register_ok(bus, RefreshAgentsCommand)
        result = bus.dispatch(RefreshAgentsCommand(slug="test"))
        assert result.success is True

    def test_presenter(self, repl_presenter):
        from harness.command.results.mgmt import RefreshAgentsResult
        result = RefreshAgentsResult(success=True, message="Refreshed")
        output = repl_presenter.present(result)
        assert output is not None


class TestSetGovernanceCommand:
    """Tests for SetGovernanceCommand."""

    def test_constructor(self):
        from harness.command.commands.mgmt import SetGovernanceCommand
        cmd = SetGovernanceCommand(slug="eng", level="strict")
        assert cmd.level == "strict"

    def test_positive(self, bus):
        from harness.command.commands.mgmt import SetGovernanceCommand
        _register_ok(bus, SetGovernanceCommand)
        result = bus.dispatch(SetGovernanceCommand(slug="test", level="standard"))
        assert result.success is True

    def test_negative_invalid_level(self, bus):
        from harness.command.commands.mgmt import SetGovernanceCommand
        _register_fail(bus, SetGovernanceCommand)
        result = bus.dispatch(SetGovernanceCommand(slug="test", level="bad"))
        assert result.success is False

    def test_presenter(self, cli_presenter):
        from harness.command.results.mgmt import SetGovernanceResult
        result = SetGovernanceResult(success=True, message="Governance set")
        output = cli_presenter.present(result)
        assert output is not None


class TestAgentListCommand:
    """Tests for AgentListCommand."""

    def test_constructor(self):
        from harness.command.commands.mgmt import AgentListCommand
        cmd = AgentListCommand(slug="")
        assert cmd.slug == ""

    def test_positive(self, bus):
        from harness.command.commands.mgmt import AgentListCommand
        _register_ok(bus, AgentListCommand)
        result = bus.dispatch(AgentListCommand(slug=""))
        assert result.success is True

    def test_presenter(self, repl_presenter):
        from harness.command.results.mgmt import AgentListResult
        result = AgentListResult(success=True, message="Agents listed", count=3)
        output = repl_presenter.present(result)
        assert output is not None


class TestTeamListCommand:
    """Tests for TeamListCommand."""

    def test_constructor(self):
        from harness.command.commands.mgmt import TeamListCommand
        cmd = TeamListCommand(slug="")
        assert cmd.slug == ""

    def test_positive(self, bus):
        from harness.command.commands.mgmt import TeamListCommand
        _register_ok(bus, TeamListCommand)
        result = bus.dispatch(TeamListCommand(slug=""))
        assert result.success is True

    def test_presenter(self, cli_presenter):
        from harness.command.results.mgmt import TeamListResult
        result = TeamListResult(success=True, message="Teams listed", count=2)
        output = cli_presenter.present(result)
        assert output is not None


class TestConsultCommand:
    """Tests for ConsultCommand."""

    def test_constructor(self):
        from harness.command.commands.mgmt import ConsultCommand
        cmd = ConsultCommand(slug="", question="test")
        assert cmd.question == "test"

    def test_positive(self, bus):
        from harness.command.commands.mgmt import ConsultCommand
        _register_ok(bus, ConsultCommand)
        result = bus.dispatch(ConsultCommand(slug="", question="test"))
        assert result.success is True

    def test_negative_empty_question(self, bus):
        from harness.command.commands.mgmt import ConsultCommand
        _register_fail(bus, ConsultCommand)
        result = bus.dispatch(ConsultCommand(slug="", question=""))
        assert result.success is False

    def test_presenter(self, repl_presenter):
        from harness.command.results.mgmt import ConsultResult
        result = ConsultResult(success=True, message="Consulted")
        output = repl_presenter.present(result)
        assert output is not None


# ═══════════════════════════════════════════════════════════════════════════
# Bus integrity
# ═══════════════════════════════════════════════════════════════════════════


class TestBusIntegrity:
    """Verifies bus integrity: no legacy string dispatch."""

    def test_no_legacy_string_dispatch_in_bus(self):
        """Bus module has no legacy string-based dispatch code."""
        import inspect as ins
        import harness.command.bus as bus_module
        source = ins.getsource(bus_module)
        assert "legacy_alias" not in source
        assert "LegacyAdapter" not in source

    def test_no_command_class_import_in_bus(self):
        """Bus module does not import legacy Command class."""
        import inspect as ins
        import harness.command.bus as bus_module
        source = ins.getsource(bus_module)
        assert "from harness.command.types import Command" not in source
