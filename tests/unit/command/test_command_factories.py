"""Tests for CLI command factories and errors module.

Covers the factory functions in cli/commands.py and errors in command/errors.py.
"""

from __future__ import annotations

import pytest

from harness.cli.commands import (
    summary_command,
    inspect_command,
    assess_command,
    create_waves_from_assessment_command,
    create_wave_from_finding_command,
    list_waves_command,
    wave_status_command,
    generate_docs_command,
    annotate_changelog_command,
    rename_engagement_command,
    set_branch_command,
    fix_engagement_command,
    refresh_agents_command,
    set_governance_command,
    agent_list_command,
    fleet_list_command,
    consult_command,
)

from harness.command.errors import HandlerError


class TestSummaryCommandFactory:
    def test_defaults(self):
        cmd = summary_command()
        from harness.command.commands.analysis import SummaryCommand
        assert isinstance(cmd, SummaryCommand)
        assert cmd.deep is False

    def test_with_args(self):
        cmd = summary_command(deep=True, assess_flag=True, engagement="test", reconcile=True)
        assert cmd.deep is True
        assert cmd.assess_flag is True
        assert cmd.slug == "test"


class TestInspectCommandFactory:
    def test_defaults(self):
        cmd = inspect_command()
        from harness.command.commands.analysis import InspectCommand
        assert isinstance(cmd, InspectCommand)
        assert cmd.root == "."

    def test_with_root(self):
        cmd = inspect_command(root="/tmp")
        assert cmd.root == "/tmp"


class TestAssessCommandFactory:
    def test_defaults(self):
        cmd = assess_command()
        from harness.command.commands.analysis import AssessCommand
        assert isinstance(cmd, AssessCommand)

    def test_with_args(self):
        cmd = assess_command(root="/tmp", deep_flag=False)
        assert cmd.root == "/tmp"
        assert cmd.deep_flag is False


class TestCreateWavesFromAssessmentFactory:
    def test_defaults(self):
        cmd = create_waves_from_assessment_command()
        from harness.command.commands.batch import CreateWavesFromAssessmentCommand
        assert isinstance(cmd, CreateWavesFromAssessmentCommand)

    def test_with_args(self):
        cmd = create_waves_from_assessment_command(focus="all", limit=5)
        assert cmd.focus == "all"
        assert cmd.limit == 5


class TestCreateWaveFromFindingFactory:
    def test_with_finding(self):
        cmd = create_wave_from_finding_command(finding_id="f-1")
        from harness.command.commands.batch import CreateWaveFromFindingCommand
        assert isinstance(cmd, CreateWaveFromFindingCommand)
        assert cmd.finding_id == "f-1"


class TestListWavesFactory:
    def test_defaults(self):
        cmd = list_waves_command()
        from harness.command.commands.batch import ListWavesCommand
        assert isinstance(cmd, ListWavesCommand)

    def test_with_slug(self):
        cmd = list_waves_command(slug="test")
        assert cmd.slug == "test"


class TestWaveStatusFactory:
    def test_defaults(self):
        cmd = wave_status_command()
        from harness.command.commands.batch import WaveStatusCommand
        assert isinstance(cmd, WaveStatusCommand)


class TestGenerateDocsFactory:
    def test_defaults(self):
        cmd = generate_docs_command()
        from harness.command.commands.batch import GenerateDocsCommand
        assert isinstance(cmd, GenerateDocsCommand)

    def test_with_root(self):
        cmd = generate_docs_command(root="/tmp")
        assert cmd.root == "/tmp"


class TestAnnotateChangelogFactory:
    def test_with_args(self):
        cmd = annotate_changelog_command(slug="test", wave="w1", text="note")
        from harness.command.commands.batch import AnnotateChangelogCommand
        assert isinstance(cmd, AnnotateChangelogCommand)
        assert cmd.text == "note"


class TestRenameEngagementFactory:
    def test_with_args(self):
        cmd = rename_engagement_command(old_slug="old", new_slug="new", branch_strategy="rename", dry_run=True)
        from harness.command.commands.mgmt import RenameEngagementCommand
        assert isinstance(cmd, RenameEngagementCommand)
        assert cmd.dry_run is True
        assert cmd.new_slug == "new"


class TestSetBranchFactory:
    def test_with_args(self):
        cmd = set_branch_command(slug="test", branch="main")
        from harness.command.commands.mgmt import SetBranchCommand
        assert isinstance(cmd, SetBranchCommand)
        assert cmd.branch == "main"


class TestFixEngagementFactory:
    def test_defaults(self):
        cmd = fix_engagement_command(slug="test")
        from harness.command.commands.mgmt import FixEngagementCommand
        assert isinstance(cmd, FixEngagementCommand)


class TestRefreshAgentsFactory:
    def test_defaults(self):
        cmd = refresh_agents_command()
        from harness.command.commands.mgmt import RefreshAgentsCommand
        assert isinstance(cmd, RefreshAgentsCommand)

    def test_with_args(self):
        cmd = refresh_agents_command(project_dir="/tmp", force=True)
        assert cmd.force is True


class TestSetGovernanceFactory:
    def test_defaults(self):
        cmd = set_governance_command()
        from harness.command.commands.mgmt import SetGovernanceCommand
        assert isinstance(cmd, SetGovernanceCommand)

    def test_with_level(self):
        cmd = set_governance_command(level="strict")
        assert cmd.level == "strict"


class TestAgentListFactory:
    def test_returns_typed(self):
        cmd = agent_list_command()
        from harness.command.commands.mgmt import AgentListCommand
        assert isinstance(cmd, AgentListCommand)


class TestFleetListFactory:
    def test_returns_typed(self):
        cmd = fleet_list_command()
        from harness.command.commands.mgmt import FleetListCommand
        assert isinstance(cmd, FleetListCommand)


class TestConsultFactory:
    def test_with_question(self):
        cmd = consult_command(question="query")
        from harness.command.commands.mgmt import ConsultCommand
        assert isinstance(cmd, ConsultCommand)
        assert cmd.question == "query"

    def test_default(self):
        cmd = consult_command()
        assert cmd.question == ""


class TestHandlerError:
    """Tests for HandlerError."""

    def test_default_message(self):
        error = HandlerError()
        assert str(error) == ""

    def test_custom_message(self):
        error = HandlerError("Something went wrong")
        assert str(error) == "Something went wrong"
