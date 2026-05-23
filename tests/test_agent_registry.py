"""Tests for harness.agents.agent_registry — agent specs and registry functions.

Tests AgentSpec, AgentRole, ToolPermissions, CriticLoopConfig, and
all registry lookup functions.
"""

from __future__ import annotations

import pytest

from harness.agents.agent_registry import (
    AGENTS,
    AgentRole,
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


class TestAgentRole:
    """Tests for AgentRole enum."""

    def test_known_roles(self):
        assert AgentRole.COORDINATOR.value == "coordinator"
        assert AgentRole.ARCHITECT.value == "architect"
        assert AgentRole.CODING_AGENT.value == "coding-agent"
        assert AgentRole.TESTING_AGENT.value == "testing-agent"

    def test_from_string(self):
        assert AgentRole("coordinator") == AgentRole.COORDINATOR
        assert AgentRole("architect") == AgentRole.ARCHITECT

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError):
            AgentRole("nonexistent-role")


class TestAgentSpec:
    """Tests for AgentSpec dataclass."""

    def test_minimal(self):
        spec = AgentSpec(
            role=AgentRole.COORDINATOR,
            name="Test Agent",
            description="A test agent",
        )
        assert spec.role == AgentRole.COORDINATOR
        assert spec.name == "Test Agent"
        assert spec.sop_summary == []
        assert spec.tags == []
        assert spec.tool_permissions is None

    def test_full(self):
        spec = AgentSpec(
            role=AgentRole.ARCHITECT,
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
        assert config.architect_role == AgentRole.ARCHITECT
        assert config.critic_role == AgentRole.CRITICAL_ANALYSER
        assert config.max_iterations == 5
        assert "no issues found" in config.convergence_keywords
        assert config.architect_output_subdir == "design/"
        assert config.critic_output_subdir == "reviews/"

    def test_custom_config(self):
        config = CriticLoopConfig(
            architect_role=AgentRole.CODING_AGENT,
            critic_role=AgentRole.TESTING_AGENT,
            max_iterations=3,
            convergence_keywords=["approved"],
            architect_output_subdir="output/",
            critic_output_subdir="reviews/",
        )
        assert config.architect_role == AgentRole.CODING_AGENT
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
    """Tests for registry lookup functions."""

    def test_get_agent_by_role_enum(self):
        agent = get_agent(AgentRole.COORDINATOR)
        assert agent is not None
        assert agent.role == AgentRole.COORDINATOR

    def test_get_agent_by_string(self):
        agent = get_agent("architect")
        assert agent is not None
        assert agent.role == AgentRole.ARCHITECT

    def test_get_agent_nonexistent(self):
        """get_agent with a string that's not a valid AgentRole raises ValueError."""
        with pytest.raises(ValueError):
            get_agent("nonexistent-role")

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
        assert len(names) > 10  # Should have many agents

    def test_list_agent_roles(self):
        roles = list_agent_roles()
        assert AgentRole.COORDINATOR in roles
        assert AgentRole.ARCHITECT in roles

    def test_registry_summary(self):
        summary = registry_summary()
        assert summary["total_agents"] == len(AGENTS)
        assert len(summary["agents"]) == len(AGENTS)
        assert all("role" in a for a in summary["agents"])
        assert all("name" in a for a in summary["agents"])


class TestHasAwarenessRole:
    """Tests for has_awareness_role()."""

    def test_architect_is_aware(self):
        assert has_awareness_role(AgentRole.ARCHITECT) is True

    def test_coding_agent_is_aware(self):
        assert has_awareness_role(AgentRole.CODING_AGENT) is True

    def test_coordinator_is_not_aware(self):
        assert has_awareness_role(AgentRole.COORDINATOR) is False


class TestGetDefaultCriticLoopConfig:
    """Tests for get_default_critic_loop_config()."""

    def test_returns_default_config(self):
        config = get_default_critic_loop_config()
        assert isinstance(config, CriticLoopConfig)
        assert config.architect_role == AgentRole.ARCHITECT
        assert config.max_iterations == 5


class TestGetSessionAwareAgents:
    """Tests for get_session_aware_agents()."""

    def test_returns_aware_agents(self):
        agents = get_session_aware_agents()
        assert all(has_awareness_role(a.role) for a in agents)
        assert len(agents) >= 7  # architect, coding, testing, etc.

    def test_excludes_non_aware(self):
        agents = get_session_aware_agents()
        roles = [a.role for a in agents]
        assert AgentRole.COORDINATOR not in roles
        assert AgentRole.DOCUMENTATION_AGENT not in roles


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
