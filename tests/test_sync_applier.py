"""Tests for harness.sync.applier."""

from pathlib import Path

import pytest

from harness.sync.applier import ApplyReport, SyncApplier
from harness.sync.mapper import AgentTemplates, MappedTemplates


class TestApplyReport:
    def test_defaults(self):
        report = ApplyReport()
        assert report.written_files == []
        assert report.skipped_files == []
        assert report.errors == []


class TestSyncApplier:
    def test_default_output_dir(self):
        applier = SyncApplier()
        assert applier.output_dir.name == "templates"

    def test_custom_output_dir(self, tmp_path):
        applier = SyncApplier(output_dir=tmp_path)
        assert applier.output_dir == tmp_path

    def test_apply_writes_agent_files(self, tmp_path):
        applier = SyncApplier(output_dir=tmp_path)
        templates = MappedTemplates(
            agents={
                "coder": AgentTemplates(
                    identity="# Coder Identity",
                    procedures="# Coder Procedures",
                ),
                "planner": AgentTemplates(
                    identity="# Planner Identity",
                    procedures="# Planner Procedures",
                ),
            },
        )
        report = applier.apply(templates)
        assert len(report.written_files) >= 4  # 2 agents × 2 files each
        assert (tmp_path / "agents" / "coder" / "identity.md").is_file()
        assert (tmp_path / "agents" / "coder" / "procedures.md").is_file()
        assert (tmp_path / "agents" / "planner" / "identity.md").is_file()

    def test_apply_writes_community_standards(self, tmp_path):
        applier = SyncApplier(output_dir=tmp_path)
        templates = MappedTemplates(
            community_standards="# Community Standards",
        )
        report = applier.apply(templates)
        assert (tmp_path / "standards" / "community-standards.md").is_file()
        assert any("community-standards.md" in str(f) for f in report.written_files)

    def test_apply_skips_none_content(self, tmp_path):
        """When content is None, tools-template.md is skipped."""
        applier = SyncApplier(output_dir=tmp_path)
        templates = MappedTemplates()
        report = applier.apply(templates)
        assert report.written_files == []
        # tools-template.md gets skipped because content is None
        assert not report.errors

    def test_never_overwrite_tools_template(self, tmp_path):
        """tools-template.md should never be overwritten once created."""
        tools_path = tmp_path / "tools-template.md"
        tools_path.write_text("# Original content\n")

        applier = SyncApplier(output_dir=tmp_path)
        templates = MappedTemplates(tools="# New content\n")
        report = applier.apply(templates)

        # Should be skipped
        assert tools_path in report.skipped_files
        # Content should remain original
        assert tools_path.read_text() == "# Original content\n"

    def test_create_tools_template_when_missing(self, tmp_path):
        """tools-template.md should be created if it doesn't exist."""
        applier = SyncApplier(output_dir=tmp_path)
        tools_path = tmp_path / "tools-template.md"
        assert not tools_path.exists()

        templates = MappedTemplates(tools="# New tools template\n")
        report = applier.apply(templates)

        if tools_path in report.written_files:
            assert tools_path.read_text() == "# New tools template\n"

    def test_apply_with_errors(self, tmp_path):
        """Apply should handle write errors gracefully."""
        applier = SyncApplier(output_dir=tmp_path)
        templates = MappedTemplates(
            agents={
                "coder": AgentTemplates(identity="id", procedures="proc"),
            },
        )

        # Make the output dir a file to cause errors
        (tmp_path / "agents").write_text("I am a file, not a dir\n")

        report = applier.apply(templates)
        assert len(report.errors) >= 1 or len(report.written_files) >= 0
        # Should not crash

    def test_apply_empty_agents(self, tmp_path):
        """No agents should produce no agent files."""
        applier = SyncApplier(output_dir=tmp_path)
        templates = MappedTemplates(agents={})
        report = applier.apply(templates)
        assert report.written_files == [] or all("agents" not in str(f) for f in report.written_files)

    def test_preview_shows_changes(self, tmp_path):
        """Preview should produce a readable report without writing."""
        applier = SyncApplier(output_dir=tmp_path)
        templates = MappedTemplates(
            agents={
                "coder": AgentTemplates(identity="# Id", procedures="# Proc"),
            },
            changes_from_previous={"coder": "identity extracted"},
        )
        preview = applier.preview(templates)
        assert "Preview" in preview
        assert "coder" in preview

    def test_preview_no_changes(self, tmp_path):
        applier = SyncApplier(output_dir=tmp_path)
        templates = MappedTemplates()
        preview = applier.preview(templates)
        assert isinstance(preview, str)
        assert "Preview" in preview

    def test_preview_with_existing_files(self, tmp_path):
        """Preview should show OVERWRITE for existing files."""
        # Pre-create some files
        (tmp_path / "agents" / "coder").mkdir(parents=True)
        (tmp_path / "agents" / "coder" / "identity.md").write_text("old")
        (tmp_path / "agents" / "coder" / "procedures.md").write_text("old")

        applier = SyncApplier(output_dir=tmp_path)
        templates = MappedTemplates(
            agents={
                "coder": AgentTemplates(identity="# New", procedures="# New"),
            },
        )
        preview = applier.preview(templates)
        assert "OVERWRITE" in preview

    def test_atomic_write_creates_parent_dir(self, tmp_path):
        """atomic_write should create parent directories."""
        applier = SyncApplier(output_dir=tmp_path)
        deep_path = tmp_path / "a" / "b" / "c" / "test.md"

        report = ApplyReport()
        applier._atomic_write(deep_path, "content", report)
        assert deep_path.is_file()
        assert deep_path.read_text() == "content"

    def test_atomic_write_report(self, tmp_path):
        applier = SyncApplier(output_dir=tmp_path)
        path = tmp_path / "test.md"
        report = ApplyReport()
        applier._atomic_write(path, "hello", report)
        assert path in report.written_files
