"""String-keyed agent catalogue — V7 §10.6.

Replaces the AgentRole enum with a string-keyed data catalogue.
Agents are identified by string name and mapped to AgentDefinition
objects containing name, description, capabilities, and default tools.

This is a data catalogue, not a runtime dispatch system. Runtime
agent dispatch (StepDispatcher) is in Wave 2.

See V7 §10.6 for the migration path from AgentRole.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from harness.errors import UnknownAgentError


@dataclass
class AgentDefinition:
    """Definition of an agent in the string-keyed catalogue.

    Attributes:
        name: Unique string identifier for the agent.
        description: Human-readable description of the agent's role.
        capabilities: List of capability identifiers.
        default_tools: List of default tool names available to
            this agent.
    """

    name: str
    description: str
    capabilities: list[str] = field(default_factory=list)
    default_tools: list[str] = field(default_factory=list)


class AgentCatalogue:
    """String-keyed catalogue of agent definitions.

    Maps string agent names to AgentDefinition objects. Supports
    lookup, listing, and registration of agents.

    Usage::

        catalogue = AgentCatalogue()
        architect = catalogue.resolve("architect")
        all_agents = catalogue.list_agents()
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentDefinition] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load the default agent definitions.

        These correspond to the agents referenced by the 7 built-in
        teams from V7 §10.1.
        """
        self._agents = {
            "architect": AgentDefinition(
                name="architect",
                description="Produces architecture designs and overviews",
                capabilities=["architecture-design", "overview-writing"],
            ),
            "architecture-critic": AgentDefinition(
                name="architecture-critic",
                description="Critiques architecture designs",
                capabilities=["architecture-review", "critical-analysis"],
            ),
            "code-critic": AgentDefinition(
                name="code-critic",
                description="Reviews code for quality and correctness",
                capabilities=["code-review"],
            ),
            "security-critic": AgentDefinition(
                name="security-critic",
                description="Reviews for security vulnerabilities",
                capabilities=["security-review"],
            ),
            "coding-agent": AgentDefinition(
                name="coding-agent",
                description="Implements code changes",
                capabilities=["coding", "implementation"],
            ),
            "testing-agent": AgentDefinition(
                name="testing-agent",
                description="Writes and runs tests",
                capabilities=["testing", "coverage-analysis"],
            ),
            "test-coverage-analyser": AgentDefinition(
                name="test-coverage-analyser",
                description="Analyses test coverage quality",
                capabilities=["coverage-analysis"],
            ),
            "design-reviewer": AgentDefinition(
                name="design-reviewer",
                description="Reviews design documents",
                capabilities=["design-review"],
            ),
            "critical-analyser": AgentDefinition(
                name="critical-analyser",
                description="Holistic critical analysis",
                capabilities=["critical-analysis"],
            ),
            "security-auditor": AgentDefinition(
                name="security-auditor",
                description="Audits security posture",
                capabilities=["security-audit"],
            ),
            "planning-agent": AgentDefinition(
                name="planning-agent",
                description="Breaks work into tasks and plans",
                capabilities=["planning", "task-decomposition"],
            ),
            "dependency-analyser": AgentDefinition(
                name="dependency-analyser",
                description="Analyses dependencies",
                capabilities=["dependency-analysis"],
            ),
            "discovery-agent": AgentDefinition(
                name="discovery-agent",
                description="Discovers and researches",
                capabilities=["research", "discovery"],
            ),
            "research-agent": AgentDefinition(
                name="research-agent",
                description="Conducts research",
                capabilities=["research"],
            ),
            "validation-agent": AgentDefinition(
                name="validation-agent",
                description="Validates against requirements",
                capabilities=["validation", "requirements-checking"],
            ),
            "example-scenarios-agent": AgentDefinition(
                name="example-scenarios-agent",
                description="Creates example scenarios",
                capabilities=["example-creation", "scenario-writing"],
            ),
        }

    def resolve(self, name: str) -> AgentDefinition:
        """Look up an agent definition by string name.

        Args:
            name: The string name of the agent.

        Returns:
            The matching AgentDefinition.

        Raises:
            UnknownAgentError: If no agent with the given name is
                registered.
        """
        if name not in self._agents:
            raise UnknownAgentError(f"Unknown agent: '{name}'")
        return self._agents[name]

    def list_agents(self) -> list[str]:
        """Return all registered agent names.

        Returns:
            Sorted list of agent string names.
        """
        return sorted(self._agents.keys())

    def register(self, definition: AgentDefinition) -> None:
        """Register or update an agent definition.

        If an agent with the same name already exists, it is replaced.
        This allows project/user config to override built-in definitions.

        Args:
            definition: The AgentDefinition to register.
        """
        self._agents[definition.name] = definition

    @property
    def count(self) -> int:
        """Return the number of registered agents."""
        return len(self._agents)
