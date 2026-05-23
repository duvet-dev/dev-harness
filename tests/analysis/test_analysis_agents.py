"""Tests for harness.analysis.agents — AnalysisAgent and AnalysisAgentRegistry.

Tests AnalysisAgent dataclass, agent constants, and registration lifecycle.
"""

from __future__ import annotations

import pytest

from harness.analysis.agents import (
    AnalysisAgent,
    AnalysisAgentRegistry,
    P1_PROJECT_PROFILER,
    P2_RESPONSIBILITY_DECODER,
    P3_ARCHITECTURE_CRITIC,
    P4_CODE_CRITIC,
    P5_TEST_AUDITOR,
)


class TestAnalysisAgent:
    """Tests for the AnalysisAgent dataclass."""

    def test_default_values(self):
        """Agent creates with sensible defaults."""
        agent = AnalysisAgent(
            name="test-agent",
            description="A test agent",
            system_prompt="You are a test agent.",
        )
        assert agent.name == "test-agent"
        assert agent.description == "A test agent"
        assert agent.system_prompt == "You are a test agent."
        assert agent.model == "deepseek-v4-pro"
        assert agent.temperature == 0.3
        assert agent.timeout == 600
        assert agent.agent_role == "critical-analyser"
        assert agent.output_schema == {}

    def test_custom_values(self):
        """Agent accepts custom field values."""
        agent = AnalysisAgent(
            name="custom",
            description="Custom agent",
            system_prompt="Custom prompt",
            model="gpt-4",
            temperature=0.7,
            timeout=120,
            agent_role="coding-agent",
            output_schema={"type": "object"},
        )
        assert agent.model == "gpt-4"
        assert agent.temperature == 0.7
        assert agent.timeout == 120
        assert agent.agent_role == "coding-agent"
        assert agent.output_schema == {"type": "object"}


class TestP1ProjectProfiler:
    """Tests for P1_PROJECT_PROFILER."""

    def test_config(self):
        assert P1_PROJECT_PROFILER.name == "project-profiler"
        assert P1_PROJECT_PROFILER.model == "deepseek-v4-pro"
        assert "project profiler" in P1_PROJECT_PROFILER.system_prompt.lower()
        assert "projects" in P1_PROJECT_PROFILER.output_schema.get("properties", {})

    def test_output_schema_has_projects(self):
        props = P1_PROJECT_PROFILER.output_schema.get("properties", {})
        assert "projects" in props
        assert "overview" in props


class TestP2ResponsibilityDecoder:
    """Tests for P2_RESPONSIBILITY_DECODER."""

    def test_config(self):
        assert P2_RESPONSIBILITY_DECODER.name == "responsibility-decoder"
        assert "responsibility decoder" in P2_RESPONSIBILITY_DECODER.system_prompt.lower()

    def test_output_schema(self):
        props = P2_RESPONSIBILITY_DECODER.output_schema.get("properties", {})
        assert "projects" in props


class TestP3ArchitectureCritic:
    """Tests for P3_ARCHITECTURE_CRITIC."""

    def test_config(self):
        assert P3_ARCHITECTURE_CRITIC.name == "architecture-critic"
        assert "architecture critic" in P3_ARCHITECTURE_CRITIC.system_prompt.lower()

    def test_output_schema(self):
        props = P3_ARCHITECTURE_CRITIC.output_schema.get("properties", {})
        assert "architecture" in props
        assert "score" in props


class TestP4CodeCritic:
    """Tests for P4_CODE_CRITIC."""

    def test_config(self):
        assert P4_CODE_CRITIC.name == "code-critic"
        assert "code critic" in P4_CODE_CRITIC.system_prompt.lower()

    def test_output_schema(self):
        props = P4_CODE_CRITIC.output_schema.get("properties", {})
        assert "dimensions" in props
        assert "overall_rating" in props


class TestP5TestAuditor:
    """Tests for P5_TEST_AUDITOR."""

    def test_config(self):
        assert P5_TEST_AUDITOR.name == "test-auditor"
        assert "test auditor" in P5_TEST_AUDITOR.system_prompt.lower()

    def test_output_schema(self):
        props = P5_TEST_AUDITOR.output_schema.get("properties", {})
        assert "overview" in props
        assert "coverage_assessment" in props


class TestAnalysisAgentRegistry:
    """Tests for AnalysisAgentRegistry."""

    def setup_method(self):
        AnalysisAgentRegistry.reset()

    def test_get_all_returns_defaults(self):
        """get_all() returns all 5 default agents."""
        agents = AnalysisAgentRegistry.get_all()
        assert len(agents) == 5
        names = {a.name for a in agents}
        assert names == {
            "project-profiler",
            "responsibility-decoder",
            "architecture-critic",
            "code-critic",
            "test-auditor",
        }

    def test_get_by_name(self):
        """get() returns agent by name."""
        agent = AnalysisAgentRegistry.get("project-profiler")
        assert agent is not None
        assert agent.name == "project-profiler"

    def test_get_nonexistent(self):
        """get() returns None for unknown name."""
        agent = AnalysisAgentRegistry.get("nonexistent")
        assert agent is None

    def test_register_custom_agent(self):
        """register() adds a custom agent to the registry."""
        custom = AnalysisAgent(
            name="custom-p6",
            description="Custom P6 agent",
            system_prompt="You are P6.",
        )
        AnalysisAgentRegistry.register(custom)
        assert AnalysisAgentRegistry.get("custom-p6") is not None
        all_agents = AnalysisAgentRegistry.get_all()
        assert len(all_agents) == 6

    def test_unregister_custom_agent(self):
        """unregister() removes a custom agent."""
        custom = AnalysisAgent(
            name="to-remove",
            description="Will be removed",
            system_prompt="Removable.",
        )
        AnalysisAgentRegistry.register(custom)
        assert AnalysisAgentRegistry.get("to-remove") is not None
        AnalysisAgentRegistry.unregister("to-remove")
        assert AnalysisAgentRegistry.get("to-remove") is None

    def test_reset_clears_custom_agents(self):
        """reset() removes all custom agents and restores defaults."""
        custom = AnalysisAgent(
            name="temp",
            description="Temporary",
            system_prompt="Temp.",
        )
        AnalysisAgentRegistry.register(custom)
        AnalysisAgentRegistry.reset()
        # get_all should still return defaults
        agents = AnalysisAgentRegistry.get_all()
        assert len(agents) == 5
        assert AnalysisAgentRegistry.get("temp") is None

    def test_get_all_includes_custom(self):
        """get_all() includes custom agents."""
        custom = AnalysisAgent(
            name="custom-p6",
            description="Custom",
            system_prompt="Custom prompt",
        )
        AnalysisAgentRegistry.register(custom)
        all_agents = AnalysisAgentRegistry.get_all()
        names = {a.name for a in all_agents}
        assert "custom-p6" in names
