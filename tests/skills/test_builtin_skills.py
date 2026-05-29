"""Tests for built-in static skill content blocks
(skills/builtin/skill_blocks.py).

V7 §7 — Pre-defined static skill blocks for agent prompt injection.
"""

from __future__ import annotations

import pytest

from harness.skills.builtin.skill_blocks import get_builtin_skills


class TestBuiltinSkills:
    """Tests for the pre-defined built-in skills."""

    def test_returns_list(self) -> None:
        skills = get_builtin_skills()
        assert isinstance(skills, list)

    def test_all_skills_have_names(self) -> None:
        skills = get_builtin_skills()
        names = [s.skill_name for s in skills]
        assert len(names) == 4
        assert "web-search" in names
        assert "code-review" in names
        assert "test-writing" in names
        assert "architecture-review" in names

    def test_all_skills_have_content(self) -> None:
        skills = get_builtin_skills()
        for skill in skills:
            assert skill.content, (
                f"Skill '{skill.skill_name}' has no content"
            )

    def test_web_search_is_tool_type(self) -> None:
        skills = get_builtin_skills()
        web = {s.skill_name: s for s in skills}["web-search"]
        assert web.skill_type == "tool"

    def test_knowledge_skills_are_knowledge_type(self) -> None:
        skills = get_builtin_skills()
        for s in skills:
            if s.skill_name != "web-search":
                assert s.skill_type == "knowledge"

    def test_code_review_has_agents(self) -> None:
        skills = get_builtin_skills()
        cr = {s.skill_name: s for s in skills}["code-review"]
        assert cr.agents is not None
        assert "coding-agent" in cr.agents

    def test_web_search_has_no_agent_scope(self) -> None:
        skills = get_builtin_skills()
        ws = {s.skill_name: s for s in skills}["web-search"]
        assert ws.agents is None  # Project-wide

    def test_all_have_descriptions(self) -> None:
        skills = get_builtin_skills()
        for skill in skills:
            assert skill.description, (
                f"Skill '{skill.skill_name}' has no description"
            )
