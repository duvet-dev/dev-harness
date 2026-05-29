"""SkillsRegistry — V7 §5.22, §7.

Manages static skill content blocks that are injected into agent
prompts. Skills are defined in ``.harness/skills.yaml`` and can be
project-wide or agent-specific.

The registry supports:
- Registering skills by name with optional agent scoping
- Resolving skill content by name
- Resolving all skills applicable to a given agent
- Listing all registered skill names

Skills are static content blocks only (no Jinja2 — dynamic injection
deferred to a later wave).
"""

from __future__ import annotations

from harness.errors import UnknownSkillError
from harness.skills.step import SkillStep


class SkillsRegistry:
    """Registry of static skill content blocks for agent prompt injection.

    Skills are registered as SkillStep objects and can be scoped to
    specific agents (``agents:`` field) or left project-wide
    (``agents: None``, applies to all agents).

    Args:
        skills: Optional initial list of SkillStep objects to register.

    Usage::

        registry = SkillsRegistry()
        registry.register(skill_step)
        content = registry.resolve("web-search")
        agent_skills = registry.resolve_for_agent("coding-agent")
        names = registry.list_skills()
    """

    def __init__(
        self,
        skills: list[SkillStep] | None = None,
    ) -> None:
        self._skills: dict[str, SkillStep] = {}
        if skills:
            for skill in skills:
                self.register(skill)

    def register(self, skill: SkillStep) -> None:
        """Register a skill.

        Args:
            skill: The SkillStep to register.

        Raises:
            UnknownSkillError: If a skill with the same name is
                already registered.
        """
        name = skill.skill_name
        if name in self._skills:
            raise UnknownSkillError(
                f"Skill '{name}' is already registered"
            )
        self._skills[name] = skill

    def resolve(self, skill_name: str) -> SkillStep:
        """Get a skill by name.

        Args:
            skill_name: The skill name to look up.

        Returns:
            The matching SkillStep.

        Raises:
            UnknownSkillError: If no skill with the given name is
                registered.
        """
        if skill_name not in self._skills:
            raise UnknownSkillError(
                f"Skill '{skill_name}' not found in registry"
            )
        return self._skills[skill_name]

    def resolve_for_agent(self, agent_name: str) -> list[SkillStep]:
        """Get all skills applicable to a specific agent.

        Returns both project-wide skills (no agent restriction) and
        skills explicitly scoped to the given agent.

        Args:
            agent_name: The agent name to filter skills for.

        Returns:
            List of SkillStep objects applicable to the agent.
        """
        result: list[SkillStep] = []
        for skill in self._skills.values():
            if skill.agents is None:
                # Project-wide skill: applies to all agents
                result.append(skill)
            elif agent_name in skill.agents:
                # Agent-specific skill
                result.append(skill)
        return result

    def list_skills(self) -> list[str]:
        """List all registered skill names.

        Returns:
            Sorted list of skill names.
        """
        return sorted(self._skills.keys())

    @property
    def count(self) -> int:
        """Return the number of registered skills."""
        return len(self._skills)
