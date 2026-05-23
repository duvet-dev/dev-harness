"""Tests for harness.constitution.templates.template_registry."""

from pathlib import Path
from unittest.mock import patch

import pytest

from harness.constitution.templates.template_registry import (
    TemplateNotFoundError,
    TemplateRegistry,
    available_templates_str,
    get_template,
    list_constitution_templates,
    merge_overrides,
    refresh_agent_profiles,
    seed_agent_profiles,
    seed_providers_yaml,
)


class TestGetTemplate:
    def test_get_backend_service(self):
        tpl = get_template("backend-service")
        assert tpl["project"]["template"] == "backend-service"
        assert "project" in tpl
        assert "agents" in tpl
        assert len(tpl["agents"]) == 8

    def test_get_library(self):
        tpl = get_template("library")
        assert tpl["project"]["template"] == "library"
        assert len(tpl["agents"]) == 7

    def test_get_cli_tool(self):
        tpl = get_template("cli-tool")
        assert tpl["project"]["template"] == "cli-tool"
        assert tpl["gates"]["default_mode"] == "wild"

    def test_get_data_pipeline(self):
        tpl = get_template("data-pipeline")
        assert tpl["project"]["template"] == "data-pipeline"
        assert tpl["project"]["name"] == "my-pipeline"

    def test_get_general_research(self):
        tpl = get_template("general-research")
        assert tpl["project"]["template"] == "general-research"
        assert tpl["gates"]["default_mode"] == "wild"

    def test_get_nonexistent_raises(self):
        with pytest.raises(KeyError, match="Unknown"):
            get_template("nonexistent")

    def test_get_returns_deep_copy(self):
        tpl1 = get_template("backend-service")
        tpl2 = get_template("backend-service")
        assert tpl1 is not tpl2
        tpl1["project"]["name"] = "modified"
        assert tpl2["project"]["name"] == "my-project"


class TestListTemplates:
    def test_list_constitution_templates(self):
        names = list_constitution_templates()
        assert "backend-service" in names
        assert "library" in names
        assert "cli-tool" in names
        assert "data-pipeline" in names
        assert "general-research" in names
        assert names == sorted(names)

    def test_available_templates_str(self):
        s = available_templates_str()
        assert "backend-service" in s
        assert "library" in s


class TestMergeOverrides:
    def test_merge_scalar(self):
        base = {"a": 1, "b": 2}
        merge_overrides(base, {"a": 99})
        assert base["a"] == 99
        assert base["b"] == 2

    def test_merge_nested(self):
        base = {"project": {"name": "old", "description": "desc"}}
        merge_overrides(base, {"project": {"name": "new"}})
        assert base["project"]["name"] == "new"
        assert base["project"]["description"] == "desc"

    def test_merge_empty_overrides(self):
        base = {"a": 1}
        result = merge_overrides(base, None)
        assert result == {"a": 1}
        assert result is base

    def test_merge_add_new_key(self):
        base = {"a": 1}
        merge_overrides(base, {"b": 2})
        assert "b" in base

    def test_merge_list_replaces(self):
        base = {"items": [1, 2, 3]}
        merge_overrides(base, {"items": [4, 5]})
        assert base["items"] == [4, 5]


class TestTemplateRegistryLegacy:
    def test_list_templates(self):
        templates = TemplateRegistry.list_templates()
        assert len(templates) >= 5
        assert all("id" in t and "name" in t and "description" in t for t in templates)

    def test_get_backend_service(self):
        tpl = TemplateRegistry.get("backend-service")
        assert tpl["name"] == "Backend Service"
        assert len(tpl["directories"]) >= 6

    def test_get_data_pipeline(self):
        tpl = TemplateRegistry.get("data-pipeline")
        assert tpl["name"] == "Data Pipeline"
        assert "pipelines" in " ".join(tpl["directories"])

    def test_get_nonexistent_raises(self):
        with pytest.raises(TemplateNotFoundError):
            TemplateRegistry.get("nonexistent")

    def test_scaffold_creates_directories(self, tmp_path):
        created = TemplateRegistry.scaffold("library", "my-lib", tmp_path)
        assert len(created) >= 3
        assert (tmp_path / "src" / "my-lib" / "domain").is_dir()
        assert (tmp_path / "tests").is_dir()
        assert (tmp_path / "docs").is_dir()

    def test_scaffold_uses_project_name(self, tmp_path):
        created = TemplateRegistry.scaffold("backend-service", "my-api", tmp_path)
        assert (tmp_path / "src" / "my-api" / "domain").is_dir()

    def test_scaffold_nonexistent_raises(self, tmp_path):
        with pytest.raises(TemplateNotFoundError):
            TemplateRegistry.scaffold("nonexistent", "x", tmp_path)

    def test_scaffold_is_idempotent(self, tmp_path):
        TemplateRegistry.scaffold("library", "my-lib", tmp_path)
        TemplateRegistry.scaffold("library", "my-lib", tmp_path)
        assert (tmp_path / "docs").is_dir()


