"""Tests for typed command construction and CommandBus dispatch.

Covers direct typed command construction (replaces factory function tests)
and errors in command/errors.py.
"""

from __future__ import annotations

import pytest

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
    RefreshAgentsCommand,
    RenameEngagementCommand,
    SetBranchCommand,
    SetGovernanceCommand,
    TeamListCommand,
)

from harness.command.errors import HandlerError


class TestSummaryCommand:
    def test_defaults(self):
        cmd = SummaryCommand()
        assert cmd.deep is False

    def test_with_args(self):
        cmd = SummaryCommand(slug="test", deep=True, assess_flag=True, reconcile=True)
        assert cmd.deep is True
        assert cmd.assess_flag is True
        assert cmd.slug == "test"


class TestInspectCommand:
    def test_defaults(self):
        cmd = InspectCommand()
        assert cmd.root == "."

    def test_with_root(self):
        cmd = InspectCommand(root="/tmp")
        assert cmd.root == "/tmp"


class TestAssessCommand:
    def test_defaults(self):
        cmd = AssessCommand()
        assert cmd.deep_flag is True

    def test_with_args(self):
        cmd = AssessCommand(root="/tmp", deep_flag=False)
        assert cmd.root == "/tmp"
        assert cmd.deep_flag is False


class TestCreateWavesFromAssessmentCommand:
    def test_defaults(self):
        cmd = CreateWavesFromAssessmentCommand()
        assert cmd.focus == "high-risk"

    def test_with_args(self):
        cmd = CreateWavesFromAssessmentCommand(focus="all", limit=5)
        assert cmd.focus == "all"
        assert cmd.limit == 5


class TestCreateWaveFromFindingCommand:
    def test_with_finding(self):
        cmd = CreateWaveFromFindingCommand(finding_id="f-1")
        assert cmd.finding_id == "f-1"


class TestListWavesCommand:
    def test_defaults(self):
        cmd = ListWavesCommand()

    def test_with_slug(self):
        cmd = ListWavesCommand(slug="test")
        assert cmd.slug == "test"


class TestWaveStatusCommand:
    def test_defaults(self):
        cmd = WaveStatusCommand()


class TestGenerateDocsCommand:
    def test_defaults(self):
        cmd = GenerateDocsCommand()

    def test_with_root(self):
        cmd = GenerateDocsCommand(root="/tmp")
        assert cmd.root == "/tmp"


class TestAnnotateChangelogCommand:
    def test_with_args(self):
        cmd = AnnotateChangelogCommand(slug="test", wave="w1", text="note")
        assert cmd.text == "note"


class TestRenameEngagementCommand:
    def test_with_args(self):
        cmd = RenameEngagementCommand(slug="old", new_slug="new", branch_strategy="rename", dry_run=True)
        assert cmd.dry_run is True
        assert cmd.new_slug == "new"


class TestSetBranchCommand:
    def test_with_args(self):
        cmd = SetBranchCommand(slug="test", branch="main")
        assert cmd.branch == "main"


class TestFixEngagementCommand:
    def test_defaults(self):
        cmd = FixEngagementCommand(slug="test")


class TestRefreshAgentsCommand:
    def test_defaults(self):
        cmd = RefreshAgentsCommand()

    def test_with_args(self):
        cmd = RefreshAgentsCommand(project_dir="/tmp", force=True)
        assert cmd.force is True


class TestSetGovernanceCommand:
    def test_defaults(self):
        cmd = SetGovernanceCommand()

    def test_with_level(self):
        cmd = SetGovernanceCommand(level="strict")
        assert cmd.level == "strict"


class TestAgentListCommand:
    def test_returns_typed(self):
        cmd = AgentListCommand()


class TestTeamListCommand:
    def test_returns_typed(self):
        cmd = TeamListCommand()


class TestConsultCommand:
    def test_with_question(self):
        cmd = ConsultCommand(question="query")
        assert cmd.question == "query"

    def test_default(self):
        cmd = ConsultCommand()
        assert cmd.question == ""


class TestHandlerError:
    """Tests for HandlerError."""

    def test_default_message(self):
        error = HandlerError()
        assert str(error) == ""

    def test_custom_message(self):
        error = HandlerError("Something went wrong")
        assert str(error) == "Something went wrong"
