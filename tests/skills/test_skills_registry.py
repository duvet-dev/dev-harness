"""Tests for SkillsRegistry (skills/registry.py).

V7 §5.22, §7 — Skills registry with project-wide and agent-specific
skill resolution.
"""

from __future__ import annotations

import pytest

from harness.errors import UnknownSkillError
from harness.skills.step import SkillStep
from harness.skills.registry import SkillsRegistry


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def empty_registry() -> SkillsRegistry:
    return SkillsRegistry()


@pytest.fixture
def sample_skills() -> list[SkillStep]:
    return [
        SkillStep(
            skill_name="web-search",
            skill_type="tool",
            description="Search the web",
            content="You can search the web.",
        ),
        SkillStep(
            skill_name="code-review",
            skill_type="knowledge",
            description="Code review guidelines",
            content="Check for correctness...",
            agents=[
                "coding-agent",
                "critical-analyser",
                "testing-agent",
            ],
        ),
        SkillStep(
            skill_name="test-writing",
            skill_type="knowledge",
            description="Test writing guidelines",
            content="Write tests first...",
            agents=["testing-agent"],
        ),
    ]


@pytest.fixture
def populated_registry(
    sample_skills: list[SkillStep],
) -> SkillsRegistry:
    return SkillsRegistry(skills=sample_skills)


# ── Registration ──────────────────────────────────────────────────────────


class TestRegister:
    """Tests for SkillsRegistry.register()."""

    def test_register_single(self, empty_registry) -> None:
        skill = SkillStep(
            skill_name="web-search",
            skill_type="tool",
            content="You can search the web.",
        )
        empty_registry.register(skill)
        assert empty_registry.count == 1
        assert empty_registry.list_skills() == ["web-search"]

    def test_register_duplicate_raises(self, populated_registry) -> None:
        with pytest.raises(UnknownSkillError) as exc:
            populated_registry.register(
                SkillStep(
                    skill_name="web-search",
                    skill_type="tool",
                    content="Duplicate",
                )
            )
        assert "already registered" in str(exc.value)

    def test_register_multiple(self, empty_registry) -> None:
        skills = [
            SkillStep(skill_name="a", skill_type="knowledge", content=""),
            SkillStep(skill_name="b", skill_type="knowledge", content=""),
        ]
        for s in skills:
            empty_registry.register(s)
        assert empty_registry.count == 2

    def test_register_via_constructor(
        self, sample_skills
    ) -> None:
        registry = SkillsRegistry(skills=sample_skills)
        assert registry.count == 3


# ── Resolution ────────────────────────────────────────────────────────────


class TestResolve:
    """Tests for SkillsRegistry.resolve()."""

    def test_resolve_existing(self, populated_registry) -> None:
        skill = populated_registry.resolve("web-search")
        assert skill.skill_name == "web-search"
        assert skill.skill_type == "tool"

    def test_resolve_nonexistent(self, populated_registry) -> None:
        with pytest.raises(UnknownSkillError) as exc:
            populated_registry.resolve("nonexistent")
        assert "nonexistent" in str(exc.value)

    def test_resolve_returns_correct_content(
        self, populated_registry
    ) -> None:
        skill = populated_registry.resolve("code-review")
        assert "Check for correctness" in skill.content

    def test_resolve_from_empty(self, empty_registry) -> None:
        with pytest.raises(UnknownSkillError):
            empty_registry.resolve("anything")


# ── Agent-Specific Resolution ─────────────────────────────────────────────


class TestResolveForAgent:
    """Tests for SkillsRegistry.resolve_for_agent()."""

    def test_project_wide_skill_applies_to_all(
        self, populated_registry
    ) -> None:
        """Project-wide skills (agents=None) apply to every agent."""
        skills = populated_registry.resolve_for_agent("any-agent")
        names = [s.skill_name for s in skills]
        assert "web-search" in names  # project-wide

    def test_agent_specific_skill_applies_to_target(
        self, populated_registry
    ) -> None:
        skills = populated_registry.resolve_for_agent("testing-agent")
        names = [s.skill_name for s in skills]
        assert "test-writing" in names
        assert "code-review" in names

    def test_agent_does_not_get_other_agents_skills(
        self, populated_registry
    ) -> None:
        skills = populated_registry.resolve_for_agent(
            "critical-analyser"
        )
        names = [s.skill_name for s in skills]
        assert "code-review" in names
        assert "test-writing" not in names  # scoped to testing-agent

    def test_unknown_agent_gets_only_project_wide(
        self, populated_registry
    ) -> None:
        skills = populated_registry.resolve_for_agent(
            "unknown-agent"
        )
        names = [s.skill_name for s in skills]
        assert names == ["web-search"]  # only the project-wide one

    def test_empty_registry_returns_empty(
        self, empty_registry
    ) -> None:
        skills = empty_registry.resolve_for_agent("any-agent")
        assert skills == []


# ── Listing ────────────────────────────────────────────────────────────────


class TestListSkills:
    """Tests for SkillsRegistry.list_skills()."""

    def test_list_empty(self, empty_registry) -> None:
        assert empty_registry.list_skills() == []

    def test_list_sorted(self, populated_registry) -> None:
        names = populated_registry.list_skills()
        assert names == ["code-review", "test-writing", "web-search"]
        assert names == sorted(names)

    def test_list_after_add(self, empty_registry) -> None:
        empty_registry.register(
            SkillStep(
                skill_name="beta", skill_type="knowledge", content=""
            )
        )
        empty_registry.register(
            SkillStep(
                skill_name="alpha", skill_type="knowledge", content=""
            )
        )
        assert empty_registry.list_skills() == ["alpha", "beta"]
