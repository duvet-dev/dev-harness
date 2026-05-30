"""Context builder — injects team guidelines and patterns into agent prompts.

Manages the ordered injection of team-level guidelines, project-specific
patterns, and language-idiomatic rules into agent system prompts.

The canonical injection order for every agent invocation is:

    1. Role definition (SOP / identity)
    2. Team guidelines (from AgentTeam via TeamRegistry)
    3. Injected patterns (project-specific, sorted by priority)
    4. Task prompt (the current assignment)

Wave 17 — Phase 2 (Fleet Guidelines & Injection).
Migrated from Fleet/FleetRegistry to AgentTeam/TeamRegistry in Phase 2.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from harness.team.model import AgentTeam
from harness.team.registry import TeamRegistry


def format_fleet_guidelines(team: AgentTeam) -> str:
    """Format team guidelines as a markdown block for injection.

    Produces a structured block that can be inserted into an agent's
    system prompt. Accepts an AgentTeam (or backward-compatible Fleet).
    """
    parts = [f"[Team: {team.name}]"]

    guidelines = getattr(team, "guidelines", None)
    if guidelines:
        if isinstance(guidelines, str):
            parts.append("Guidelines:")
            for line in guidelines.split("\n"):
                parts.append(f"  {line}")
        elif isinstance(guidelines, dict):
            # Structured guidelines
            input_proto = guidelines.get("input_protocol", {})
            output_proto = guidelines.get("output_protocol", {})
            cooperation = guidelines.get("cooperation", [])
            phases = guidelines.get("phases", [])

            if input_proto:
                parts.append("Input Protocol:")
                parts.append(f"  Format: {input_proto.get('format', 'markdown')}")
                req = input_proto.get("required_sections", [])
                if req:
                    parts.append(f"  Required Sections: {', '.join(req)}")

            if output_proto:
                parts.append("Output Protocol:")
                parts.append(f"  Format: {output_proto.get('format', 'markdown')}")
                req = output_proto.get("required_sections", [])
                if req:
                    parts.append(f"  Required Sections: {', '.join(req)}")

            if cooperation:
                parts.append("Cooperation Rules:")
                for rule in cooperation:
                    parts.append(f"  - {rule}")

            if phases:
                parts.append(f"Participates in Phases: {', '.join(phases)}")
        else:
            parts.append(f"Guidelines: {str(guidelines)}")

    return "\n".join(parts)


def get_fleet_system_prompt_section(
    agent_role: str,
    registry: TeamRegistry,
) -> str:
    """Build the team guidelines section for an agent.

    Returns a string to be injected into the system prompt, or an
    empty string if the agent is not part of any team.

    The returned string includes ``[Team: ...]`` delimiters so the
    agent can distinguish team guidelines from its role definition.

    Args:
        agent_role: The agent role string (e.g. ``"architect"``).
        registry: A TeamRegistry instance.

    Returns:
        Guidelines section string, or empty string.
    """
    # Find which team this agent belongs to by scanning team agents lists
    team_name = None
    for name in registry.list_teams():
        try:
            team = registry.resolve(name)
            if agent_role in team.agents or team.name == agent_role:
                team_name = name
                break
        except Exception:
            pass

    if team_name is None:
        return ""

    try:
        team = registry.resolve(team_name)
        return format_fleet_guidelines(team)
    except Exception:
        return ""


def get_fleet_system_prompt_section_for_phase(
    team_names: list[str],
    registry: TeamRegistry,
) -> str:
    """Build the combined team guidelines section for a list of team names.

    Returns a string with guidelines from all the given teams concatenated,
    or an empty string if no teams are specified. Each team's guidelines
    are separated by ``\n\n---\n\n``.

    Args:
        team_names: List of team names.
        registry: A TeamRegistry instance.

    Returns:
        Combined guidelines string, or empty string.
    """
    if not team_names:
        return ""

    sections: list[str] = []
    for name in team_names:
        try:
            team = registry.resolve(name)
            sections.append(format_fleet_guidelines(team))
        except Exception:
            pass

    if not sections:
        return ""

    return "\n\n---\n\n".join(sections)


def build_agent_context(
    agent_role: str,
    root: Optional[Path] = None,
    base_prompt: str = "",
    task_prompt: str = "",
    patterns_section: str = "",
) -> str:
    """Build the full context for an agent invocation.

    Produces the canonical order:

        1. Base prompt (role definition / SOP)
        2. Team guidelines (via TeamRegistry)
        3. Injected patterns
        4. Task prompt

    Args:
        agent_role: The agent's role string (e.g. ``"architect"``).
        root: Project root for loading team configuration.
            If ``None``, team guidelines are omitted.
        base_prompt: The agent's role definition / system prompt.
        task_prompt: The current task prompt.
        patterns_section: Pre-formatted patterns section from the
            pattern injection system (Phase 3).

    Returns:
        The assembled context string.
    """
    parts = []

    if base_prompt:
        parts.append(base_prompt)

    # Team guidelines from registry
    if root is not None:
        from harness.team.defaults import get_builtin_teams

        registry = TeamRegistry(builtin=get_builtin_teams())
        fleet_section = get_fleet_system_prompt_section(agent_role, registry)
        if fleet_section:
            parts.append(fleet_section)

    # Injected patterns
    if patterns_section:
        parts.append(patterns_section)

    # Task prompt
    if task_prompt:
        parts.append(task_prompt)

    return "\n\n".join(parts)
