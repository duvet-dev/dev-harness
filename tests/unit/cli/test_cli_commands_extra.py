"""Additional tests for typed command construction.

Tests direct construction of typed commands (replaces factory function tests).
"""

from __future__ import annotations


class TestAllTypedCommands:
    """Tests that all typed commands can be constructed correctly."""

    def test_assess_command_args(self):
        from harness.command.commands.analysis import AssessCommand
        cmd = AssessCommand(root="/tmp", deep_flag=False)
        assert cmd.root == "/tmp"
        assert cmd.deep_flag is False

    def test_create_wave_from_finding_args(self):
        from harness.command.commands.batch import CreateWaveFromFindingCommand
        cmd = CreateWaveFromFindingCommand(finding_id="find-123", slug="eng")
        assert cmd.finding_id == "find-123"
        assert cmd.slug == "eng"

    def test_rename_engagement_args(self):
        from harness.command.commands.mgmt import RenameEngagementCommand
        cmd = RenameEngagementCommand(slug="old", new_slug="new", branch_strategy="rename", dry_run=True)
        assert cmd.new_slug == "new"
        assert cmd.dry_run is True
        assert cmd.branch_strategy == "rename"

    def test_set_branch_args(self):
        from harness.command.commands.mgmt import SetBranchCommand
        cmd = SetBranchCommand(slug="eng", branch="feature/x")
        assert cmd.branch == "feature/x"

    def test_refresh_agents_args(self):
        from harness.command.commands.mgmt import RefreshAgentsCommand
        cmd = RefreshAgentsCommand(project_dir="/tmp", force=True)
        assert cmd.project_dir == "/tmp"
        assert cmd.force is True

    def test_set_governance_args(self):
        from harness.command.commands.mgmt import SetGovernanceCommand
        cmd = SetGovernanceCommand(level="strict", slug="eng")
        assert cmd.level == "strict"
        assert cmd.slug == "eng"

    def test_consult_args(self):
        from harness.command.commands.mgmt import ConsultCommand
        cmd = ConsultCommand(question="test query")
        assert cmd.question == "test query"

    def test_annotate_changelog_args(self):
        from harness.command.commands.batch import AnnotateChangelogCommand
        cmd = AnnotateChangelogCommand(slug="eng", wave="w1", text="note")
        assert cmd.text == "note"
        assert cmd.wave == "w1"

    def test_generate_docs_args(self):
        from harness.command.commands.batch import GenerateDocsCommand
        cmd = GenerateDocsCommand(root="/tmp")
        assert cmd.root == "/tmp"
