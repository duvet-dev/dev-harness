"""Agent registry — the harness's own catalogue of build agents.

Each agent is a named role with a description and SOP (Standard Operating
Procedure). This registry forms the basis of the harness's agentic
framework — the coordinator dispatches work to agents by name, and each
agent owns its own HOW from its SOP and AGENTS.md.

The agents defined here are the same 10 agents that built the harness
itself, reflected from the OpenClaw sub-agent definitions at
`Research/Dev Harness/agent-definitions.md`.

Architecture §2 — Agent System.
"""

from __future__ import annotations

import warnings

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass
class ToolPermissions:
    """Permissions for the Agent Read/Write Tool (Wave 13) and
    Web Search Tool (Wave 19).

    Attributes:
        read: Whether the agent can read files.
        write: Whether the agent can write files.
        write_prefixes: Allow-list of directory prefixes for writes.
            ``None`` means unrestricted (any path in the repo).
            An empty list means no write access even if ``write=True``.
        web_search: Whether the agent can search the web.
    """

    read: bool = True
    write: bool = True
    write_prefixes: list[str] | None = None  # None = any path
    web_search: bool = True

    @classmethod
    def read_only(cls) -> ToolPermissions:
        """Convenience for agents that only need read access."""
        return cls(read=True, write=False, web_search=True)

    @classmethod
    def restricted_write(cls, prefixes: list[str]) -> ToolPermissions:
        """Convenience for agents limited to specific directories."""
        return cls(read=True, write=True, write_prefixes=prefixes, web_search=True)

    @classmethod
    def unrestricted(cls) -> ToolPermissions:
        """Convenience for agents that can write anywhere."""
        return cls(read=True, write=True, write_prefixes=None, web_search=True)

    @classmethod
    def with_web_search(
        cls,
        read: bool = True,
        write: bool = False,
        write_prefixes: list[str] | None = None,
    ) -> ToolPermissions:
        """Convenience for agents that need both filesystem and web access.

        Note: web_search is now True by default for all agents.
        This method exists for backward compatibility.
        """
        return cls(
            read=read,
            write=write,
            write_prefixes=write_prefixes,
            web_search=True,
        )




class CriticLoopState(str, Enum):
    """States for the design-critic multi-agent loop."""

    RUNNING = "running"
    CONVERGED = "converged"
    MAX_ITERATIONS_REACHED = "max-iterations"
    ERROR = "error"


from harness.phase.model import ConvergenceConfig


@dataclass
class CriticLoopIteration:
    """Snapshot of a single architect→critic cycle."""

    iteration: int
    """Iteration number (0-indexed)."""

    architect_artifacts: dict[str, str] = field(default_factory=dict)
    """Artifacts produced by the architect in this iteration.
    Map of filename → content."""

    critic_artifacts: dict[str, str] = field(default_factory=dict)
    """Artifacts produced by the critic in this iteration.
    Map of filename → content."""

    converged: bool = False
    """Whether the critic signalled convergence in this iteration."""


@dataclass
class AgentSpec:
    """Specification for a single agent role."""

    role: str
    name: str
    description: str
    sop_summary: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    tool_permissions: ToolPermissions | None = None
    """Access permissions for the Agent Read/Write Tool (Wave 13).

    ``None`` means the agent has no access to the tool at all.
    Set to a ``ToolPermissions`` instance to grant access.
    """


# ---------------------------------------------------------------------------
# Agent specifications — one per role
# ---------------------------------------------------------------------------

