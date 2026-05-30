"""Package: agents — agent management and routing.

The harness's agent system provides:
- AgentRegistry (agent_registry.py) — catalogue of agent roles and SOPs
- AgentOrchestrator (orchestrator.py) — backend-agnostic LLM agent execution
- PluginRegistry (plugin_registry.py) — backend plugin discovery
- ContextPacket (context.py) — structured context for agent runs
- AgentTeam (team/model.py) — logical groupings of agents with guidelines
- TeamRegistry (team/registry.py) — manages AgentTeam definitions
- Validator (validator.py) — output contract validation

Note: CycleRunner (cycle.py) and AgentRunner (runner.py) have been deleted.
Use AgentOrchestrator for LLM agent execution. Use config-driven critic loops
via template steps in .harness/step_templates.yaml or LoopRunner with
convergence strategies from harness.loop.convergence instead.
"""

from harness.agents.agent_registry import (
    AGENTS,
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
from harness.agents.orchestrator import AgentOrchestrator
from harness.team.model import AgentTeam
from harness.team.registry import TeamRegistry

__all__ = [
    "LanguageDetector",
    "LanguagePatterns",
    "AGENTS",
    "AgentOrchestrator",
    # AgentRole — removed in Wave J; roles are plain strings
    "AgentSpec",
    "AgentTeam",
    "ConsultationOrchestrator",
    "ConsultationResult",
    "SYNC_AGENT",
    "TeamRegistry",
    "get_agent",
    "get_agents_by_tag",
    "list_agent_names",
    "list_agent_roles",
    "registry_summary",
]
