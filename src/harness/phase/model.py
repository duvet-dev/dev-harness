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
class LoopConfig:
    """Configuration for a loop step (R33).

    Attributes:
        count: Number of iterations. Default 1.
        description: Human-readable description of the loop.
    """

    count: int = 1
    description: str = ""


@dataclass
class Step:
    """A single step in a phase — can be an agent, loop, or phase step.

    Exactly one of the four mutually exclusive fields must be set:
    agents, team, loop, or phase.

    Attributes:
        agents: Explicit list of agent names for an agent step.
        team: Team name reference (auto-expands via TeamRegistry).
        loop: LoopConfig for a recursive sub-loop step.
        phase: Name of another phase to jump to.
        parallel: If True, dispatch agents in parallel.
        lead: Lead agent name for aggregation.
        serial_lead: Lead agent for serial dispatch.
        input: Required input artifact types.
        output: Output artifact types produced.
        role: Agent role override for this step.
        action: Action description for the step.
        auto: If True, step runs automatically without user prompt.
    """

    # Mutually exclusive — exactly one of these four:
    agents: list[str] | None = None
    team: str | None = None
    loop: LoopConfig | None = None
    phase: str | None = None

    # Common fields:
    parallel: bool = False
    lead: str | None = None
    serial_lead: str | None = None
    input: list[ArtifactType] | None = None
    output: list[ArtifactType] | None = None
    role: str | None = None
    action: str | None = None
    auto: bool | None = None

    def __post_init__(self) -> None:
        """Validate mutual exclusivity of agents/team/loop/phase.

        Raises StepMutualExclusionError if not exactly one is set.
        """
        specified = sum(
            [
                self.agents is not None,
                self.team is not None,
                self.loop is not None,
                self.phase is not None,
            ]
        )
        if specified != 1:
            raise StepMutualExclusionError(
                "Exactly one of 'agents', 'team', 'loop', or 'phase' "
                "must be specified. "
                f"Found {specified} (agents={self.agents}, "
                f"team={self.team}, loop={self.loop}, "
                f"phase={self.phase})"
            )

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
