"""Tests for AgentCatalogue (agents/agent_catalogue.py).

V7 §10.6 — String-keyed agent catalogue replacing AgentRole.
"""

from __future__ import annotations

import pytest

from harness.agents.agent_catalogue import AgentCatalogue, AgentDefinition
from harness.errors import UnknownAgentError


class TestAgentCatalogue:
    """Tests for the string-keyed agent catalogue."""

    def test_default_agents_loaded(self) -> None:
        """Catalogue loads default agents on construction."""
        catalogue = AgentCatalogue()
        assert catalogue.count == 16
        assert "architect" in catalogue.list_agents()
        assert "coding-agent" in catalogue.list_agents()

    def test_resolve_returns_definition(self) -> None:
        """resolve() returns the correct AgentDefinition."""
        catalogue = AgentCatalogue()
        architect = catalogue.resolve("architect")
        assert isinstance(architect, AgentDefinition)
        assert architect.name == "architect"
        assert architect.description == (
            "Produces architecture designs and overviews"
        )
        assert "architecture-design" in architect.capabilities

    def test_resolve_raises_unknown(self) -> None:
        """resolve() raises UnknownAgentError for unknown agents."""
        catalogue = AgentCatalogue()
        with pytest.raises(UnknownAgentError) as exc:
            catalogue.resolve("nonexistent-agent")
        assert "nonexistent-agent" in str(exc.value)

    def test_list_agents_sorted(self) -> None:
        """list_agents() returns sorted agent names."""
        catalogue = AgentCatalogue()
        agents = catalogue.list_agents()
        # Should be sorted
        assert agents == sorted(agents)
        # Should contain expected agents
        assert "architect" in agents
        assert "validation-agent" in agents

    def test_register_new_agent(self) -> None:
        """register() adds a new agent to the catalogue."""
        catalogue = AgentCatalogue()
        new_agent = AgentDefinition(
            name="custom-agent",
            description="A custom agent",
            capabilities=["custom-capability"],
        )
        catalogue.register(new_agent)
        assert catalogue.count == 17
        assert "custom-agent" in catalogue.list_agents()
        resolved = catalogue.resolve("custom-agent")
        assert resolved.name == "custom-agent"
        assert resolved.capabilities == ["custom-capability"]

    def test_register_overrides_existing(self) -> None:
        """register() replaces an existing agent definition."""
        catalogue = AgentCatalogue()
        original = catalogue.resolve("architect")
        assert original.description == (
            "Produces architecture designs and overviews"
        )

        override = AgentDefinition(
            name="architect",
            description="Overridden architect",
            capabilities=["new-capability"],
        )
        catalogue.register(override)
        assert catalogue.count == 16  # Same count, replaced
        assert catalogue.resolve("architect").description == (
            "Overridden architect"
        )
        assert catalogue.resolve("architect").capabilities == [
            "new-capability"
        ]

    def test_list_agents_completeness(self) -> None:
        """All expected default agents are present."""
        catalogue = AgentCatalogue()
        expected = {
            "architect",
            "architecture-critic",
            "code-critic",
            "security-critic",
            "coding-agent",
            "testing-agent",
            "test-coverage-analyser",
            "design-reviewer",
            "critical-analyser",
            "security-auditor",
            "planning-agent",
            "dependency-analyser",
            "discovery-agent",
            "research-agent",
            "validation-agent",
            "example-scenarios-agent",
        }
        actual = set(catalogue.list_agents())
        assert actual == expected

    def test_agent_definition_default_tools(self) -> None:
        """AgentDefinition has empty default_tools if not specified."""
        agent = AgentDefinition(name="test", description="test")
        assert agent.default_tools == []

    def test_agent_definition_with_tools(self) -> None:
        """AgentDefinition can specify default_tools."""
        agent = AgentDefinition(
            name="test",
            description="test",
            default_tools=["web-search"],
        )
        assert agent.default_tools == ["web-search"]


class TestAgentDefinition:
    """Tests for the AgentDefinition dataclass."""

    def test_create_minimal(self) -> None:
        """AgentDefinition can be created with just name and description."""
        ad = AgentDefinition(name="test", description="a test agent")
        assert ad.name == "test"
        assert ad.description == "a test agent"
        assert ad.capabilities == []
        assert ad.default_tools == []

    def test_create_full(self) -> None:
        """AgentDefinition can be created with all fields."""
        ad = AgentDefinition(
            name="full-agent",
            description="Full agent",
            capabilities=["cap1", "cap2"],
            default_tools=["tool1"],
        )
        assert ad.name == "full-agent"
        assert ad.capabilities == ["cap1", "cap2"]
        assert ad.default_tools == ["tool1"]

    def test_equality(self) -> None:
        """Two AgentDefinitions with same fields are equal."""
        a1 = AgentDefinition(name="x", description="d")
        a2 = AgentDefinition(name="x", description="d")
        assert a1 == a2
