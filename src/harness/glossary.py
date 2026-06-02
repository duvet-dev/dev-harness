"""Domain glossary — ubiquitous language for the Dev Harness.

Every term used in the codebase is defined here. If a term doesn't have
a clear definition, it needs refinement.

This module is the authoritative reference for the Dev Harness domain
language. All team members and agents should refer to these definitions
when communicating about the system.
"""

from __future__ import annotations

from typing import ClassVar

GLOSSARY: ClassVar[dict[str, dict]] = {
    # ── Aggregate root ─────────────────────────────────────────────────
    "Engagement": {
        "definition": (
            "A development session with a specific goal and type. "
            "The top-level aggregate root that owns the entire development "
            "lifecycle — creation, phase transitions, and completion."
        ),
        "types": {
            "greenfield": "Build from scratch — no existing codebase to accommodate.",
            "brownfield": "Work within an existing codebase — add features without restructuring.",
            "refactoring": "Restructure existing code without changing external behaviour.",
            "get-well": "Remediation — diagnose and fix a broken or degraded state.",
            "quick-fix": "Targeted, small-scope fix with minimal process.",
            "inspect": "Read-only audit and reporting pass over the codebase.",
        },
        "lifecycle": "CREATED → ACTIVE → COMPLETED | ABORTED (PAUSED is an intermediate on ACTIVE)",
        "relationships": [
            "Session", "SessionType", "Workflow", "Phase", "Plan", "Wave",
        ],
        "used_in": [
            "src/harness/domain/engagement_aggregate.py",
            "src/harness/domain/engagement/model.py",
            "src/harness/domain/events/engagement_events.py",
            "src/harness/workflows/engagement.py",
        ],
        "key_fields": ["slug", "session_type", "workflow_name", "status", "current_phase"],
    },
    "Session": {
        "definition": (
            "An execution context for running an engagement's phase or for "
            "interactive chat with the user. Two kinds: phase session (runs "
            "an engagement's phase steps) and chat session (interactive user "
            "conversation within a phase)."
        ),
        "relationships": ["Engagement", "Phase", "Step"],
        "used_in": [
            "src/harness/session/helpers.py",
        ],
        "key_fields": ["engagement_slug", "phase_name", "agent", "status"],
    },
    "SessionType": {
        "definition": (
            "Classification of an engagement that determines which workflow "
            "and phase sequence is used. One of: greenfield, brownfield, "
            "refactoring, get-well. Maps directly to a Workflow."
        ),
        "values": ["greenfield", "brownfield", "refactoring", "get-well", "quick-fix"],
        "mapped_to": {
            "greenfield": "Workflow 'standard' → requirements, design, build, test, review",
            "brownfield": "Workflow 'brownfield' → analyse, design, build, test, review",
            "refactoring": "Workflow 'refactoring' → analyse, design, characterise, refactor, verify, review",
            "get-well": "Workflow 'get-well' → assessment-triage, remediation-requirements, architecture-design, planning, implementation, testing, review",
            "quick-fix": "Workflow 'quick-fix' → fix, test, validate, deliver",
            "audit/inspect": "Workflow 'inspect' → audit, report",
        },
        "relationships": ["Engagement", "Workflow", "Phase"],
        "used_in": [
            "src/harness/domain/enums.py",
            "src/harness/domain/engagement/model.py",
            "src/harness/session/helpers.py",
            "src/harness/workflow/orchestrator.py",
        ],
    },
    "Workflow": {
        "definition": (
            "A named, ordered collection of phases that defines the execution "
            "sequence for an engagement of a given session type. Each SessionType "
            "maps to a specific Workflow with a distinct phase sequence."
        ),
        "known_workflows": {
            "standard": "requirements → design → build → review → test → validate → deliver (existing orchestrator, used by greenfield)",
            "brownfield": "analyse → design → build → test → review (proposed)",
            "refactoring": "assess → refactor → test → validate (existing orchestrator)",
            "get-well": "assessment-triage → remediation-requirements → architecture-design → planning → implementation → testing → review (existing helpers)",
            "quick-fix": "fix → test → validate → deliver (existing orchestrator)",
            "inspect": "audit → report (existing orchestrator)",
        },
        "relationships": ["SessionType", "Phase", "WorkflowState", "Engagement"],
        "used_in": [
            "src/harness/workflow/model.py",
            "src/harness/workflows/engagement.py",
            "src/harness/cli/helpers.py",
        ],
        "key_fields": ["name", "phases"],
    },
    "Phase": {
        "definition": (
            "A named stage within a workflow that groups related steps. "
            "Each phase has a lead agent, a chat agent, and an ordered list "
            "of steps to execute. Phases may re-enter with 'restart' or 'resume' "
            "semantics."
        ),
        "known_phases": [
            # Canonical — in PhaseName.VALID
            "requirements", "design", "implementation", "testing",
            "review", "deployment", "assessment-triage",
            # Proposed — aspirational, not yet in PhaseName.VALID
            "analyse", "characterise", "refactor", "verify",
            "build", "plan", "execute", "test",
            # Existing in codebase — not yet in PhaseName.VALID
            "research", "planning",
            "remediation-requirements", "architecture-design",
            "understanding",
            # Workflow orchestrator phases — not in PhaseName.VALID
            "discover", "fix", "validate", "deliver", "triage",
            "assess", "audit", "report",
        ],
        "note": (
            "This list mixes validated (PhaseName.VALID), aspirational "
            "(proposed), and legacy (existing in code) phase names. "
            "The workflow architecture doc (workflow-architecture.md) "
            "reconciles these into 6 canonical workflow definitions. "
            "Entries marked 'Proposed' or 'Existing in codebase' are "
            "candidates for inclusion in PhaseName.VALID."
        ),
        "relationships": ["Workflow", "Step", "StepTemplate", "ConvergenceConfig"],
        "used_in": [
            "src/harness/phase/model.py",
            "src/harness/session/helpers.py",
            "src/harness/domain/enums.py",
        ],
        "key_fields": ["name", "lead_agent", "chat_agent", "steps", "reentry"],
    },
    "Step": {
        "definition": (
            "A single unit of work within a phase. Exactly one of five mutually "
            "exclusive types must be set: agents (dispatch named agents), team "
            "(expand a team template), loop (iterate with convergence), phase "
            "(jump to another phase as a sub-phase), or template (expand from "
            "template registry)."
        ),
        "types": ["agent", "team", "loop", "phase", "template"],
        "relationships": ["Phase", "StepTemplate", "ConvergenceConfig", "StepResult"],
        "used_in": [
            "src/harness/phase/model.py",
            "src/harness/phase/step_executor.py",
        ],
        "key_fields": [
            "agents|team|loop|phase|template (mutually exclusive)",
            "parallel", "lead", "input", "output", "role", "action",
        ],
    },
    "StepTemplate": {
        "definition": (
            "A reusable step definition registered in the template registry. "
            "Used by template-type steps to expand into one or more concrete "
            "steps at execution time. Not yet wired into the phase runner."
        ),
        "relationships": ["Step", "Phase", "TemplateRegistry"],
        "used_in": [
            "src/harness/constitution/templates/template_registry.py",
        ],
        "status": "defined but not wired to step execution",
    },
    "Wave": {
        "definition": (
            "A PR-sized batch of work within a development plan. The primary "
            "decomposition unit for implementation planning. A wave can span "
            "multiple phases (e.g. design + build + test for a small feature). "
            "Waves track origin (type), state (planned/in-progress/committed), "
            "and provenance for rework tracking."
        ),
        "types": {
            "STANDARD": "Normal feature or implementation wave.",
            "ADJUSTMENT": "Fixes or changes to an already-committed wave.",
            "REFACTOR": "Structural rework without functional change.",
        },
        "relationships": ["Plan", "WaveType", "WaveState", "WaveProvenance"],
        "used_in": [
            "src/harness/plan/wave_model.py",
            "src/harness/wave/",
        ],
        "key_fields": ["id", "title", "type", "state", "tasks", "provenance"],
    },
    "WaveType": {
        "definition": "The nature of a wave's work: STANDARD, ADJUSTMENT, or REFACTOR.",
        "relationships": ["Wave", "Plan"],
        "used_in": ["src/harness/plan/wave_model.py"],
    },
    "EngagementStatus": {
        "definition": (
            "Lifecycle status of an engagement. CREATED → ACTIVE → COMPLETED "
            "(or PAUSED → ACTIVE → COMPLETED, or → ABORTED at any point)."
        ),
        "values": ["created", "active", "paused", "aborted", "completed"],
        "relationships": ["Engagement"],
        "used_in": [
            "src/harness/domain/enums.py",
            "src/harness/domain/engagement/model.py",
            "src/harness/domain/engagement_aggregate.py",
        ],
    },
    "Plan": {
        "definition": (
            "A development plan containing an ordered sequence of waves. "
            "Created during the planning phase, consumed by the session loop "
            "for per-wave implementation, and updated as adjustment/refactor "
            "waves are added. Provides input to the self-improvement loop."
        ),
        "relationships": ["Wave", "WaveType", "Engagement", "Phase"],
        "used_in": ["src/harness/plan/wave_model.py"],
        "key_fields": ["waves", "priorities", "constraints"],
    },
    "WorkflowState": {
        "definition": (
            "Runtime state for an active workflow execution. Tracks the current "
            "position within a workflow's phase sequence, which phases are pending, "
            "completed, or failed, and the overall workflow lifecycle status "
            "(PENDING → ACTIVE → COMPLETED | FAILED)."
        ),
        "relationships": ["Workflow", "Phase", "Engagement"],
        "used_in": ["src/harness/workflow/model.py"],
        "key_fields": [
            "workflow_name", "slug", "current_phase",
            "pending_phases", "completed_phases", "failed_phases", "status",
        ],
    },
    "DomainEvent": {
        "definition": (
            "A significant state change within the domain that other parts of "
            "the system need to know about. Published by the Engagement aggregate "
            "when lifecycle transitions occur (created, started, completed, aborted, "
            "phase transitioned, wave committed)."
        ),
        "event_types": [
            "EngagementCreated", "EngagementStarted", "EngagementStatusChanged",
            "EngagementCompleted", "EngagementAborted", "PhaseTransitioned",
            "WaveCommitted",
        ],
        "relationships": ["Engagement", "EventBus"],
        "used_in": [
            "src/harness/domain/events/engagement_events.py",
            "src/harness/domain/events/event_bus.py",
        ],
    },
    "EventBus": {
        "definition": (
            "In-process publish/subscribe channel for domain events. The "
            "Engagement aggregate publishes events through the bus; handlers "
            "can react for side effects (logging, snapshots, notifications). "
            "Currently in-process only — not connected to a distributed event bus."
        ),
        "relationships": ["DomainEvent", "Engagement"],
        "used_in": [
            "src/harness/domain/events/event_bus.py",
            "src/harness/domain/engagement_aggregate.py",
        ],
    },
    "AgentService": {
        "definition": (
            "Application service that orchestrates agent execution. Takes a "
            "ContextPacket and a backend name, resolves the backend from the "
            "PluginRegistry, dispatches the agent, and returns the result "
            "with artifacts and metrics. Used by Temporal activities to run "
            "single-agents."
        ),
        "relationships": ["PluginRegistry", "Agent", "ContextPacket", "Backend"],
        "used_in": [
            "src/harness/application/services/agent_service.py",
            "src/harness/workflows/activities.py",
        ],
    },
    "PluginRegistry": {
        "definition": (
            "Registry of agent backends and plugins. Initialized at startup, "
            "provides backend resolution for AgentService. Holds the map from "
            "backend names (e.g. 'api', 'cli', 'editor') to their implementations."
        ),
        "relationships": ["AgentService", "Backend"],
        "used_in": [
            "src/harness/infrastructure/plugins/registry.py",
        ],
    },
    "HealthCheck": {
        "definition": (
            "A check that assesses the health of an engagement or a project. "
            "Produces findings with severity levels (CRITICAL, BRANCH, WARN, INFO) "
            "that can trigger get-well engagements. Health checks are the diagnostic "
            "entry point for the get-well workflow."
        ),
        "relationships": ["HealthSeverity", "Engagement", "Assessment"],
        "used_in": [
            "src/harness/health.py",
            "src/harness/domain/health.py",
        ],
    },
    "HealthSeverity": {
        "definition": "Severity levels for health check findings: CRITICAL, BRANCH, WARN, INFO.",
        "relationships": ["HealthCheck", "Engagement"],
        "used_in": ["src/harness/domain/enums.py"],
    },
    "GitRepo": {
        "definition": (
            "Interface to the underlying git repository for SCM operations. "
            "Encapsulates commit, branch management, status checks, and "
            "diff operations. Used by engagements to track work against a "
            "target branch."
        ),
        "relationships": ["Engagement", "Plan"],
        "used_in": [
            "src/harness/scm/git.py",
        ],
    },
    "Axonitation": {
        "definition": (
            "An artificial constraint or limitation imposed on an agent to prevent "
            "it from taking actions it would normally be able to take (e.g., 'don't "
            "write tests', 'only write production code'). Axonitations narrow an "
            "agent's scope within a phase to enforce separation of concerns. Used "
            "in phase prompts as 'boundaries' sections. Named for 'axon' (nerve "
            "fiber) + 'prohibition' — a deliberate limitation on an agent's agency."
        ),
        "relationships": ["Phase", "Step", "Agent"],
        "used_in": [
            "src/harness/session/helpers.py",
        ],
        "example": (
            "A requirements-builder agent has an axonitation: 'Do NOT write any "
            "code, even if asked. Do NOT propose architectures, designs, or "
            "implementations.'"
        ),
    },
    "ConvergenceConfig": {
        "definition": (
            "Configuration for convergence-aware loop iteration. Determines how "
            "a loop step decides when to stop iterating. Strategies include: "
            "gate_judgment (a gate agent signals convergence), all_gates (all "
            "gate steps produce output), test_suite (external tests pass), stable "
            "(output unchanged between iterations), and external_approval (callback "
            "confirms convergence)."
        ),
        "strategies": [
            "gate_judgment", "all_gates", "test_suite", "stable", "external_approval",
        ],
        "relationships": ["Step", "LoopConfig", "StepResult"],
        "used_in": ["src/harness/phase/model.py"],
        "key_fields": ["strategy", "max_iterations", "on_timeout", "gate_agent"],
    },
    "StepResult": {
        "definition": (
            "Result of executing a single step within a loop iteration. "
            "Captures the step type, role, status, artifacts produced, any "
            "error, iteration number, and retry count."
        ),
        "relationships": ["Step", "StepStatus", "ConvergenceConfig"],
        "used_in": ["src/harness/phase/model.py"],
        "key_fields": [
            "step_type", "step_role", "status", "artifacts", "error",
            "iteration", "retries",
        ],
    },
    "Consultation": {
        "definition": (
            "A mechanism for routing ad-hoc questions to the matching agent "
            "fleet during an active phase. Used via /consult command. Can be "
            "advisory (informational) or blocking (must be resolved before "
            "advancing)."
        ),
        "relationships": ["Phase", "Agent", "TeamRegistry"],
        "used_in": [
            "src/harness/agents/consultation.py",
            "src/harness/session/helpers.py",
        ],
        "modes": ["advisory", "blocking"],
    },
    "TeamRegistry": {
        "definition": (
            "Registry of named teams (groups of agents). Teams are used by "
            "team-type steps for parallel dispatch. The registry resolves team "
            "names to their member agents. Built-in teams are seeded from "
            "default definitions."
        ),
        "relationships": ["Step", "Agent", "Consultation"],
        "used_in": [
            "src/harness/team/registry.py",
            "src/harness/team/defaults.py",
        ],
    },
    "TemplateRegistry": {
        "definition": (
            "Registry of reusable step templates. Template-type steps reference "
            "a template name that expands to one or more concrete steps. "
            "Currently holds agent profile templates and constitution templates."
        ),
        "relationships": ["Step", "StepTemplate", "Phase"],
        "used_in": [
            "src/harness/constitution/templates/template_registry.py",
        ],
        "status": "defined but not wired to step execution engine",
    },
    "Assessment": {
        "definition": (
            "A structured health assessment run against a project. Produces "
            "findings with severity, category, and location. Findings can be "
            "grouped into themes and used to drive a get-well engagement."
        ),
        "relationships": ["HealthCheck", "Engagement", "Plan"],
        "used_in": [
            "src/harness/analysis/",
            "src/harness/health.py",
        ],
    },
    "WorkflowStatus": {
        "definition": "Lifecycle status of a workflow execution: PENDING → ACTIVE → COMPLETED | FAILED.",
        "values": ["pending", "active", "completed", "failed"],
        "relationships": ["Workflow", "WorkflowState"],
        "used_in": ["src/harness/workflow/model.py"],
    },
    "LoopConfig": {
        "definition": (
            "Configuration for a loop step within a phase. Controls iteration "
            "count and optionally convergence behaviour (via ConvergenceConfig). "
            "A loop step repeats its sub-steps until convergence or max iterations."
        ),
        "relationships": ["Step", "ConvergenceConfig"],
        "used_in": ["src/harness/phase/model.py"],
        "key_fields": ["count", "convergence", "description"],
    },
    "StepStatus": {
        "definition": (
            "Execution status for a single step within an iteration. "
            "Values: SUCCESS, FAILURE, SKIPPED. Used in StepResult to indicate "
            "whether the step completed, errored, or was bypassed."
        ),
        "values": ["success", "failure", "skipped"],
        "relationships": ["StepResult", "Step"],
        "used_in": ["src/harness/domain/enums.py"],
    },
    "WaveState": {
        "definition": (
            "Lifecycle state of a development wave. PLANNED (defined but not "
            "started), IN_PROGRESS (currently being worked on), or COMMITTED "
            "(code merged, closed to direct modification). Committed waves "
            "require adjustment/refactor waves for further changes."
        ),
        "values": ["planned", "in_progress", "committed"],
        "relationships": ["Wave", "Plan"],
        "used_in": ["src/harness/plan/wave_model.py"],
    },
    "WaveProvenance": {
        "definition": (
            "Provenance metadata for adjustment/refactor waves. Captures which "
            "phase and reason triggered the rework, plus an optional reference "
            "to the original wave ID. Enables the harness to measure rework "
            "patterns across engagements."
        ),
        "relationships": ["Wave", "Plan"],
        "used_in": ["src/harness/plan/wave_model.py"],
        "key_fields": ["trigger_phase", "trigger_reason", "original_wave_id"],
    },
    "Agent": {
        "definition": (
            "An individual AI agent configured with a role, model, backend, "
            "and prompt. Agents are the atomic execution unit -- dispatched by "
            "AgentService for single-agent steps, or grouped into teams for "
            "parallel dispatch."
        ),
        "relationships": ["AgentService", "Phase", "Step", "TeamRegistry"],
        "used_in": ["src/harness/application/services/agent_service.py"],
    },
    "Backend": {
        "definition": (
            "An agent execution backend registered in PluginRegistry. Backends "
            "resolve model provider connections (e.g. 'api' for OpenAI, 'cli' "
            "for local models) and handle serialisation/deserialisation. "
            "AgentService resolves backends by name from the registry."
        ),
        "relationships": ["PluginRegistry", "AgentService"],
        "used_in": ["src/harness/infrastructure/plugins/registry.py"],
    },
    "ContextPacket": {
        "definition": (
            "A bundle of context data passed to AgentService when dispatching "
            "an agent. Contains the system prompt, conversation history, "
            "engagement context, and any prior artifacts the agent needs."
        ),
        "relationships": ["AgentService", "Agent"],
        "used_in": ["src/harness/application/services/agent_service.py"],
    },
}

