"""SkillStep dataclass — V7 §8 error hierarchy.

A SkillStep represents a step that invokes a registered skill. This is
a lightweight wrapper that connects skill content blocks to the agent
dispatch system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SkillStep:
    """A step that invokes a registered skill.

    Attributes:
        skill_name: Name of the skill to invoke.
        skill_type: Type of the skill ('tool' or 'knowledge').
        description: Human-readable description of the skill.
        content: The skill's content block to inject.
        agents: Optional list of agent names this skill applies to.
            If None, the skill is project-wide.
    """

    skill_name: str
    skill_type: str = "knowledge"
    description: str | None = None
    content: str = ""
    agents: list[str] | None = None
