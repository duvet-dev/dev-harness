"""Additional tests for CLI command factories.

Tests the typed command factory functions from harness.cli.commands.
"""

from __future__ import annotations


class TestAllFactories:
    """Tests that all factory functions produce correct typed commands."""

    def test_assess_command_args(self):
        from harness.cli.commands import assess_command
        cmd = assess_command(root="/tmp", deep_flag=False)
        assert cmd.root == "/tmp"
        assert cmd.deep_flag is False

    def test_create_wave_from_finding_args(self):
        from harness.cli.commands import create_wave_from_finding_command
        cmd = create_wave_from_finding_command(finding_id="find-123", slug="eng")
        assert cmd.finding_id == "find-123"
        assert cmd.slug == "eng"

    def test_rename_engagement_args(self):
        from harness.cli.commands import rename_engagement_command
        cmd = rename_engagement_command(old_slug="old", new_slug="new", branch_strategy="rename", dry_run=True)
        assert cmd.new_slug == "new"
        assert cmd.dry_run is True
        assert cmd.branch_strategy == "rename"

    def test_set_branch_args(self):
        from harness.cli.commands import set_branch_command
        cmd = set_branch_command(slug="eng", branch="feature/x")
        assert cmd.branch == "feature/x"

    def test_refresh_agents_args(self):
        from harness.cli.commands import refresh_agents_command
        cmd = refresh_agents_command(project_dir="/tmp", force=True)
        assert cmd.project_dir == "/tmp"
        assert cmd.force is True

    def test_set_governance_args(self):
        from harness.cli.commands import set_governance_command
        cmd = set_governance_command(level="strict", slug="eng")
        assert cmd.level == "strict"
        assert cmd.slug == "eng"

    def test_consult_args(self):
        from harness.cli.commands import consult_command
        cmd = consult_command(question="test query")
        assert cmd.question == "test query"

    def test_annotate_changelog_args(self):
        from harness.cli.commands import annotate_changelog_command
        cmd = annotate_changelog_command(slug="eng", wave="w1", text="note")
        assert cmd.text == "note"
        assert cmd.wave == "w1"

    def test_generate_docs_args(self):
        from harness.cli.commands import generate_docs_command
        cmd = generate_docs_command(root="/tmp")
        assert cmd.root == "/tmp"
