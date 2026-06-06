"""StepTemplate data model — V7 §10.5, D35.

A StepTemplate is a config-driven blueprint for creating concrete Step
instances. Templates reference teams or agents (mutually exclusive, same
rule as Step) and carry output, parallel, role, input, and description
fields that are merged into the resolved Step.

For critic loop templates, templates can also carry `loop` and `steps`
fields. When set, the template represents a convergence-aware critic loop
rather than a single agent/team step.

See V7 §7 (Config Schema: step_templates.yaml) and §10.5 for the full
specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.artifact.types import ArtifactType
from harness.errors import StepMutualExclusionError
from harness.phase.model import LoopConfig, Step


@dataclass
class StepTemplate:
    """A config-driven step template for creating concrete Step instances.

    Templates define reusable step blueprints in config
    (``.harness/step_templates.yaml``). They are resolved into concrete
    :class:`Step <harness.phase.model.Step>` objects at runtime by the
    :class:`StepTemplateRegistry`.

    For simple templates, exactly one of ``team`` or ``agents`` must be
    set (D35). For critic loop templates, ``loop`` and ``steps`` can be
    set instead.

    Attributes:
        name: Unique template name used for lookups.
        team: Team name reference (mutually exclusive with agents).
            Auto-expands via TeamRegistry when the template is expanded.
        agents: Explicit list of agent names (mutually exclusive with
            team).
        output: Output artifact types produced by steps from this
            template.
        parallel: If True, agents are dispatched in parallel.
        role: Agent role override for steps from this template.
        input: Required input artifact types for steps from this
            template.
        description: Human-readable description of what this template
            does.
        loop: Loop configuration for critic loop templates. When set,
            the template expands to a loop step with convergence config.
        steps: Sub-steps for the critic loop. Only valid when ``loop``
            is also set.
        input_artifact_names: [DEPRECATED] Use ``input`` instead.
            Retained for backward compatibility only - will be
            removed in a future wave.
        output_artifact_name: [DEPRECATED] Use ``output`` instead.
            Retained for backward compatibility only - will be
            removed in a future wave.
    """

    name: str

    # Simple template fields (mutually exclusive with loop+steps):
    team: str | None = None
    agents: list[str] | None = None

    # Step configuration fields:
    output: list[ArtifactType] | str | None = None
    parallel: bool = False
    role: str | None = None
    input: list[ArtifactType] | None = None
    description: str | None = None

    # Critic loop template fields:
    loop: LoopConfig | None = None
    steps: list[Step] = field(default_factory=list)
    input_artifact_names: list[str] | None = None
    output_artifact_name: str | None = None

    def __post_init__(self) -> None:
        """Validate mutual exclusivity of team/agents and loop+steps.

        Raises StepMutualExclusionError if both team/agents AND
        loop+steps are set, or if neither side is populated
        meaningfully.
        """
        has_simple = self.team is not None or self.agents is not None
        has_loop = self.loop is not None and len(self.steps) > 0

        if has_simple and has_loop:
            raise StepMutualExclusionError(
                "A StepTemplate cannot have both team/agents AND "
                "loop/steps. Use one or the other. "
                f"team={self.team}, agents={self.agents}, "
                f"loop={'set' if self.loop else 'None'}, "
                f"steps={len(self.steps)}"
            )

    @property
    def template_type(self) -> str:
        """Return 'team', 'agents', or 'critic_loop' depending on config."""
        if self.team is not None:
            return "team"
        if self.agents is not None:
            return "agents"
        if self.loop is not None:
            return "critic_loop"
        return "unknown"
