"""Tests for harness.sync.openclaw_extractor."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.sync.openclaw_extractor import ExtractionResult, OpenClawExtractor


class TestExtractionResult:
    def test_defaults(self):
        result = ExtractionResult()
        assert result.identities == {}
        assert result.procedures == {}
        assert result.community_standards is None
        assert result.tools is None
        assert result.agent_definitions == []
        assert result.sources_read == []


class TestOpenClawExtractor:
    def test_default_paths(self):
        extractor = OpenClawExtractor()
        assert "andy-personal" in str(extractor.openclaw_dir)
        assert "skills" in str(extractor.skills_dir)
        assert "AgentBrain" in str(extractor.vault_dir)

    def test_custom_paths(self, tmp_path):
        openclaw_path = tmp_path / "workspaces"
        skills_path = tmp_path / "skills"
        vault_path = tmp_path / "vault"

        extractor = OpenClawExtractor(
            openclaw_dir=str(openclaw_path),
            skills_dir=str(skills_path),
            vault_dir=str(vault_path),
        )
        assert extractor.openclaw_dir == openclaw_path
        assert extractor.skills_dir == skills_path
        assert extractor.vault_dir == vault_path

    def test_extract_all_empty_dirs(self, tmp_path):
        """Extraction from empty dirs should return empty results."""
        extractor = OpenClawExtractor(
            openclaw_dir=str(tmp_path / "workspaces"),
            skills_dir=str(tmp_path / "skills"),
            vault_dir=str(tmp_path / "vault"),
        )
        result = extractor.extract_all()
        assert result.identities == {}
        assert result.procedures == {}
        assert result.community_standards is None

    def test_extract_all_with_workspace_files(self, tmp_path):
        """Extraction should find SOUL.md and AGENTS.md in workspaces."""
        workspaces_root = tmp_path / "workspaces"
        workspaces_root.mkdir()
        # TOOLS.md must be at the openclaw_dir root, not inside agent subdir
        (workspaces_root / "TOOLS.md").write_text("# TOOLS content\n")
        agent_dir = workspaces_root / "andy-personal"
        agent_dir.mkdir()
        (agent_dir / "SOUL.md").write_text("# SOUL content\n")
        (agent_dir / "AGENTS.md").write_text("# AGENTS content\n")

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "community-standards.md").write_text("# Standards\n")

        vault_dir = tmp_path / "vault"
        vault_dir.mkdir(parents=True)

        extractor = OpenClawExtractor(
            openclaw_dir=str(workspaces_root),
            skills_dir=str(skills_dir),
            vault_dir=str(vault_dir),
        )
        result = extractor.extract_all()
        assert "andy-personal" in result.identities
        assert "andy-personal" in result.procedures
        assert result.community_standards is not None
        assert result.tools is not None

    def test_extract_all_multiple_workspaces(self, tmp_path):
        """Multiple workspace directories should each be extracted."""
        workspaces_dir = tmp_path / "workspaces"
        for name in ["agent-a", "agent-b", "agent-c"]:
            d = workspaces_dir / name
            d.mkdir(parents=True)
            (d / "SOUL.md").write_text(f"# {name} SOUL\n")
            (d / "AGENTS.md").write_text(f"# {name} AGENTS\n")

        extractor = OpenClawExtractor(
            openclaw_dir=str(workspaces_dir),
            skills_dir=str(tmp_path / "skills"),
            vault_dir=str(tmp_path / "vault"),
        )
        result = extractor.extract_all()
        assert len(result.identities) == 3
        assert len(result.procedures) == 3

    def test_extract_identity_missing(self, tmp_path):
        """Missing SOUL.md should return None."""
        extractor = OpenClawExtractor(
            openclaw_dir=str(tmp_path / "workspaces"),
        )
        result = extractor.extract_identity("nonexistent")
        assert result is None

    def test_extract_identity_present(self, tmp_path):
        workspace_dir = tmp_path / "workspaces" / "my-agent"
        workspace_dir.mkdir(parents=True)
        (workspace_dir / "SOUL.md").write_text("# My SOUL\n")

        extractor = OpenClawExtractor(
            openclaw_dir=str(workspace_dir.parent),
        )
        result = extractor.extract_identity("my-agent")
        assert result == "# My SOUL\n"

    def test_extract_procedures_missing(self, tmp_path):
        extractor = OpenClawExtractor(
            openclaw_dir=str(tmp_path / "workspaces"),
        )
        result = extractor.extract_procedures("nonexistent")
        assert result is None

    def test_extract_community_standards_from_skills(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "community-standards.md").write_text("# Standards\n")

        extractor = OpenClawExtractor(
            openclaw_dir=str(tmp_path / "workspaces"),
            skills_dir=str(skills_dir),
        )
        result = extractor.extract_community_standards()
        assert result is not None
        assert "Standards" in result

    def test_extract_community_standards_missing(self, tmp_path):
        extractor = OpenClawExtractor(
            openclaw_dir=str(tmp_path / "workspaces"),
            skills_dir=str(tmp_path / "skills"),
        )
        result = extractor.extract_community_standards()
        assert result is None

    def test_extract_tools_missing(self, tmp_path):
        extractor = OpenClawExtractor(
            openclaw_dir=str(tmp_path / "workspaces"),
        )
        result = extractor.extract_tools()
        assert result is None

    def test_extract_tools_present(self, tmp_path):
        openclaw_dir = tmp_path / "workspaces"
        openclaw_dir.mkdir()
        (openclaw_dir / "andy-personal").mkdir()
        (openclaw_dir / "TOOLS.md").write_text("# My Tools\n")

        extractor = OpenClawExtractor(
            openclaw_dir=str(openclaw_dir),
        )
        result = extractor.extract_tools()
        assert result is not None

    def test_extract_agent_registry_empty(self, tmp_path):
        """No vault or workspaces should return empty list."""
        extractor = OpenClawExtractor(
            openclaw_dir=str(tmp_path / "workspaces"),
            vault_dir=str(tmp_path / "vault"),
        )
        result = extractor.extract_agent_registry()
        assert result == []

    def test_extract_agent_registry_with_vault(self, tmp_path):
        """Vault entity-index should be included."""
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir(parents=True)
        (vault_dir / "agent-entity-index.md").write_text("# Entity Index\n")

        extractor = OpenClawExtractor(
            openclaw_dir=str(tmp_path / "workspaces"),
            vault_dir=str(vault_dir),
        )
        result = extractor.extract_agent_registry()
        assert len(result) == 1
        assert result[0]["type"] == "entity-index"

    def test_extract_agent_registry_with_workspaces(self, tmp_path):
        """USER.md files in workspaces should be included."""
        workspace_dir = tmp_path / "workspaces" / "my-agent"
        workspace_dir.mkdir(parents=True)
        (workspace_dir / "USER.md").write_text("# User profile\n")

        extractor = OpenClawExtractor(
            openclaw_dir=str(workspace_dir.parent),
            vault_dir=str(tmp_path / "vault"),
        )
        result = extractor.extract_agent_registry()
        assert len(result) == 1
        assert result[0]["type"] == "agent-definition"

    def test_extract_all_no_vault_entry(self, tmp_path):
        """Missing vault entity-index should not cause errors."""
        workspace_dir = tmp_path / "workspaces" / "test-agent"
        workspace_dir.mkdir(parents=True)
        (workspace_dir / "SOUL.md").write_text("# SOUL\n")

        extractor = OpenClawExtractor(
            openclaw_dir=str(workspace_dir.parent),
            skills_dir=str(tmp_path / "skills"),
            vault_dir=str(tmp_path / "vault"),
        )
        result = extractor.extract_all()
        assert "test-agent" in result.identities


class TestExtractorEdgeCases:
    def test_read_file_missing(self, tmp_path):
        result = OpenClawExtractor._read_file(tmp_path / "nonexistent.txt")
        assert result is None

    def test_read_file_permission_error(self, tmp_path):
        """_read_file should handle permission errors gracefully."""
        path = tmp_path / "restricted.txt"
        path.write_text("content")
        path.chmod(0o000)
        try:
            result = OpenClawExtractor._read_file(path)
            assert result is None
        finally:
            path.chmod(0o644)

    def test_read_file_empty(self, tmp_path):
        path = tmp_path / "empty.txt"
        path.write_text("")
        result = OpenClawExtractor._read_file(path)
        assert result is not None
        assert result == ""

    def test_extract_all_with_no_workspace_dir(self, tmp_path):
        """If workspaces directory doesn't exist, no error."""
        extractor = OpenClawExtractor(
            openclaw_dir=str(tmp_path / "nonexistent"),
            skills_dir=str(tmp_path / "skills"),
            vault_dir=str(tmp_path / "vault"),
        )
        result = extractor.extract_all()
        assert result.identities == {}
        assert result.procedures == {}
