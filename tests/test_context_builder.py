"""Tests for harness.agents.context_builder — fleet guideline injection.

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
from harness.agents.fleet import Fleet, FleetGuidelines, InclusionRules
from harness.agents.fleet_registry import FleetRegistry


class TestFormatFleetGuidelines:
    """Tests for format_fleet_guidelines()."""

    def test_basic_format(self):
        fleet = Fleet(
            name="coding",
            lead_role="coding-agent",
            guidelines=FleetGuidelines(
                input_protocol={"format": "markdown", "required_sections": ["spec"]},
                output_protocol={"format": "code", "required_sections": ["impl"]},
                cooperation=["Rule 1", "Rule 2"],
                phases=["implementation"],
            ),
        )
        text = format_fleet_guidelines(fleet)
        assert "[Fleet: coding]" in text
        assert "Input Protocol" in text
        assert "Output Protocol" in text
        assert "Cooperation Rules" in text
        assert "Rule 1" in text
        assert "implementation" in text

    def test_empty_cooperation(self):
        fleet = Fleet(
            name="empty",
            lead_role="coordinator",
            guidelines=FleetGuidelines(),
        )
        text = format_fleet_guidelines(fleet)
        assert "[Fleet: empty]" in text
        # Should not contain Cooperation Rules if empty
        assert "Cooperation Rules" not in text


class TestGetFleetSystemPromptSection:
    """Tests for get_fleet_system_prompt_section()."""

    def test_agent_in_fleet(self, tmp_path):
        """Returns fleet guidelines for an agent in a known fleet."""
        registry = FleetRegistry(tmp_path)
        section = get_fleet_system_prompt_section("coding-agent", registry)
        # coding-agent should be in the coding fleet
        assert "Fleet" in section

    def test_agent_not_in_fleet(self, tmp_path):
        """Returns empty string for an unknown agent role."""
        registry = FleetRegistry(tmp_path)
        section = get_fleet_system_prompt_section("nonexistent-agent", registry)
        assert section == ""


class TestGetFleetSystemPromptSectionForPhase:
    """Tests for get_fleet_system_prompt_section_for_phase()."""

    def test_with_fleet_names(self, tmp_path):
        """Returns concatenated guidelines for specified fleets."""
        registry = FleetRegistry(tmp_path)
        section = get_fleet_system_prompt_section_for_phase(
            ["architecture", "coding"], registry,
        )
        assert "[Fleet: architecture]" in section
        assert "[Fleet: coding]" in section

    def test_empty_list(self, tmp_path):
        """Returns empty string for empty fleet list."""
        registry = FleetRegistry(tmp_path)
        section = get_fleet_system_prompt_section_for_phase([], registry)
        assert section == ""


class TestBuildAgentContext:
    """Tests for build_agent_context()."""

    def test_all_sections(self, tmp_path):
        """Builds context with all parts in correct order."""
        context = build_agent_context(
            agent_role="coding-agent",
            root=tmp_path,
            base_prompt="## Role Definition\nYou are a coder.",
            task_prompt="## Task\nImplement feature X.",
            patterns_section="## Patterns\nUse hexagonal architecture.",
        )
        assert "Role Definition" in context
        assert "Task" in context
        # Fleet section should be present (coding-agent is in coding fleet)
        # The order should be: base prompt, fleet section, patterns, task
        assert context.index("Role Definition") < context.index("Task")
        # Fleet section should exist
        assert "Fleet" in context

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

    def test_no_root_skips_fleet(self):
        """Fleet section is omitted when root is None."""
        context = build_agent_context(
            agent_role="coding-agent",
            root=None,
            base_prompt="Role",
            task_prompt="Task",
        )
        assert "[Fleet:" not in context

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
