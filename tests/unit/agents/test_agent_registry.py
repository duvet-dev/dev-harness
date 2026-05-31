"""Tests for harness.agents.agent_registry.

AgentRole enum has been removed — all roles are now plain strings.
"""

from __future__ import annotations

import pytest

from harness.agents.agent_registry import (
    AGENTS,
    AgentSpec,
    CriticLoopConfig,
    CriticLoopIteration,
    CriticLoopState,
    ToolPermissions,
    get_agent,
    get_agents_by_tag,
    get_default_critic_loop_config,
    get_session_aware_agents,
    has_awareness_role,
    list_agent_names,
    list_agent_roles,
    registry_summary,
)


class TestToolPermissions:
    """Tests for ToolPermissions."""

    def test_unrestricted(self):
        p = ToolPermissions.unrestricted()
        assert p.read is True
        assert p.write is True
        assert p.write_prefixes is None
        assert p.web_search is True

    def test_read_only(self):
        p = ToolPermissions.read_only()
        assert p.read is True
        assert p.write is False
        assert p.web_search is True

    def test_restricted_write(self):
        p = ToolPermissions.restricted_write(["docs/", "tests/"])
        assert p.read is True
        assert p.write is True
        assert p.write_prefixes == ["docs/", "tests/"]

    def test_with_web_search(self):
        p = ToolPermissions.with_web_search(read=True, write=True)
        assert p.read is True
        assert p.write is True


class TestAgentSpec:
    """Tests for AgentSpec dataclass."""

    def test_minimal(self):
        spec = AgentSpec(
            role="coordinator",
            name="Test Agent",
            description="A test agent",
        )
        assert spec.role == "coordinator"
        assert spec.name == "Test Agent"
        assert spec.sop_summary == []
        assert spec.tags == []
        assert spec.tool_permissions is None

    def test_full(self):
        spec = AgentSpec(
            role="architect",
            name="Architect",
            description="Designs systems",
            sop_summary=["Analyse requirements", "Produce architecture"],
            tags=["design", "core"],
            tool_permissions=ToolPermissions.read_only(),
        )
        assert len(spec.sop_summary) == 2
        assert spec.tool_permissions.read is True
        assert spec.tool_permissions.write is False


class TestCriticLoopConfig:
    """Tests for CriticLoopConfig."""

    def test_default_config(self):
        config = CriticLoopConfig()
        assert config.architect_role == "architect"
        assert config.critic_role == "critical-analyser"
        assert config.max_iterations == 3
        assert config.convergence_keywords is None or "no issues found" in config.convergence_keywords
        assert config.architect_output_subdir == "design/"
        assert config.critic_output_subdir == "reviews/"

    def test_custom_config(self):
        config = CriticLoopConfig(
            architect_role="coding-agent",
            critic_role="testing-agent",
            max_iterations=3,
            convergence_keywords=["approved"],
            architect_output_subdir="output/",
            critic_output_subdir="reviews/",
        )
        assert config.architect_role == "coding-agent"
        assert config.max_iterations == 3


class TestCriticLoopIteration:
    """Tests for CriticLoopIteration."""

    def test_defaults(self):
        it = CriticLoopIteration(iteration=0)
        assert it.iteration == 0
        assert it.architect_artifacts == {}
        assert it.critic_artifacts == {}
        assert it.converged is False

    def test_converged(self):
        it = CriticLoopIteration(iteration=1, converged=True)
        assert it.converged is True


class TestRegistryFunctions:
    """Tests for registry lookup functions (string-based agent keys)."""

    def test_get_agent_by_role_string(self):
        agent = get_agent("coordinator")
        assert agent is not None
        assert agent.role == "coordinator"

    def test_get_agent_by_another_string(self):
        agent = get_agent("architect")
        assert agent is not None
        assert agent.role == "architect"

    def test_get_agent_nonexistent(self):
        """get_agent with an unknown string returns None."""
        result = get_agent("nonexistent-role")
        assert result is None

    def test_get_agents_by_tag(self):
        agents = get_agents_by_tag("core")
        assert len(agents) >= 1
        assert all("core" in a.tags for a in agents)

    def test_get_agents_by_tag_empty(self):
        agents = get_agents_by_tag("nonexistent-tag")
        assert agents == []

    def test_list_agent_names(self):
        names = list_agent_names()
        assert "coordinator" in names
        assert "architect" in names
        assert "coding-agent" in names
        assert len(names) > 10

    def test_list_agent_roles(self):
        roles = list_agent_roles()
        assert "coordinator" in roles
        assert "architect" in roles

    def test_registry_summary(self):
        summary = registry_summary()
        assert summary["total_agents"] == len(AGENTS)
        assert len(summary["agents"]) == len(AGENTS)
        assert all("role" in a for a in summary["agents"])
        assert all("name" in a for a in summary["agents"])


class TestHasAwarenessRole:
    """Tests for has_awareness_role()."""

    def test_architect_is_aware(self):
        assert has_awareness_role("architect") is True

    def test_coding_agent_is_aware(self):
        assert has_awareness_role("coding-agent") is True

    def test_coordinator_is_not_aware(self):
        assert has_awareness_role("coordinator") is False


class TestGetDefaultCriticLoopConfig:
    """Tests for get_default_critic_loop_config()."""

    def test_returns_default_config(self):
        config = get_default_critic_loop_config()
        assert isinstance(config, CriticLoopConfig)
        assert config.architect_role == "architect"
        assert config.max_iterations == 5


class TestGetSessionAwareAgents:
    """Tests for get_session_aware_agents()."""

    def test_returns_aware_agents(self):
        agents = get_session_aware_agents()
        assert all(has_awareness_role(a.role) for a in agents)
        assert len(agents) >= 7

    def test_excludes_non_aware(self):
        agents = get_session_aware_agents()
        roles = [a.role for a in agents]
        assert "coordinator" not in roles
        assert "documentation-agent" not in roles


class TestAGENTS:
    """Tests for the AGENTS constant."""

    def test_all_agents_have_names(self):
        for agent in AGENTS:
            assert agent.name, f"Agent {agent.role} has no name"

    def test_all_agents_have_descriptions(self):
        for agent in AGENTS:
            assert agent.description, f"Agent {agent.role} has no description"

    def test_unique_roles(self):
        roles = [a.role for a in AGENTS]
        assert len(roles) == len(set(roles)), "Duplicate roles in AGENTS"