# ── Lookup helpers ────────────────────────────────────────────────────────


def lookup(term: str) -> dict | None:
    """Look up a glossary term by name.

    Args:
        term: The term name (case-sensitive).

    Returns:
        The glossary entry dict, or None if the term is not found.
    """
    return GLOSSARY.get(term)


def terms_by_used_in(module_path: str) -> list[str]:
    """Find all terms used in a given module.

    Args:
        module_path: Module path (e.g. "src/harness/phase/model.py").

    Returns:
        Sorted list of term names used in that module.
    """
    return sorted(
        name for name, entry in GLOSSARY.items()
        if module_path in entry.get("used_in", [])
    )


def terms_by_type(entry_type: str) -> list[str]:
    """Find all terms that have a specific type or value.

    Args:
        entry_type: Key in the entry to check (e.g. 'relationships',
            'key_fields').

    Returns:
        Sorted list of term names that have that key.
    """
    return sorted(
        name for name, entry in GLOSSARY.items()
        if entry_type in entry
    )


def all_term_names() -> list[str]:
    """Return all glossary term names, sorted."""
    return sorted(GLOSSARY.keys())


def validate() -> list[str]:
    """Validate that all glossary entries have required fields.

    Each entry must have: 'definition', 'relationships', 'used_in'.

    Returns:
        List of validation warnings. Empty list if all valid.
    """
    warnings: list[str] = []
    required = {"definition", "relationships", "used_in"}
    for name, entry in GLOSSARY.items():
        missing = required - set(entry.keys())
        if missing:
            warnings.append(
                f"'{name}' missing required field(s): {', '.join(sorted(missing))}"
            )
        if not isinstance(entry.get("relationships"), list):
            warnings.append(
                f"'{name}' relationships must be a list"
            )
        if not isinstance(entry.get("used_in"), list):
            warnings.append(
                f"'{name}' used_in must be a list"
            )
    return warnings


__all__ = [
    "GLOSSARY",
    "lookup",
    "terms_by_used_in",
    "terms_by_type",
    "all_term_names",
    "validate",
]