AGENTS: list[AgentSpec] = [
    AgentSpec(
        role="coordinator",
        name="Harness Coordinator",
        description=(
            "Top-level orchestrator. Manages the build plan, dispatches "
            "work to the right agent, tracks progress, manages feedback "
            "loops, and produces status summaries."
        ),
        sop_summary=[
            "Receive brief and decompose into tasks",
            "Dispatch to the appropriate agent with context",
            "Monitor progress and detect blockers",
            "Validate output before marking complete",
            "Produce status summaries on demand",
            "Detect session type and route to appropriate orchestration loop",
        ],
        tags=["orchestrator", "core"],
        tool_permissions=ToolPermissions.read_only(),
    ),
    AgentSpec(
        role="requirements-builder",
        name="Requirements Builder",
        description=(
            "Takes raw input (voice notes, briefs, discussions) and "
            "turns them into structured, well-defined requirements."
        ),
        sop_summary=[
            "Extract individual requirements from raw material",
            "Group by thematic cluster and assign priorities",
            "Flag ambiguities, gaps, and contradictions",
            "Produce structured requirements doc",
        ],
        tags=["requirements", "analysis"],
        tool_permissions=ToolPermissions.restricted_write(
            ['.harness/engagements/<slug>/requirements/']
        ),
    ),
    AgentSpec(
        role="architect",
        name="Architect",
        description=(
            "Produces technical architectures from requirements, "
            "applying DDD, Clean Architecture, hexagonal architecture, "
            "anti-corruption layers, adapter isolation, and SOLID "
            "principles. In brownfield mode, understands it is constrained "
            "by existing code and documents compromises."
        ),
        sop_summary=[
            "Analyse requirements and identify domain boundaries",
            "Produce domain model, context map, and aggregate designs",
            "Use hexagonal/clean architecture as default output pattern",
            "Design anti-corruption layers between bounded contexts",
            "Design adapter interfaces that isolate domain from infrastructure",
            "Design for testability: explicit boundaries with seam identification",
            "In brownfield mode: document compromises from ideal architecture",
            "Document decisions with rationale and alternatives",
            "Iterate based on architecture review feedback",
        ],
        tags=["architecture", "design", "hexagonal", "testing"],
        tool_permissions=ToolPermissions.restricted_write(
            ['.harness/engagements/<slug>/design/', '.harness/engagements/<slug>/architecture/']
        ),
    ),
    AgentSpec(
        role="architecture-analyser",
        name="Architecture Analyser",
        description=(
            "Critical second opinion on architectures. Probes for mixed "
            "concerns, tight coupling, boundary violations, ACL completeness, "
            "domain isolation, and risks."
        ),
        sop_summary=[
            "Review architecture for structural issues",
            "Flag mixed concerns, boundary violations, anti-patterns",
            "Assess anti-corruption layer completeness",
            "Check domain isolation from external concerns",
            "Flag missing adapter boundaries",
            "Verify test seam adequacy",
            "Check performance bottlenecks and scaling limits",
            "Produce findings by severity with recommendations",
            "Zero magic: flag EVERY inline literal (string, number, value) that should "
            "be a named constant, enum, or resolver function. No exceptions.",
        ],
        tags=["architecture", "review", "quality", "acls", "testing"],
        tool_permissions=ToolPermissions.read_only(),
    ),
    AgentSpec(
        role="planning-agent",
        name="Planning Agent",
        description=(
            "Decomposes architecture into manageable implementation "
            "chunks and creates individual tasks for coding agents."
        ),
        sop_summary=[
            "Break architecture into independently-buildable pieces",
            "Determine dependency order (DAG)",
            "Assign agent roles and estimate effort per task",
            "Flag oversized or undersized work items",
        ],
        tags=["planning", "project-management"],
        tool_permissions=ToolPermissions.restricted_write(
            ['.harness/engagements/']
        ),
    ),
    AgentSpec(
        role="coding-agent",
        name="Coding Agent",
        description=(
            "Implements code per spec and architecture. Follows SOLID, "
            "writes to adapter and anti-corruption layer interfaces, "
            "tests at boundaries not internals, and preserves existing "
            "behaviour via boundary tests."
        ),
        sop_summary=[
            "Implement code per task description and architecture",
            "Write to adapter and anti-corruption layer interfaces",
            "Test at boundaries (domain interfaces, not implementation details)",
            "Build CI-viable test suites using mocks",
            "In brownfield mode: preserve existing behaviour, pass existing tests",
            "In refactoring mode: boundary tests are IMMUTABLE — only implementation changes",
            "Follow SOLID principles and dependency rules",
            "Handle failure cases, edge cases, and errors",
            "Zero magic: every literal must be a named constant, enum, or resolver function. "
            "No raw strings, numbers, or values anywhere — not even single-use. "
            "Group constants by domain/component in dedicated modules.",
        ],
        tags=["implementation", "core", "testing", "clean-architecture"],
        tool_permissions=ToolPermissions.unrestricted(),
    ),
    AgentSpec(
        role="testing-agent",
        name="Testing Agent",
        description=(
            "Tests code with a behaviour-first philosophy. Tests "
            "interfaces, not implementations. Supports boundary test "
            "generation for behaviour preservation during refactoring."
        ),
        sop_summary=[
            "Write tests against interfaces (not implementations)",
            "Test expected behaviour from specifications",
            "Cover edge cases, boundary conditions, failure modes",
            "Build CI-viable test suites using mocks at domain boundaries",
            "Mark boundary tests as immutable during refactoring sessions",
            "Ensure test isolation and independent runnability",
        ],
        tags=["testing", "quality", "boundaries"],
        tool_permissions=ToolPermissions.unrestricted(),
    ),
    AgentSpec(
        role="critical-analyser",
        name="Critical Analyser",
        description=(
            "Inspects code, tests, and infrastructure holistically. "
            "Finds logic holes, coverage gaps, and system-level risks."
        ),
        sop_summary=[
            "Review code for logic holes and incorrect assumptions",
            "Analyse test coverage by intent and by code path",
            "Check integration points and failure isolation",
            "Produce report with findings by category and severity",
            "Zero magic: flag EVERY inline literal (string, number, value) that should "
            "be a named constant, enum, or resolver function. No exceptions.",
        ],
        tags=["review", "quality", "security"],
        tool_permissions=ToolPermissions.restricted_write(
            ['.harness/engagements/<slug>/reviews/', '.harness/engagements/<slug>/design/']
        ),
    ),
    AgentSpec(
        role="validation-agent",
        name="Validation Agent",
        description=(
            "Validates that the build output meets all requirements across "
            "three dimensions:\n"
            "1. Tests against requirements — Does the test suite cover "
            "every requirement?\n"
            "2. Tests against code — Do tests actually validate what "
            "they claim?\n"
            "3. Domain language against requirements — Is the ubiquitous "
            "language consistent across reqs, code, and tests?\n"
            "The bridge between 'what was asked for' and 'what was built'."
        ),
        sop_summary=[
            "Verify tests against requirements: map each requirement to specific "
            "tests, flag untested requirements, verify tests exercise stated "
            "behaviour (not superficial assertions)",
            "Verify tests against code: check test assertions validate intended "
            "behaviour, flag no-op checks, always-true conditions, over-mocked "
            "boundaries, and shared state issues",
            "Verify domain language against requirements: build a domain glossary "
            "from codebase and compare against requirements, flag inconsistencies "
            "in terminology across code, tests, and specifications",
            "Produce a structured Validation Report with three sections: "
            "Requirements Coverage matrix, Test Correctness analysis, and "
            "Domain Language Consistency audit",
        ],
        tags=["validation", "quality", "requirements", "conformance", "coverage"],
        tool_permissions=ToolPermissions.read_only(),
    ),
    AgentSpec(
        role="documentation-agent",
        name="Documentation Agent",
        description=(
            "Creates and maintains development and usage documentation "
            "in the project's docs/ directory."
        ),
        sop_summary=[
            "Generate developer docs from architecture and code",
            "Generate user-facing docs (commands, examples)",
            "Update docs after each build wave",
            "Maintain changelogs and migration guides",
        ],
        tags=["documentation", "devx"],
        tool_permissions=ToolPermissions.restricted_write(
            ['docs/', '.harness/engagements/<slug>/']
        ),
    ),
    AgentSpec(
        role="example-scenarios-agent",
        name="Example Scenarios Agent",
        description=(
            "Creates runnable example scenarios as versioned snapshots "
            "that serve as both documentation and integration tests."
        ),
        sop_summary=[
            "Design example scenarios that exercise features",
            "Implement as versioned snapshots",
            "Verify examples are runnable end-to-end",
            "Maintain example documentation",
        ],
        tags=["examples", "documentation", "testing"],
        tool_permissions=ToolPermissions.restricted_write(
            ['examples/', 'tests/']
        ),
    ),
    AgentSpec(
        role="discovery-agent",
        name="Discovery Agent",
        description=(
            "Ideation and research. Explores new patterns, evaluates "
            "technologies, and assesses value before committing to build."
        ),
        sop_summary=[
            "Research and evaluate new technologies and patterns",
            "Assess value and risk before committing to build",
            "Integrate findings into requirements and architecture",
        ],
        tags=["research", "exploration", "ideation"],
        tool_permissions=ToolPermissions.with_web_search(),
    ),
    # ── Wave 16a: Refactoring / Brownfield Agents ──────────────────────
    AgentSpec(
        role="refactoring-agent",
        name="Refactoring Agent",
        description=(
            "Understands project intent, feeds the architecture loop to "
            "produce an ideal target architecture, assesses migration effort, "
            "and hands off refactoring steps to coding agents. Does not "
            "write code directly."
        ),
        sop_summary=[
            "Understand intent: analyse project purpose, validate with user",
            "Feed into architecture loop: feed intent + constraints to architect",
            "Assess migration effort: evaluate work from existing to proposed",
            "Produce boundary test specification for boundary-test-agent",
            "Hand off to coding agents for refactoring implementation",
            "Verify: confirm boundary tests pass post-refactoring",
        ],
        tags=["refactoring", "architecture", "analysis", "migration"],
        tool_permissions=ToolPermissions.restricted_write(
            ['.harness/engagements/<slug>/refactoring/', '.harness/engagements/<slug>/plan/']
        ),
    ),
    AgentSpec(
        role="boundary-test-agent",
        name="Boundary Test Agent",
        description=(
            "Generates behaviour-capturing tests at application boundaries. "
            "Identifies boundaries by structural inference, confirms with user, "
            "and generates immutable tests that act as refactoring guard rails. "
            "Usable across all session types."
        ),
        sop_summary=[
            "Identify boundaries: examine structure for public APIs, module boundaries, entry points",
            "Present boundaries to user for confirmation and correction",
            "Generate behaviour-capturing tests at each confirmed boundary",
            "Mark tests IMMUTABLE — they capture current behaviour, not desired",
            "Register boundary test metadata in .harness/boundaries.yaml",
        ],
        tags=["testing", "boundaries", "refactoring", "safety"],
        tool_permissions=ToolPermissions.restricted_write(
            ['.harness/boundaries.yaml', 'tests/boundary/', '.harness/engagements/<slug>/']
        ),
    ),
    AgentSpec(
        role="refactor-orchestrator",
        name="Refactor Orchestrator",
        description=(
            "Top-level orchestrator for refactoring sessions. Manages the "
            "refactoring-specific workflow loop: intent-discovery \u2192 "
            "architecture-proposal \u2192 migration-assessment \u2192 "
            "boundary-test-generation \u2192 wave-execution \u2192 verification "
            "\u2192 summary. Delegates to refactoring-agent, boundary-test-agent, "
            "and existing coding/testing agents."
        ),
        sop_summary=[
            "Run intent-discovery: deploy refactoring-agent to understand project",
            "Run architecture-proposal: deploy architect + critic loop for target architecture",
            "Run migration-assessment: deploy refactoring-agent to estimate effort",
            "Run boundary-test-generation: deploy boundary-test-agent for guard-rail tests",
            "Execute waves: per-wave refactoring via WaveCycleRunner",
            "Run verification: full suite + boundary test integrity check",
            "Produce summary: architecture debt delta + remaining debt",
        ],
        tags=["orchestration", "refactoring", "session"],
        tool_permissions=ToolPermissions.read_only(),  # Orchestrator delegates, doesn't write directly
    ),
    # ── Wave 19 Phase 2: Review Agents ──────────────────────────────────
    AgentSpec(
        role="dead-code-analyser",
        name="Dead Code Analyser",
        description=(
            "Two-pronged analysis: (1) static analysis finds dead code, "
            "unused exports, unreachable branches, commented-out code, "
            "orphaned functions, and duplicate logic. (2) Coverage-based "
            "analysis identifies code exercised only by unit tests but "
            "never by integration/business tests — code that exists "
            "\"because the tests say so.\" Especially effective in "
            "DDD/clean-architecture projects where strict layer boundaries "
            "make business-layer code clearly separable from infrastructure."
        ),
        sop_summary=[
            "Scan project for potential dead code indicators",
            "Check each candidate: is it exported/referenced anywhere?",
            "Check for duplicate logic blocks",
            "Flag commented-out code blocks (size-based threshold, >5 lines)",
            "Check for unreachable branches (constant-condition guards)",
            "Identify business-layer tests (domain/application/integration/feature)",
            "Run coverage twice: all tests vs business-layer tests only",
            "Find delta: code covered by unit tests but NOT by business tests",
            "Categorise uncovered code: business-logic gap vs expected infrastructure",
            "Produce structured report with static + coverage findings",
        ],
        tags=["review", "quality", "analysis", "dead-code"],
        tool_permissions=ToolPermissions.with_web_search(),
    ),
    AgentSpec(
        role="component-analyser",
        name="Component Analyser",
        description=(
            "Evaluates whether interfaces and components are right-sized — "
            "cohesive, decoupled, and at appropriate granularity. Identifies "
            "god objects, shotgun surgery, mixed concerns, anemic models, "
            "and missing abstractions."
        ),
        sop_summary=[
            "Identify all public interfaces, classes, modules, and entry points",
            "Measure method count, parameter count, dependency count per component",
            "Check cohesion: do methods operate on shared state?",
            "Check coupling: how many external modules does each reference?",
            "Flag god objects, shotgun surgery, mixed concerns",
            "Flag anemic models and missing abstractions",
            "Compare against language-specific norms for right-sizing",
            "Produce coupling metrics, cohesion scores, and recommendations",
            "Zero magic: flag EVERY inline literal (string, number, value) that should "
            "be a named constant, enum, or resolver function. No exceptions.",
        ],
        tags=["review", "quality", "architecture", "design"],
        tool_permissions=ToolPermissions.read_only(),
    ),
    # ── Wave 19 Phase 3: Domain Interface Tester ────────────────────────
    AgentSpec(
        role="domain-interface-tester",
        name="Domain Interface Tester",
        description=(
            "Black-box testing against domain object interfaces. Discovers "
            "ABCs, Protocols, and abstract classes, then generates probe "
            "tests that probe each method with valid, invalid, and boundary "
            "inputs to verify interface conformance. Finds methods that "
            "accept parameters they don't use, return types that never "
            "return certain values, documented exceptions never thrown, "
            "and behaviour implied by the interface that doesn't "
            "materialise in implementations."
        ),
        sop_summary=[
            "Discover domain interfaces (ABCs, Protocols, abstract classes)",
            "Parse method signatures: parameters, types, return types",
            "Generate probe tests with valid, invalid, and boundary inputs",
            "Check: does the method handle all branches implied by its signature?",
            "Check: documented exceptions that never get thrown",
            "Check: states the method can enter that the interface doesn't document",
            "Check return type shape matches expectations",
            "Write probes to tests/domain-interface/ (auto-generated, not assertions)",
            "Produce conformance report with score, mismatches, recommendations",
        ],
        tags=["testing", "quality", "domain", "interfaces"],
        tool_permissions=ToolPermissions.restricted_write(
            ['tests/domain-interface/']
        ),
    ),
    # ── Wave 19 Phase 3b: Requirements Conformance Reviewer ────────────
    AgentSpec(
        role="requirements-conformance-reviewer",
        name="Requirements Conformance Reviewer",
        description=(
            "Verifies that tests cover every acceptance criterion defined "
            "in the requirements document. Builds a traceability matrix "
            "mapping each AC to the tests that verify it, flags untested "
            "ACs (requirements drift), flags tests with no AC trace "
            "(implementation drift), and checks test-level fit. Helps "
            "prevent drift from requirements by ensuring tests are "
            "verifying the specification, not just the code."
        ),
        sop_summary=[
            "Parse requirements document to extract structured acceptance criteria",
            "Scan all test files for references to requirements and ACs",
            "Build AC-to-test traceability matrix",
            "Flag acceptance criteria with no test coverage (requirements drift)",
            "Flag tests with no traceable AC (implementation drift)",
            "Check test-level appropriateness (unit vs integration vs acceptance)",
            "Report conformance score and recommendations",
        ],
        tags=["validation", "quality", "requirements", "testing"],
        tool_permissions=ToolPermissions.read_only(),
    ),
    # ── Short-form agent role aliases (used by fleet/phase configs) ────
    AgentSpec(
        role="researcher",
        name="Researcher",
        description="Researches and gathers information for the current task.",
        sop_summary=[
            "Research the task using available tools and context",
            "Gather information needed for subsequent phases",
            "Document findings with sources",
        ],
        tags=["research", "analysis"],
        tool_permissions=ToolPermissions.unrestricted(),
    ),
    AgentSpec(
        role="planner",
        name="Planner",
        description="Plans implementation steps based on architecture and requirements.",
        sop_summary=[
            "Break design into sequenced implementation tasks",
            "Identify dependencies between tasks",
            "Estimate effort per task",
        ],
        tags=["planning", "design"],
        tool_permissions=ToolPermissions.unrestricted(),
    ),
    AgentSpec(
        role="coder",
        name="Coder",
        description=(
            "Implements code per spec and architecture. Follows SOLID, "
            "writes clean, testable code."
        ),
        sop_summary=[
            "Implement code per task description and architecture",
            "Write clean, maintainable code",
            "Ensure all existing tests still pass",
        ],
        tags=["implementation", "core"],
        tool_permissions=ToolPermissions.unrestricted(),
    ),
    AgentSpec(
        role="tester",
        name="Tester",
        description=(
            "Tests code with a behaviour-first philosophy. Tests "
            "interfaces, not implementations."
        ),
        sop_summary=[
            "Write tests against interfaces (not implementations)",
            "Test expected behaviour from specifications",
            "Cover edge cases, boundary conditions, failure modes",
        ],
        tags=["testing", "core"],
        tool_permissions=ToolPermissions.unrestricted(),
    ),
    AgentSpec(
        role="reviewer",
        name="Reviewer",
        description="Reviews code, design, and documentation for quality and correctness.",
        sop_summary=[
            "Review implementation for correctness and style",
            "Verify tests cover the acceptance criteria",
            "Check for regressions and edge cases",
        ],
        tags=["review", "quality"],
        tool_permissions=ToolPermissions.unrestricted(),
    ),
]