class TestSeedProvidersYaml:
    def test_creates_file(self, tmp_path):
        result = seed_providers_yaml(tmp_path)
        assert result is not None
        assert result.is_file()
        assert ".harness" in str(result)

    def test_does_not_overwrite(self, tmp_path):
        path = tmp_path / ".harness" / "providers.yaml"
        path.parent.mkdir(parents=True)
        path.write_text("# existing\n")
        result = seed_providers_yaml(tmp_path)
        assert result is None
        assert path.read_text() == "# existing\n"

    def test_contains_deepseek_config(self, tmp_path):
        result = seed_providers_yaml(tmp_path)
        assert result is not None
        content = result.read_text()
        assert "deepseek" in content
        assert "DEEPSEEK_API_KEY" in content


class TestSeedAgentProfiles:
    def test_seeds_agent_profiles(self, tmp_path):
        agents = [
            {"name": "planner"},
            {"name": "coder"},
        ]
        agents_dir = seed_agent_profiles(tmp_path, agents)
        assert agents_dir.is_dir()

        assert (agents_dir / "planner" / "identity.md").is_file()
        identity = (agents_dir / "planner" / "identity.md").read_text()
        assert "Planner" in identity

        assert (agents_dir / "planner" / "procedures.md").is_file()
        procedures = (agents_dir / "planner" / "procedures.md").read_text()
        assert "memory" in procedures.lower()

        assert (agents_dir / "planner" / "memory" / ".gitkeep").is_file()

    def test_seeds_community_standards(self, tmp_path):
        agents = [{"name": "coder"}]
        agents_dir = seed_agent_profiles(tmp_path, agents)
        assert (agents_dir / "standards" / "community-standards.md").is_file()

    def test_seeds_providers_yaml(self, tmp_path):
        agents = [{"name": "coder"}]
        seed_agent_profiles(tmp_path, agents)
        assert (tmp_path / ".harness" / "providers.yaml").is_file()

    def test_multiple_agents_all_created(self, tmp_path):
        agents = [
            {"name": "planner"},
            {"name": "coder"},
            {"name": "reviewer"},
            {"name": "tester"},
        ]
        agents_dir = seed_agent_profiles(tmp_path, agents)
        for agent in agents:
            assert (agents_dir / agent["name"] / "identity.md").is_file()


class TestRefreshAgentProfiles:
    def test_refresh_creates_profiles_from_registry(self, tmp_path):
        """Test that refresh_agent_profiles creates profiles based on AGENTS registry."""
        result = refresh_agent_profiles(tmp_path, force=True)
        assert isinstance(result, dict)
        assert any(k in result for k in ("created", "updated", "existing"))

        agents_dir = tmp_path / ".harness" / "agents"
        assert agents_dir.is_dir()
        assert (agents_dir / "standards" / "community-standards.md").is_file()

    def test_refresh_preserves_existing(self, tmp_path):
        """With force=False, existing profiles should be kept."""
        # Create an existing profile for a known agent
        agents_dir = tmp_path / ".harness" / "agents" / "testing-agent"
        agents_dir.mkdir(parents=True)
        (agents_dir / "identity.md").write_text("# My custom identity\n")
        (agents_dir / "procedures.md").write_text("# My custom procedures\n")
        (agents_dir / "memory").mkdir()
        (agents_dir / "memory" / ".gitkeep").write_text("")

        result = refresh_agent_profiles(tmp_path, force=False)
        assert "existing" in result
        # Our custom identity should still be intact
        content = (agents_dir / "identity.md").read_text()
        assert "My custom identity" in content

    def test_refresh_force_overwrites(self, tmp_path):
        """With force=True, existing profiles should be overwritten."""
        agents_dir = tmp_path / ".harness" / "agents" / "testing-agent"
        agents_dir.mkdir(parents=True)
        (agents_dir / "identity.md").write_text("# Old identity\n")
        (agents_dir / "procedures.md").write_text("# Old procedures\n")

        result = refresh_agent_profiles(tmp_path, force=True)
        assert any(k in result for k in ("updated",))

    def test_refresh_creates_providers_yaml(self, tmp_path):
        refresh_agent_profiles(tmp_path, force=True)
        assert (tmp_path / ".harness" / "providers.yaml").is_file()


class TestRefreshEdgeCases:
    def test_empty_project_path(self, tmp_path):
        """Call with a tmp_path that has no pre-existing structure."""
        result = refresh_agent_profiles(tmp_path, force=True)
        assert isinstance(result, dict)
