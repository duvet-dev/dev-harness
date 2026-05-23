"""Tests for harness.paths — canonical path resolvers."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.paths import (
    find_project_root,
    resolve_project_root,
    get_harness_dir,
    get_engagements_dir,
    get_engagement_dir,
    get_engagement_phases_path,
    get_engagement_goal_path,
    get_context_cache_dir,
    get_active_engagements_path,
    get_agents_dir,
    get_agent_dir,
    get_agent_identity_path,
    get_agent_procedures_path,
    get_agent_memory_dir,
    get_agent_standards_dir,
    get_config_path,
    get_providers_path,
    get_fleets_path,
    get_patterns_dir,
    get_cache_dir,
    get_architecture_goal_path,
    get_boundaries_path,
    get_docs_backups_dir,
    get_freshness_path,
    get_harness_state_path,
    get_engagement_md,
    get_engagement_yaml,
    get_engagement_plan_md,
    get_engagement_plan_yaml,
    get_engagement_waves_dir,
    get_engagement_checkpoints_dir,
    get_engagement_feedback_dir,
    get_engagement_changelog_dir,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    """A temporary project root with a ``.harness/`` directory."""
    (tmp_path / ".harness").mkdir()
    return tmp_path


# ── Project root discovery ────────────────────────────────────────────────


class TestFindProjectRoot:
    def test_finds_root_from_subdir(self, tmp_root: Path) -> None:
        """Finds the project root from a nested subdirectory."""
        sub = tmp_root / "a" / "b" / "c"
        sub.mkdir(parents=True)
        assert find_project_root(sub) == tmp_root

    def test_returns_none_when_no_harness(self, tmp_path: Path) -> None:
        """Returns None when no .harness/ directory exists."""
        assert find_project_root(tmp_path) is None

    def test_returns_root_when_in_root(self, tmp_root: Path) -> None:
        """Finds the project root when already at that directory."""
        assert find_project_root(tmp_root) == tmp_root

    def test_returns_root_with_trailing_slash(self, tmp_root: Path) -> None:
        """Handles paths with trailing slashes correctly."""
        root = str(tmp_root) + "/"
        assert find_project_root(Path(root)) == tmp_root


class TestResolveProjectRoot:
    def test_resolves_when_found(self, tmp_root: Path) -> None:
        """Returns the project root when found."""
        assert resolve_project_root(tmp_root) == tmp_root

    def test_raises_when_not_found(self, tmp_path: Path) -> None:
        """Exits with error when no .harness/ directory."""
        with pytest.raises(SystemExit):
            resolve_project_root(tmp_path)


# ── Directory getters ─────────────────────────────────────────────────────


class TestDirectoryGetters:
    def test_get_harness_dir(self, tmp_root: Path) -> None:
        """Returns root/.harness/."""
        assert get_harness_dir(tmp_root) == tmp_root / ".harness"

    def test_get_engagements_dir(self, tmp_root: Path) -> None:
        """Returns root/.harness/engagements/."""
        assert get_engagements_dir(tmp_root) == tmp_root / ".harness" / "engagements"

    def test_get_engagement_dir(self, tmp_root: Path) -> None:
        """Returns root/.harness/engagements/<slug>/."""
        slug = "test-engagement"
        expected = tmp_root / ".harness" / "engagements" / slug
        assert get_engagement_dir(tmp_root, slug) == expected

    def test_get_engagement_phases_path(self, tmp_root: Path) -> None:
        """Returns the phases.yaml path for an engagement."""
        slug = "my-slug"
        expected = tmp_root / ".harness" / "engagements" / slug / "phases.yaml"
        assert get_engagement_phases_path(tmp_root, slug) == expected

    def test_get_engagement_goal_path(self, tmp_root: Path) -> None:
        """Returns the architecture-goal.yaml path for an engagement."""
        slug = "my-slug"
        result = get_engagement_goal_path(tmp_root, slug)
        assert "architecture-goal.yaml" in str(result)

    def test_get_context_cache_dir(self, tmp_root: Path) -> None:
        """Returns the context directory for an engagement."""
        slug = "my-slug"
        result = get_context_cache_dir(tmp_root, slug)
        assert str(result).endswith("context")

    def test_get_active_engagements_path(self, tmp_root: Path) -> None:
        """Returns the active engagements mapping file path."""
        result = get_active_engagements_path(tmp_root)
        assert "active-engagements.yaml" in str(result)

    def test_get_agents_dir(self, tmp_root: Path) -> None:
        """Returns .harness/agents/."""
        result = get_agents_dir(tmp_root)
        assert result == tmp_root / ".harness" / "agents"

    def test_get_agent_dir(self, tmp_root: Path) -> None:
        """Returns the per-agent profile directory."""
        result = get_agent_dir(tmp_root, "architect")
        assert result == tmp_root / ".harness" / "agents" / "architect"

    def test_get_agent_identity_path(self, tmp_root: Path) -> None:
        """Returns identity.md for an agent."""
        result = get_agent_identity_path(tmp_root, "architect")
        assert result == tmp_root / ".harness" / "agents" / "architect" / "identity.md"

    def test_get_agent_procedures_path(self, tmp_root: Path) -> None:
        """Returns procedures.md for an agent."""
        result = get_agent_procedures_path(tmp_root, "architect")
        assert result == tmp_root / ".harness" / "agents" / "architect" / "procedures.md"

    def test_get_agent_memory_dir(self, tmp_root: Path) -> None:
        """Returns the memory directory for an agent."""
        result = get_agent_memory_dir(tmp_root, "coder")
        assert result == tmp_root / ".harness" / "agents" / "coder" / "memory"

    def test_get_agent_standards_dir(self, tmp_root: Path) -> None:
        """Returns the standards directory under agents."""
        result = get_agent_standards_dir(tmp_root)
        assert result == tmp_root / ".harness" / "agents" / "standards"

    def test_get_config_path(self, tmp_root: Path) -> None:
        """Returns config.yaml path."""
        result = get_config_path(tmp_root)
        assert "config.yaml" in str(result)

    def test_get_providers_path(self, tmp_root: Path) -> None:
        """Returns providers.yaml path."""
        result = get_providers_path(tmp_root)
        assert "providers.yaml" in str(result)

    def test_get_fleets_path(self, tmp_root: Path) -> None:
        """Returns fleets.yaml path."""
        result = get_fleets_path(tmp_root)
        assert "fleets.yaml" in str(result)

    def test_get_patterns_dir(self, tmp_root: Path) -> None:
        """Returns the patterns directory."""
        result = get_patterns_dir(tmp_root)
        assert result == tmp_root / ".harness" / "patterns"

    def test_get_cache_dir(self, tmp_root: Path) -> None:
        """Returns the cache directory."""
        result = get_cache_dir(tmp_root)
        assert result == tmp_root / ".harness" / "cache"

    def test_get_architecture_goal_path(self, tmp_root: Path) -> None:
        """Returns architecture-goal.yaml path."""
        result = get_architecture_goal_path(tmp_root)
        assert "architecture-goal.yaml" in str(result)

    def test_get_boundaries_path(self, tmp_root: Path) -> None:
        """Returns boundaries.yaml path."""
        result = get_boundaries_path(tmp_root)
        assert "boundaries.yaml" in str(result)

    def test_get_docs_backups_dir(self, tmp_root: Path) -> None:
        """Returns the docs backups directory."""
        result = get_docs_backups_dir(tmp_root)
        assert result == tmp_root / ".harness" / "docs-backups"

    def test_get_freshness_path(self, tmp_root: Path) -> None:
        """Returns freshness file at project root."""
        result = get_freshness_path(tmp_root)
        assert result == tmp_root / ".harness-freshness.yaml"

    def test_get_harness_state_path(self, tmp_root: Path) -> None:
        """Returns state file at project root."""
        result = get_harness_state_path(tmp_root)
        assert result == tmp_root / "harness-state.yaml"

    def test_get_engagement_md(self, tmp_root: Path) -> None:
        """Returns the engagement.md path."""
        result = get_engagement_md(tmp_root, "my-slug")
        assert "engagement.md" in str(result)

    def test_get_engagement_yaml(self, tmp_root: Path) -> None:
        """Returns the engagement.yaml path."""
        result = get_engagement_yaml(tmp_root, "my-slug")
        assert "engagement.yaml" in str(result)

    def test_get_engagement_plan_md(self, tmp_root: Path) -> None:
        """Returns the plan.md path."""
        result = get_engagement_plan_md(tmp_root, "my-slug")
        assert "plan.md" in str(result)

    def test_get_engagement_plan_yaml(self, tmp_root: Path) -> None:
        """Returns the plan.yaml path."""
        result = get_engagement_plan_yaml(tmp_root, "my-slug")
        assert "plan.yaml" in str(result)

    def test_get_engagement_waves_dir(self, tmp_root: Path) -> None:
        """Returns the waves directory."""
        result = get_engagement_waves_dir(tmp_root, "my-slug")
        assert result.name == "waves"

    def test_get_engagement_checkpoints_dir(self, tmp_root: Path) -> None:
        """Returns the checkpoints directory."""
        result = get_engagement_checkpoints_dir(tmp_root, "my-slug")
        assert result.name == "checkpoints"

    def test_get_engagement_feedback_dir(self, tmp_root: Path) -> None:
        """Returns the feedback directory."""
        result = get_engagement_feedback_dir(tmp_root, "my-slug")
        assert result.name == "feedback"

    def test_get_engagement_changelog_dir(self, tmp_root: Path) -> None:
        """Returns the changelog directory."""
        result = get_engagement_changelog_dir(tmp_root, "my-slug")
        assert result.name == "changelog"
