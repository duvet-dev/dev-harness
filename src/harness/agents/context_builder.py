"""Context builder — injects fleet guidelines and patterns into agent prompts.

Manages the ordered injection of fleet-level guidelines, project-specific
patterns, and language-idiomatic rules into agent system prompts.

The canonical injection order for every agent invocation is:

    1. Role definition (SOP / identity)
    2. Fleet guidelines (inherited from the agent's fleet)
    3. Injected patterns (project-specific, sorted by priority)
    4. Task prompt (the current assignment)

Wave 17 — Phase 2 (Fleet Guidelines & Injection).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from harness.agents.fleet import Fleet
from harness.agents.fleet_registry import FleetRegistry


def format_fleet_guidelines(fleet: Fleet) -> str:
    """Format fleet guidelines as a markdown block for injection.

    Produces a structured block that can be inserted into an agent's
    system prompt:
    """
    parts = [f"[Fleet: {fleet.name}]"]

    # Input protocol
    ip = fleet.guidelines.input_protocol
    parts.append("Input Protocol:")
    parts.append(f"  Format: {ip.get('format', 'markdown')}")
    req_sections = ip.get("required_sections", [])
    if req_sections:
        parts.append(f"  Required Sections: {', '.join(req_sections)}")

    # Output protocol
    op = fleet.guidelines.output_protocol
    parts.append("Output Protocol:")
    parts.append(f"  Format: {op.get('format', 'markdown')}")
    req_sections = op.get("required_sections", [])
    if req_sections:
        parts.append(f"  Required Sections: {', '.join(req_sections)}")

    # Cooperation rules
    cooperation = fleet.guidelines.cooperation
    if cooperation:
        parts.append("Cooperation Rules:")
        for rule in cooperation:
            parts.append(f"  - {rule}")

    # Phase participation
    phases = fleet.guidelines.phases
    if phases:
        parts.append(f"Participates in Phases: {', '.join(phases)}")

    return "\n".join(parts)


def get_fleet_system_prompt_section(
    agent_role: str,
    registry: FleetRegistry,
) -> str:
    """Build the fleet guidelines section for an agent.

    Returns a string to be injected into the system prompt, or an
    empty string if the agent is not part of any fleet.

    The returned string includes ``[Fleet: ...]`` delimiters so the
    agent can distinguish fleet guidelines from its role definition.
    """
    fleet_name = registry.find_fleet_for_agent(agent_role)
    if fleet_name is None:
        return ""

    fleet = registry.get_fleet(fleet_name)
    if fleet is None:
        return ""

    return format_fleet_guidelines(fleet)


def get_fleet_system_prompt_section_for_phase(
    fleet_names: list[str],
    registry: FleetRegistry,
) -> str:
    """Build the combined fleet guidelines section for a list of fleet names.

    Returns a string with guidelines from all the given fleets concatenated,
    or an empty string if no fleets are specified. Each fleet's guidelines
    are separated by ``\n\n---\n\n``.

    This is the Phase 2 replacement for
    :func:`get_fleet_system_prompt_section` — instead of looking up which
    fleet an agent belongs to, the phase explicitly declares which fleets
    participate via the ``fleets`` key in :data:`PHASES <PHASES>`.
    """
    if not fleet_names:
        return ""

    sections: list[str] = []
    for name in fleet_names:
        fleet = registry.get_fleet(name)
        if fleet is not None:
            sections.append(format_fleet_guidelines(fleet))

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
        2. Fleet guidelines
        3. Injected patterns
        4. Task prompt

    Args:
        agent_role: The agent's role string (e.g. ``"architect"``).
        root: Project root for loading fleet configuration.
            If ``None``, fleet guidelines are omitted.
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

    # Fleet guidelines from registry
    if root is not None:
        registry = FleetRegistry(root)
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
