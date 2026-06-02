"""Tests for TeamRegistry (team/registry.py).

V7 §10.3 — TeamRegistry with merge semantics.
"""

from __future__ import annotations

import pytest

from harness.errors import EmptyTeamError, UnknownTeamError
from harness.team.model import AgentTeam
from harness.team.registry import TeamRegistry


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def builtin_teams() -> list[AgentTeam]:
    return [
        AgentTeam(name="architecture", agents=["architect"]),
        AgentTeam(name="coding", agents=["coder"]),
    ]


@pytest.fixture
def registry_with_all() -> TeamRegistry:
    return TeamRegistry(
        builtin=[
            AgentTeam(name="architecture", agents=["architect"]),
            AgentTeam(name="coding", agents=["coder"]),
        ],
        project=[
            AgentTeam(
                name="architecture",
                agents=["project-architect"],
            ),
            AgentTeam(name="data-science", agents=["ml-engineer"]),
        ],
        user=[
            AgentTeam(
                name="coding",
                agents=["user-coder", "user-tester"],
            ),
            AgentTeam(name="devops", agents=["infra-agent"]),
        ],
    )


# ── Basic Resolution ──────────────────────────────────────────────────────


class TestResolve:
    """Tests for TeamRegistry.resolve()."""

    def test_resolve_returns_correct_team(self, builtin_teams) -> None:
        registry = TeamRegistry(builtin=builtin_teams)
        team = registry.resolve("architecture")
        assert team.name == "architecture"
        assert team.agents == ["architect"]

    def test_resolve_raises_unknown_team(self, builtin_teams) -> None:
        registry = TeamRegistry(builtin=builtin_teams)
        with pytest.raises(UnknownTeamError) as exc:
            registry.resolve("nonexistent")
        assert "nonexistent" in str(exc.value)


class TestResolveAgents:
    """Tests for TeamRegistry.resolve_agents()."""

    def test_resolve_agents_returns_agents(self):
        registry = TeamRegistry(
            builtin=[AgentTeam(name="dev", agents=["a", "b"])]
        )
        assert registry.resolve_agents("dev") == ["a", "b"]

    def test_resolve_agents_raises_unknown_team(self):
        registry = TeamRegistry(builtin=[])
        with pytest.raises(UnknownTeamError):
            registry.resolve_agents("nowhere")

    def test_resolve_agents_raises_empty_team(self):
        registry = TeamRegistry(
            builtin=[AgentTeam(name="empty", agents=[])]
        )
        with pytest.raises(EmptyTeamError) as exc:
            registry.resolve_agents("empty")
        assert "empty" in str(exc.value)


class TestListTeams:
    """Tests for TeamRegistry.list_teams()."""

    def test_list_teams_returns_names(self, builtin_teams):
        registry = TeamRegistry(builtin=builtin_teams)
        names = registry.list_teams()
        assert "architecture" in names
        assert "coding" in names

    def test_list_teams_sorted(self):
        registry = TeamRegistry(
            builtin=[
                AgentTeam(name="z-team", agents=["z"]),
                AgentTeam(name="a-team", agents=["a"]),
            ]
        )
        assert registry.list_teams() == ["a-team", "z-team"]

    def test_list_teams_empty(self):
        registry = TeamRegistry(builtin=[])
        assert registry.list_teams() == []


class TestCount:
    """Tests for TeamRegistry.count."""

    def test_count(self, builtin_teams):
        registry = TeamRegistry(builtin=builtin_teams)
        assert registry.count == 2


# ── Merge Semantics ───────────────────────────────────────────────────────


class TestMerge:
    """Tests for built-in < project < user merge semantics (D38)."""

    def test_project_overrides_builtin_full_replacement(self):
        """Project team fully replaces built-in team with same name."""
        registry = TeamRegistry(
            builtin=[
                AgentTeam(
                    name="architecture",
                    description="Original",
                    agents=["architect"],
                    guidelines="old",
                ),
            ],
            project=[
                AgentTeam(
                    name="architecture",
                    description="Replacement",
                    agents=["project-architect"],
                    guidelines="new",
                ),
            ],
        )
        team = registry.resolve("architecture")
        assert team.description == "Replacement"
        assert team.agents == ["project-architect"]
        assert team.guidelines == "new"
        # Everything from built-in was replaced
        assert "Original" not in team.description

    def test_user_overrides_project(self):
        """User team overrides project team with same name."""
        registry = TeamRegistry(
            builtin=[
                AgentTeam(name="dev", agents=["builtin-dev"]),
            ],
            project=[
                AgentTeam(name="dev", agents=["project-dev"]),
            ],
            user=[
                AgentTeam(name="dev", agents=["user-dev"]),
            ],
        )
        team = registry.resolve("dev")
        assert team.agents == ["user-dev"]

    def test_user_overrides_builtin(self):
        """User team overrides built-in team directly."""
        registry = TeamRegistry(
            builtin=[
                AgentTeam(name="ops", agents=["builtin-ops"]),
            ],
            user=[
                AgentTeam(name="ops", agents=["user-ops"]),
            ],
        )
        team = registry.resolve("ops")
        assert team.agents == ["user-ops"]

    def test_unique_names_appended(self):
        """Teams with unique names from any source are preserved."""
        registry = TeamRegistry(
            builtin=[
                AgentTeam(name="builtin-only", agents=["b1"]),
            ],
            project=[
                AgentTeam(name="project-only", agents=["p1"]),
            ],
            user=[
                AgentTeam(name="user-only", agents=["u1"]),
            ],
        )
        assert registry.count == 3
        assert registry.resolve("builtin-only").agents == ["b1"]
        assert registry.resolve("project-only").agents == ["p1"]
        assert registry.resolve("user-only").agents == ["u1"]

    def test_no_partial_merge(self):
        """Project team fully replaces built-in agents AND guidelines (D38)."""
        registry = TeamRegistry(
            builtin=[
                AgentTeam(
                    name="plat",
                    agents=["a", "b", "c"],
                    guidelines="Lots of advice",
                ),
            ],
            project=[
                AgentTeam(
                    name="plat",
                    agents=["x", "y"],
                    # No guidelines set — should remain None, not inherit
                ),
            ],
        )
        team = registry.resolve("plat")
        assert team.agents == ["x", "y"]
        # Should NOT inherit built-in guidelines
        assert team.guidelines is None

    def test_merge_only_builtin(self):
        """Registry with only built-in teams works."""
        registry = TeamRegistry(
            builtin=[AgentTeam(name="solo", agents=["s1"])]
        )
        assert registry.count == 1
        assert registry.resolve("solo").agents == ["s1"]

    def test_merge_project_and_user_no_builtin(self):
        """Registry without built-in teams still works."""
        registry = TeamRegistry(
            project=[AgentTeam(name="p", agents=["p1"])],
            user=[AgentTeam(name="u", agents=["u1"])],
        )
        assert registry.count == 2
        assert registry.resolve("p").agents == ["p1"]
        assert registry.resolve("u").agents == ["u1"]

    def test_empty_registry(self):
        """Empty registry has no teams."""
        registry = TeamRegistry()
        assert registry.count == 0
        assert registry.list_teams() == []
        with pytest.raises(UnknownTeamError):
            registry.resolve("anything")
