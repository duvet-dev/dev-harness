"""Package: agents — agent management and routing.

The harness's agent system provides:
- AgentRegistry (agent_registry.py) — catalogue of agent roles and SOPs
- AgentRunner (runner.py) — backend-agnostic LLM agent execution
- PluginRegistry (plugin_registry.py) — backend plugin discovery
- ContextPacket (context.py) — structured context for agent runs
- CycleRunner (cycle.py) — generic multi-agent iteration engine
- Fleet (fleet.py) — logical groupings of agents with guidelines
- Validator (validator.py) — output contract validation
"""

from harness.agents.agent_registry import (
    AGENTS,
    AgentRole,
    AgentSpec,
    get_agent,
    get_agents_by_tag,
    list_agent_names,
    list_agent_roles,
    registry_summary,
)
from harness.agents.builtin.sync_agent import SYNC_AGENT
from harness.agents.consultation import (
    ConsultationOrchestrator,
    ConsultationResult,
)
from harness.agents.detectors import LanguageDetector, LanguagePatterns
from harness.agents.cycle import (
    CycleConvergence,
    CycleResult,
    CycleRunner,
    CycleRunnerDefinition,
    CycleStep,
    CycleStepResult,
    design_cycle_definition,
    discovery_cycle_definition,
    get_cycle_definition,
    is_phase_jump_status,
    list_cycle_definitions,
    parse_phase_jump_target,
    planning_cycle_definition,
    review_cycle_definition,
    testing_cycle_definition,
    wave_cycle_definition,
)
from harness.agents.fleet import (
    ConsultationCapability,
    Fleet,
    FleetGuidelines,
    GovernanceLevel,
    InclusionRules,
    builtin_fleets,
)
from harness.agents.fleet_registry import FleetRegistry

__all__ = [
    "LanguageDetector",
    "LanguagePatterns",
    "AGENTS",
    "AgentRole",
    "AgentSpec",
    "ConsultationCapability",
    "ConsultationOrchestrator",
    "ConsultationResult",
    "CycleConvergence",
    "CycleResult",
    "CycleRunner",
    "CycleRunnerDefinition",
    "CycleStep",
    "CycleStepResult",
    "Fleet",
    "FleetGuidelines",
    "FleetRegistry",
    "GovernanceLevel",
    "InclusionRules",
    "SYNC_AGENT",
    "builtin_fleets",
    "design_cycle_definition",
    "discovery_cycle_definition",
    "get_cycle_definition",
    "is_phase_jump_status",
    "list_cycle_definitions",
    "parse_phase_jump_target",
    "planning_cycle_definition",
    "review_cycle_definition",
    "testing_cycle_definition",
    "wave_cycle_definition",
    "get_agent",
    "get_agents_by_tag",
    "list_agent_names",
    "list_agent_roles",
    "registry_summary",
]
