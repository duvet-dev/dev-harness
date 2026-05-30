"""Data models for phase orchestration.

Defines the recursive Step model (agent step | loop step | phase step),
LoopConfig for loop steps, and Phase for phase definitions.
See V7 §2.1 and §5.1 for the design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.artifact.types import ArtifactType
from harness.errors import StepMutualExclusionError


@dataclass
class ConvergenceConfig:
    """Configuration for convergence-aware loop iteration.

    Attributes:
        strategy: Which convergence strategy to use.
            - "gate_judgment": Gate agent's output signals convergence.
            - "all_gates": All gate steps produce non-empty output.
            - "test_suite": External test suite passes.
            - "stable": Produce output unchanged between iterations.
            - "external_approval": External callback confirms convergence.
        max_iterations: Hard cap on iterations before timeout.
        on_timeout: Behaviour on max iterations.
            - "best_effort": Return best artifacts with "timeout" status.
            - "fail": Return "error" status.
        gate_agent: For gate_judgment — which agent role to inspect for
            convergence keywords. If None, inspects all gate steps.
        test_command: For test_suite — explicit test command.
        convergence_keywords: Override default convergence keywords
            for gate_judgment.
        test_output_path: For test_suite — path to write captured test
            output for persistent storage across context rebuilds.
    """

    strategy: str = "gate_judgment"
    max_iterations: int = 3
    on_timeout: str = "best_effort"  # "best_effort" | "fail"
    gate_agent: str | None = None
    test_command: str = ""
    convergence_keywords: list[str] | None = None
    test_output_path: str = ".harness/test_output/latest.txt"


@dataclass
class LoopConfig:
    """Configuration for a loop step (R33).

    Attributes:
        count: Number of iterations. Default 1. Ignored when
            convergence is set.
        convergence: Optional convergence configuration. When set,
            iteration count is determined by
            convergence.max_iterations.
        description: Human-readable description of the loop.
    """

    count: int = 1
    convergence: ConvergenceConfig | None = None
    description: str = ""


@dataclass
class ConvergenceVerdict:
    """Result of a convergence check.

    Attributes:
        converged: True if the loop should stop.
        status_override: Alternative status to return
            (e.g. "phase_jump:design").
        reason: Human-readable explanation.
        test_output: Test output from test_suite strategy — captured
            for feed-through to the next iteration.
    """

    converged: bool = False
    status_override: str | None = None
    reason: str = ""
    test_output: str | None = None


@dataclass
class StepResult:
    """Result of executing a single step within a loop iteration.

    Attributes:
        step_type: The step role ("produce", "critique",
            "gate", "consult").
        step_role: The agent/team/phase that ran.
        status: "success" | "failure" | "skipped".
        artifacts: Artifact keys and content produced.
        error: Error message on failure.
        iteration: Which iteration this step belonged to.
        retries: Number of retries attempted before success/failure.
    """

    step_type: str = ""
    step_role: str = ""
    status: str = "success"
    artifacts: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    iteration: int = 0
    retries: int = 0


@dataclass
class Step:
    """A single step in a phase — can be an agent, loop, phase,
    or template step.

    Exactly one of the five mutually exclusive fields must be set:
    agents, team, loop, phase, or template.

    v4 CHANGE: output now accepts free-form strings (str | list[str] | None)
    instead of list[ArtifactType]. This decouples template output names
    from the ArtifactType enum, consistent with the V7 Step model.

    Attributes:
        agents: Explicit list of agent names for an agent step.
        team: Team name reference (auto-expands via TeamRegistry).
        loop: LoopConfig for a recursive sub-loop step.
        phase: Name of another phase to jump to.
        template: Name of a step template to expand.
        parallel: If True, dispatch agents in parallel.
        lead: Lead agent name for aggregation.
        serial_lead: Lead agent for serial dispatch.
        input: Required input artifact types.
        output: Output artifact names produced (free-form strings).
        role: Agent role override for this step.
        action: Action description for the step.
        auto: If True, step runs automatically without user prompt.
        max_retries: Per-step retry on agent dispatch failure.
    """

    # Mutually exclusive — exactly one of these five:
    agents: list[str] | None = None
    team: str | None = None
    loop: LoopConfig | None = None
    phase: str | None = None
    template: str | None = None

    # Common fields:
    parallel: bool = False
    lead: str | None = None
    serial_lead: str | None = None
    input: list[ArtifactType] | None = None
    # v4 CHANGE: output now accepts free-form strings.
    output: str | list[str] | None = None
    role: str | None = None
    action: str | None = None
    auto: bool | None = None
    max_retries: int = 1

    def __post_init__(self) -> None:
        """Validate mutual exclusivity and normalise output.

        Raises StepMutualExclusionError if not exactly one of
        agents/team/loop/phase/template is set.
        """
        specified = sum(
            [
                self.agents is not None,
                self.team is not None,
                self.loop is not None,
                self.phase is not None,
                self.template is not None,
            ]
        )
        if specified != 1:
            raise StepMutualExclusionError(
                "Exactly one of 'agents', 'team', 'loop', 'phase', or "
                "'template' must be specified. "
                f"Found {specified} (agents={self.agents}, "
                f"team={self.team}, loop={self.loop}, "
                f"phase={self.phase}, template={self.template})"
            )

        # Normalise output to list[str] for internal consistency
        if isinstance(self.output, str):
            self.output = [self.output]

    @property
    def step_type(self) -> str:
        """Return the human-readable step type name."""
        if self.agents is not None:
            return "agent"
        if self.team is not None:
            return "team"
        if self.loop is not None:
            return "loop"
        if self.phase is not None:
            return "phase"
        if self.template is not None:
            return "template"
        return "unknown"


@dataclass
class Phase:
    """Definition of a phase in a workflow.

    Attributes:
        name: Unique phase name.
        lead_agent: Agent responsible for leading this phase.
        chat_agent: Agent handling user chat during this phase.
        steps: Ordered list of steps to execute.
        reentry: Re-entry semantics ("restart", "resume", or None).
    """

    name: str
    lead_agent: str
    chat_agent: str
    steps: list[Step] = field(default_factory=list)
    reentry: str | None = None
