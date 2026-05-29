"""Fleet data model — domain fleets, fleet guidelines, inclusion rules.

DEPRECATED (Wave 1.5): Fleet, FleetGuidelines, and the fleet abstraction
are superseded by AgentTeam, TeamRegistry, and string-keyed agent
catalogue in ``harness.team``. This module is retained for backward
compatibility only and will be removed in a future cleanup wave.

Use ``harness.team.model.AgentTeam`` and ``harness.team.registry.TeamRegistry``
instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from harness.agents.agent_registry import AgentRole


class GovernanceLevel(str, Enum):
    """Three-tier governance for agent activity depth.

    Controls which agents are active and at what depth. Configurable at the
    project level in ``.harness/config.yaml``, overridable at the engagement
    level in ``.harness/engagements/<slug>/engagement.yaml``.

    * ``exploration`` — POC / example / learning. Lead agent only. Sub-agents
      inactive. Minimal guidelines.
    * ``standard`` — Normal production work. Lead + relevant sub-agents
      (matched by project type). Full fleet guidelines.
    * ``strict`` — High governance (regulated, critical). Full fleet + all
      applicable sub-agents + extra reviewers. Maximum guideline depth.
    """

    EXPLORATION = "exploration"
    STANDARD = "standard"
    STRICT = "strict"


# ---------------------------------------------------------------------------
# Consultation Capability
# ---------------------------------------------------------------------------


@dataclass
class ConsultationCapability:
    """A cross-fleet consultation that this fleet can answer.

    Fleets declare their consultation capabilities so the
    :class:`ConsultationOrchestrator` can route questions to the
    right fleet without hard-coding dispatch logic.

    Matching uses **structured phrase matching** (deterministic,
    testable, no NLP infra). A question matches if any
    ``match_phrases`` string appears as a substring of the
    question text (case-insensitive).

    If no phrase matches among all registered capabilities, the
    orchestrator returns the full list for user selection.

    Attributes:
        name: Unique capability identifier (e.g.
            ``"architecture-review"``).
        description: Human-readable description.
        match_phrases: List of exact phrases that trigger this
            consultation. Match is case-insensitive substring.
        scope: When this consultation can fire.
            ``"cross-phase"`` — any phase, any time.
            ``"wave-build"`` — during wave implementation.
            ``"phase:<name>"`` — only during a specific phase.
            ``"trigger:<phase>"`` — auto-fire when entering a phase.
            ``"cycle:<runner-name>"`` — only during a named cycle.
        question: The default question template that this
            capability answers (may be overridden by the caller).
            Example: "Is this implementation still architecturally
            sound?"
    """
    name: str
    match_phrases: list[str]
    description: str = ""
    mode: Literal["advisory", "blocking"] = "advisory"
    scope: str = "cross-phase"
    question: str = ""

    def matches(self, question: str) -> bool:
        """Return True if this capability can answer the question.

        Performs case-insensitive substring matching against all
        ``match_phrases``.
        """
        q_lower = question.lower()
        return any(phrase.lower() in q_lower for phrase in self.match_phrases)


# ---------------------------------------------------------------------------
# Fleet Guidelines
# ---------------------------------------------------------------------------


@dataclass
class FleetGuidelines:
    """Protocols and rules shared by ALL agents in a fleet.

    Guidelines are injected into every agent's context, including custom
    user-defined agents added to the fleet. They ensure consistent
    cooperation, input/output formatting, and phase participation.

    Attributes:
        input_protocol: Specification for how the fleet receives input.
        output_protocol: Specification for what the fleet produces.
        cooperation: List of cooperation rules as natural-language strings.
        phases: List of phase names this fleet participates in.
    """

    input_protocol: dict = field(default_factory=lambda: {
        "format": "markdown",
        "required_sections": ["context", "scope", "constraints"],
    })
    output_protocol: dict = field(default_factory=lambda: {
        "format": "markdown",
        "required_sections": ["proposal", "rationale", "tradeoffs"],
    })
    cooperation: list[str] = field(default_factory=list)
    """Cooperation rules. Example: "Receive intent from discovery phase"."""

    phases: list[str] = field(default_factory=list)
    """Phases this fleet participates in. Example: ["design", "review"]."""


# ---------------------------------------------------------------------------
# Inclusion Rules
# ---------------------------------------------------------------------------


@dataclass
class InclusionRules:
    """Which sub-agents are active for a given project type and governance level.

    Attributes:
        project_type: Mapping of project type → list of sub-agent roles
            (e.g. ``{"ddd-backend": ["domain-model", "event-driven"]}``).
        governance_minimum: Mapping of sub-agent role → minimum governance
            level required for that agent to be active.
    """

    project_type: dict[str, list[str]] = field(default_factory=dict)
    governance_minimum: dict[str, GovernanceLevel] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Fleet Definition
# ---------------------------------------------------------------------------


@dataclass
class Fleet:
    """A domain fleet grouping related harness agents.

    Attributes:
        name: Unique fleet identifier (e.g. ``"architecture"``).
        lead_role: Agent role of the fleet's lead coordinator. Must exist
            in the agent registry.
        description: Human-readable description of the fleet's purpose.
        guidelines: Fleet-level guidelines inherited by all agents.
        sub_agents: List of sub-agent roles (strings referencing roles from
            the agent registry or custom roles).
        inclusion_rules: Rules controlling sub-agent activation.
        builtin: Whether this fleet is built into the harness (``True``) or
            user-defined (``False``).
        consultations: List of :class:`ConsultationCapability` that this
            fleet can answer. Used by the ConsultationOrchestrator for
            cross-fleet routing.
        agent_names: Alternative agent role names that map to this fleet.
            Used for name normalization so fleet injection works for
            all phases without explicit ``fleets`` key.
            Example: ``["coder", "coding-agent"]``.
        created: Timestamp of fleet creation.
        updated: Timestamp of last update.
    """

    name: str
    lead_role: str
    description: str = ""
    guidelines: FleetGuidelines = field(default_factory=FleetGuidelines)
    sub_agents: list[str] = field(default_factory=list)
    inclusion_rules: InclusionRules = field(default_factory=InclusionRules)
    builtin: bool = True
    consultations: list[ConsultationCapability] = field(default_factory=list)
    agent_names: list[str] = field(default_factory=list)
    created: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def matches_agent(self, role: str) -> bool:
        """Return True if the given role name belongs to this fleet.

        Checks lead_role, sub_agents, and agent_names.
        """
        return (
            role == self.lead_role
            or role in self.sub_agents
            or role in self.agent_names
        )

    def has_consultation_for(self, question: str) -> bool:
        """Return True if any consultation capability matches the question."""
        return any(c.matches(question) for c in self.consultations)

    def get_active_agents(
        self,
        governance: GovernanceLevel = GovernanceLevel.STANDARD,
        project_type: str | None = None,
    ) -> list[str]:
        """Return the list of active agent roles for this fleet.

        At ``exploration`` level, only the lead agent is active.
        At ``standard`` level, the lead + sub-agents matching the project type.
        At ``strict`` level, all sub-agents are active.
        """
        active = [self.lead_role]

        if governance == GovernanceLevel.EXPLORATION:
            return active

        # Determine the base set of sub-agents to consider
        if governance == GovernanceLevel.STRICT:
            candidates = list(self.sub_agents)
        else:
            # standard: filter by project type
            if project_type and project_type in self.inclusion_rules.project_type:
                allowed = set(self.inclusion_rules.project_type[project_type])
                candidates = [r for r in self.sub_agents if r in allowed]
            else:
                candidates = list(self.sub_agents)

        # Filter by governance minimum
        for role in candidates:
            min_level = self.inclusion_rules.governance_minimum.get(role)
            if min_level is not None:
                # Check if governance meets minimum
                level_rank = {
                    GovernanceLevel.EXPLORATION: 0,
                    GovernanceLevel.STANDARD: 1,
                    GovernanceLevel.STRICT: 2,
                }
                min_rank = level_rank.get(min_level, 0)
                current_rank = level_rank.get(governance, 1)
                if current_rank < min_rank:
                    continue
            active.append(role)

        return active


# ---------------------------------------------------------------------------
# Built-in Fleet Definitions
# ---------------------------------------------------------------------------

_BUILTIN_ARCHITECTURE_SUB_AGENTS = [
    "domain-model",
    "event-driven",
    "persistence",
    "api-surface",
    "cli-command",
    "component-tree",
    "state-mgmt",
    "flow-orch",
]

_BUILTIN_CODING_SUB_AGENTS = [
    "python-coder",
    "go-coder",
    "ts-coder",
    "java-coder",
    "rust-coder",
    "refinement-coder",
    "refactoring-agent",
    "refactor-orchestrator",
]

_BUILTIN_REVIEW_SUB_AGENTS = [
    "security-review",
    "performance-review",
    "style-review",
    "spec-alignment",
    "dead-code-analyser",
    "component-analyser",
    "critical-analyser",
    "documentation-agent",
]

_BUILTIN_TESTING_SUB_AGENTS = [
    "unit-test-gen",
    "domain-interface-test",
    "feature-test-gen",
    "integration-test",
    "domain-interface-tester",
    "boundary-test-agent",
    "testing-agent",
]


_BUILTIN_DISCOVERY_SUB_AGENTS: list[str] = [
    "requirements-analyser",
    "stakeholder-interface",
    "discovery-agent",
    "example-scenarios-agent",
]

_BUILTIN_PLANNING_SUB_AGENTS: list[str] = [
    "task-decomposer",
    "dependency-analyser",
    "effort-estimator",
    "coordinator",
    "sync",
]

_BUILTIN_VALIDATION_SUB_AGENTS: list[str] = [
    "acceptance-verifier",
    "scenario-tester",
    "quality-gate",
]


def builtin_fleets() -> list[Fleet]:
    """Return the 7 built-in fleets with their default configuration.

    Four original fleets (architecture, coding, review, testing) plus
    three new fleets (discovery, planning, validation). All fleets now
    include ``agent_names`` for name normalization and
    ``consultations`` for cross-fleet routing (Wave 18, Phase 1).
    """
    now = datetime.now(timezone.utc).isoformat()

    return [
        # ── Discovery Fleet ───────────────────────────────────────────────
        Fleet(
            name="discovery",
            lead_role="requirements-builder",
            description=(
                "Analyses requirements, researches context, and produces "
                "structured requirements and research notes. First phase "
                "of the engagement lifecycle."
            ),
            guidelines=FleetGuidelines(
                input_protocol={
                    "format": "markdown",
                    "required_sections": ["intent", "context"],
                },
                output_protocol={
                    "format": "markdown",
                    "required_sections": ["requirements", "research", "constraints"],
                },
                cooperation=[
                    "Receive project intent from user prompt",
                    "Produce structured requirements for architecture fleet",
                    "Research technical context and dependencies",
                    "Flag ambiguous requirements before design",
                ],
                phases=["requirements", "research"],
            ),
            sub_agents=list(_BUILTIN_DISCOVERY_SUB_AGENTS),
            inclusion_rules=InclusionRules(
                project_type={},
                governance_minimum={
                    "requirements-analyser": GovernanceLevel.STANDARD,
                    "stakeholder-interface": GovernanceLevel.STRICT,
                },
            ),
            consultations=[
                ConsultationCapability(
                    name="requirements-clarification",
                    match_phrases=[
                        "requirements clarification",
                        "what are the requirements",
                        "requirement definition",
                    ],
                    description="Clarify or expand on engagement requirements",
                    scope="cross-phase",
                    question="What are the current requirements for this engagement?",
                ),
            ],
            agent_names=["researcher"],
            builtin=True,
            created=now,
            updated=now,
        ),
        # ── Planning Fleet ────────────────────────────────────────────────
        Fleet(
            name="planning",
            lead_role="planning-agent",
            description=(
                "Decomposes work into tasks, estimates effort, identifies "
                "dependencies, and produces the wave plan for an engagement."
            ),
            guidelines=FleetGuidelines(
                input_protocol={
                    "format": "markdown",
                    "required_sections": ["requirements", "architecture"],
                },
                output_protocol={
                    "format": "markdown",
                    "required_sections": ["waves", "tasks", "dependencies", "estimation"],
                },
                cooperation=[
                    "Receive requirements from discovery fleet",
                    "Receive architecture constraints from architecture fleet",
                    "Produce wave plan for coding fleet",
                    "Coordinate task dependencies across fleets",
                ],
                phases=["planning"],
            ),
            sub_agents=list(_BUILTIN_PLANNING_SUB_AGENTS),
            inclusion_rules=InclusionRules(
                project_type={
                    "ddd-backend": ["dependency-analyser"],
                    "cli-tool": ["task-decomposer"],
                    "web-frontend": ["task-decomposer", "effort-estimator"],
                    "data-pipeline": ["dependency-analyser", "effort-estimator"],
                },
                governance_minimum={
                    "task-decomposer": GovernanceLevel.STANDARD,
                    "dependency-analyser": GovernanceLevel.STANDARD,
                    "effort-estimator": GovernanceLevel.STANDARD,
                },
            ),
            consultations=[
                ConsultationCapability(
                    name="effort-estimation",
                    match_phrases=[
                        "effort estimate",
                        "how long will this take",
                        "task estimation",
                        "scope estimation",
                    ],
                    description="Estimate effort and complexity for proposed work",
                    scope="cross-phase",
                    question="How much effort is required for this task?",
                ),
                ConsultationCapability(
                    name="dependency-analysis",
                    match_phrases=[
                        "dependency analysis",
                        "what dependencies exist",
                        "task dependencies",
                    ],
                    description="Analyse dependencies between tasks or components",
                    scope="cross-phase",
                    question="What are the dependencies for this work?",
                ),
            ],
            agent_names=["planner"],
            builtin=True,
            created=now,
            updated=now,
        ),
        # ── Architecture Fleet ─────────────────────────────────────────────
        Fleet(
            name="architecture",
            lead_role=AgentRole.ARCHITECT,
            description=(
                "Designs system architecture, domain models, and "
                "boundaries. Produces architecture documents, ADRs, "
                "and interface contracts."
            ),
            guidelines=FleetGuidelines(
                input_protocol={
                    "format": "markdown",
                    "required_sections": ["intent", "scope", "constraints"],
                },
                output_protocol={
                    "format": "markdown",
                    "required_sections": ["proposal", "rationale", "tradeoffs"],
                },
                cooperation=[
                    "Receive intent from discovery/prompt phase",
                    "Produce architecture proposal for coding fleet",
                    "Flag unresolvable constraints to orchestrator",
                    "Incorporate critic feedback from architecture analyser",
                ],
                phases=["design", "architecture-proposal"],
            ),
            sub_agents=list(_BUILTIN_ARCHITECTURE_SUB_AGENTS),
            inclusion_rules=InclusionRules(
                project_type={
                    "ddd-backend": ["domain-model", "event-driven", "persistence", "api-surface"],
                    "cli-tool": ["cli-command"],
                    "web-frontend": ["component-tree", "state-mgmt", "api-surface"],
                    "data-pipeline": ["flow-orch"],
                },
                governance_minimum={
                    "domain-model": GovernanceLevel.STANDARD,
                    "event-driven": GovernanceLevel.STANDARD,
                    "persistence": GovernanceLevel.STANDARD,
                    "api-surface": GovernanceLevel.STANDARD,
                    "cli-command": GovernanceLevel.STANDARD,
                    "component-tree": GovernanceLevel.STANDARD,
                    "state-mgmt": GovernanceLevel.STANDARD,
                    "flow-orch": GovernanceLevel.STANDARD,
                },
            ),
            consultations=[
                ConsultationCapability(
                    name="architecture-review",
                    match_phrases=[
                        "architecturally sound",
                        "architecture review",
                        "arch review",
                        "architecture question",
                    ],
                    description="Review architecture decisions and proposals",
                    scope="cross-phase",
                    question="Is this implementation still architecturally sound?",
                ),
            ],
            agent_names=[],
            builtin=True,
            created=now,
            updated=now,
        ),
        # ── Coding Fleet ──────────────────────────────────────────────────
        Fleet(
            name="coding",
            lead_role=AgentRole.CODING_AGENT,
            description=(
                "Implements code following architecture decisions. "
                "Consumes architecture specs, produces implementation "
                "code and test stubs."
            ),
            guidelines=FleetGuidelines(
                input_protocol={
                    "format": "markdown",
                    "required_sections": ["architecture", "specification"],
                },
                output_protocol={
                    "format": "code",
                    "required_sections": ["implementation", "tests"],
                },
                cooperation=[
                    "Receive architecture spec from architecture fleet",
                    "Produce implementation for testing fleet",
                    "Write to adapter and anti-corruption layer interfaces",
                    "Preserve existing behaviour via boundary tests in refactoring mode",
                ],
                phases=["implementation"],
            ),
            sub_agents=list(_BUILTIN_CODING_SUB_AGENTS),
            inclusion_rules=InclusionRules(
                project_type={
                    "ddd-backend": ["refinement-coder"],
                    "cli-tool": ["refinement-coder"],
                    "web-frontend": ["ts-coder", "refinement-coder"],
                },
                governance_minimum={
                    "python-coder": GovernanceLevel.STANDARD,
                    "go-coder": GovernanceLevel.STANDARD,
                    "ts-coder": GovernanceLevel.STANDARD,
                    "java-coder": GovernanceLevel.STANDARD,
                    "rust-coder": GovernanceLevel.STANDARD,
                    "refinement-coder": GovernanceLevel.STANDARD,
                },
            ),
            consultations=[
                ConsultationCapability(
                    name="code-review-request",
                    match_phrases=[
                        "code review",
                        "implementation review",
                        "review this code",
                        "check implementation",
                    ],
                    description="Request review of implementation code before completion",
                    scope="wave-build",
                    question="Review the latest implementation for correctness and style.",
                ),
            ],
            agent_names=["coder"],
            builtin=True,
            created=now,
            updated=now,
        ),
        # ── Testing Fleet ─────────────────────────────────────────────────
        Fleet(
            name="testing",
            lead_role=AgentRole.TESTING_AGENT,
            description=(
                "Defines test strategies, generates test code, and "
                "validates implementations against specifications. "
                "Supports boundary test generation for refactoring safety."
            ),
            guidelines=FleetGuidelines(
                input_protocol={
                    "format": "markdown",
                    "required_sections": ["specifications", "implementation"],
                },
                output_protocol={
                    "format": "code",
                    "required_sections": ["tests", "coverage"],
                },
                cooperation=[
                    "Receive specifications from architecture fleet",
                    "Receive implementation from coding fleet",
                    "Produce test code and coverage reports for review fleet",
                    "Mark boundary tests as IMMUTABLE during refactoring sessions",
                ],
                phases=["testing"],
            ),
            sub_agents=list(_BUILTIN_TESTING_SUB_AGENTS),
            inclusion_rules=InclusionRules(
                project_type={},
                governance_minimum={
                    "unit-test-gen": GovernanceLevel.STANDARD,
                    "domain-interface-test": GovernanceLevel.STANDARD,
                    "feature-test-gen": GovernanceLevel.STANDARD,
                    "integration-test": GovernanceLevel.STRICT,
                },
            ),
            consultations=[
                ConsultationCapability(
                    name="test-strategy-review",
                    match_phrases=[
                        "test strategy",
                        "testing approach",
                        "coverage question",
                        "what tests are needed",
                    ],
                    description="Advise on test strategy and coverage",
                    scope="wave-build",
                    question="What test strategy should be used for this implementation?",
                ),
            ],
            agent_names=["tester"],
            builtin=True,
            created=now,
            updated=now,
        ),
        # ── Review Fleet ──────────────────────────────────────────────────
        Fleet(
            name="review",
            lead_role=AgentRole.CRITICAL_ANALYSER,
            description=(
                "Reviews architecture, code, and test output for "
                "correctness, security, performance, and alignment "
                "with specifications."
            ),
            guidelines=FleetGuidelines(
                input_protocol={
                    "format": "markdown",
                    "required_sections": ["artifacts", "criteria"],
                },
                output_protocol={
                    "format": "markdown",
                    "required_sections": ["findings", "severity", "recommendations"],
                },
                cooperation=[
                    "Receive architecture artifacts from architecture fleet",
                    "Receive code artifacts from coding fleet",
                    "Produce structured review reports for orchestrator",
                    "Flag blockers and critical issues immediately",
                ],
                phases=["design-review", "code-review"],
            ),
            sub_agents=list(_BUILTIN_REVIEW_SUB_AGENTS),
            inclusion_rules=InclusionRules(
                project_type={},
                governance_minimum={
                    "security-review": GovernanceLevel.STRICT,
                    "performance-review": GovernanceLevel.STRICT,
                    "style-review": GovernanceLevel.STANDARD,
                    "spec-alignment": GovernanceLevel.STANDARD,
                },
            ),
            consultations=[
                ConsultationCapability(
                    name="quality-assessment",
                    match_phrases=[
                        "quality assessment",
                        "is this good enough",
                        "quality gate",
                        "review findings",
                    ],
                    description="Assess quality of deliverables against standards",
                    scope="cross-phase",
                    question="Is the current deliverable quality acceptable?",
                ),
            ],
            agent_names=["reviewer"],
            builtin=True,
            created=now,
            updated=now,
        ),
        # ── Validation Fleet ──────────────────────────────────────────────
        Fleet(
            name="validation",
            lead_role="validation-agent",
            description=(
                "Validates outputs against acceptance criteria. Checks "
                "scenario completeness, quality gate compliance, and "
                "overall deliverable integrity."
            ),
            guidelines=FleetGuidelines(
                input_protocol={
                    "format": "markdown",
                    "required_sections": ["artifacts", "acceptance-criteria"],
                },
                output_protocol={
                    "format": "markdown",
                    "required_sections": ["validation-status", "issues", "recommendations"],
                },
                cooperation=[
                    "Receive artifacts from all prior phases",
                    "Validate against acceptance criteria",
                    "Produce validation report with pass/fail per criterion",
                    "Escalate critical validation failures to orchestrator",
                ],
                phases=["testing", "review"],
            ),
            sub_agents=list(_BUILTIN_VALIDATION_SUB_AGENTS),
            inclusion_rules=InclusionRules(
                project_type={},
                governance_minimum={
                    "acceptance-verifier": GovernanceLevel.STANDARD,
                    "scenario-tester": GovernanceLevel.STANDARD,
                    "quality-gate": GovernanceLevel.STRICT,
                },
            ),
            consultations=[
                ConsultationCapability(
                    name="validation-check",
                    match_phrases=[
                        "validation check",
                        "acceptance criteria",
                        "does this meet requirements",
                        "scenario validation",
                    ],
                    description="Validate deliverables against acceptance criteria",
                    scope="cross-phase",
                    question="Does this deliverable meet all acceptance criteria?",
                ),
                ConsultationCapability(
                    name="quality-gate-status",
                    match_phrases=[
                        "quality gate status",
                        "is this ready",
                        "release readiness",
                        "completeness check",
                    ],
                    description="Check whether the deliverable passes quality gates",
                    scope="cross-phase",
                    question="Is this deliverable ready for the next phase?",
                ),
            ],
            agent_names=[],
            builtin=True,
            created=now,
            updated=now,
        ),
    ]