# ---------------------------------------------------------------------------
# Registry functions
# ---------------------------------------------------------------------------


def get_agent(role: str) -> AgentSpec | None:
    """Look up an agent specification by role."""
    try:
        role = role
    except ValueError:
        return None
    for agent in AGENTS:
        if agent.role == role:
            return agent
    return None


def get_agents_by_tag(tag: str) -> list[AgentSpec]:
    """Get all agents that have the given tag."""
    return [a for a in AGENTS if tag in a.tags]


def list_agent_names() -> list[str]:
    """Get the canonical names of all registered agents."""
    return [a.role for a in AGENTS]


def list_agent_roles() -> list[str]:
    """Get all registered agent roles."""
    return [a.role for a in AGENTS]


def has_awareness_role(role: str) -> bool:
    """Check if an agent role is one of the brownfield/refactoring-aware roles."""
    return role in (
        "architect",
        "coding-agent",
        "testing-agent",
        "architecture-analyser",
        "refactoring-agent",
        "boundary-test-agent",
        "refactor-orchestrator",
    )


def get_session_aware_agents() -> list[AgentSpec]:
    """Get agents that have session-type-aware SOPs.

    These are agents whose behaviour changes depending on whether the
    session is greenfield, brownfield, or refactoring.
    """
    return [a for a in AGENTS if has_awareness_role(a.role)]


def registry_summary() -> dict[str, Any]:
    """Produce a summary dict of the full agent registry."""
    return {
        "total_agents": len(AGENTS),
        "agents": [
            {
                "role": a.role,
                "name": a.name,
                "tags": a.tags,
            }
            for a in AGENTS
        ],
    }


def get_default_critic_loop_config() -> ConvergenceConfig:
    """Return the default convergence configuration for critic loops.

    Uses ConvergenceConfig (unified config replacing old CriticLoopConfig).
    Default delegates to architect (writer) and critical-analyser (reviewer)
    with 5 max iterations.
    """
    return ConvergenceConfig(
        strategy="gate_judgment",
        max_iterations=5,
        convergence_keywords=[
            "no issues found",
            "no new issues",
            "design approved",
            "converged",
            "convergence",
        ],
        architect_role="architect",
        critic_role="critical-analyser",
        architect_output_subdir="design/",
        critic_output_subdir="reviews/",
    )
