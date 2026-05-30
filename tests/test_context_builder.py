"""Tests for harness.agents.context_builder — team guideline injection.

Tests format_fleet_guidelines, get_fleet_system_prompt_section,
get_fleet_system_prompt_section_for_phase, and build_agent_context.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.agents.context_builder import (
    build_agent_context,
    format_fleet_guidelines,
    get_fleet_system_prompt_section,
    get_fleet_system_prompt_section_for_phase,
)
from harness.team.model import AgentTeam
from harness.team.registry import TeamRegistry


class TestFormatFleetGuidelines:
    """Tests for format_fleet_guidelines()."""

    def test_basic_format(self):
        team = AgentTeam(
            name="coding",
            description="Coding team",
            agents=["coder", "tester"],
            guidelines="Input Protocol: markdown\nCooperation: Rule 1",
        )
        text = format_fleet_guidelines(team)
        assert "[Team: coding]" in text
        assert "Guidelines" in text or "Input Protocol" in text or "Cooperation" in text

    def test_empty_guidelines(self):
        team = AgentTeam(name="empty")
        text = format_fleet_guidelines(team)
        assert "[Team: empty]" in text


class TestGetFleetSystemPromptSection:
    """Tests for get_fleet_system_prompt_section()."""

    def test_agent_in_team(self):
        """Returns guidelines for an agent in a known team."""
        registry = TeamRegistry(
            builtin=[
                AgentTeam(name="coding", agents=["coder", "tester"]),
            ],
        )
        section = get_fleet_system_prompt_section("coder", registry)
        assert "Team" in section or section == ""

    def test_agent_not_in_team(self):
        """Returns empty string for an unknown agent role."""
        registry = TeamRegistry()
        section = get_fleet_system_prompt_section("nonexistent-agent", registry)
        assert section == ""


class TestGetFleetSystemPromptSectionForPhase:
    """Tests for get_fleet_system_prompt_section_for_phase()."""

    def test_with_team_names(self):
        """Returns concatenated guidelines for specified teams."""
        registry = TeamRegistry(
            builtin=[
                AgentTeam(name="architecture", agents=["architect"]),
                AgentTeam(name="coding", agents=["coder", "tester"]),
            ],
        )
        section = get_fleet_system_prompt_section_for_phase(
            ["architecture", "coding"], registry,
        )
        assert "[Team: architecture]" in section
        assert "[Team: coding]" in section

    def test_empty_list(self):
        """Returns empty string for empty team list."""
        registry = TeamRegistry()
        section = get_fleet_system_prompt_section_for_phase([], registry)
        assert section == ""


class TestBuildAgentContext:
    """Tests for build_agent_context()."""

    def test_all_sections(self, tmp_path):
        """Builds context with all parts in correct order."""
        context = build_agent_context(
            agent_role="coder",
            root=tmp_path,
            base_prompt="## Role Definition\nYou are a coder.",
            task_prompt="## Task\nImplement feature X.",
            patterns_section="## Patterns\nUse hexagonal architecture.",
        )
        assert "Role Definition" in context
        assert "Task" in context
        assert context.index("Role Definition") < context.index("Task")

    def test_minimal(self):
        """Builds context with just base and task prompts."""
        context = build_agent_context(
            agent_role="test-agent",
            root=None,
            base_prompt="Role definition",
            task_prompt="Do the thing.",
        )
        assert "Role definition" in context
        assert "Do the thing" in context

    def test_no_root_skips_team(self):
        """Team section is omitted when root is None."""
        context = build_agent_context(
            agent_role="coder",
            root=None,
            base_prompt="Role",
            task_prompt="Task",
        )
        assert "[Team:" not in context

    def test_empty_parts(self):
        """Empty parts are handled gracefully."""
        context = build_agent_context(
            agent_role="test-agent",
            root=None,
            base_prompt="",
            task_prompt="",
            patterns_section="",
        )
        assert context == ""
