"""StepTemplate data model — V7 §10.5, D35.

A StepTemplate is a config-driven blueprint for creating concrete Step
instances. Templates reference teams or agents (mutually exclusive, same
rule as Step) and carry output, parallel, role, input, and description
fields that are merged into the resolved Step.

See V7 §7 (Config Schema: step_templates.yaml) and §10.5 for the full
specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.artifact.types import ArtifactType
from harness.errors import StepMutualExclusionError


@dataclass
class StepTemplate:
    """A config-driven step template for creating concrete Step instances.

    Templates define reusable step blueprints in config
    (``.harness/step_templates.yaml``). They are resolved into concrete
    :class:`Step <harness.phase.model.Step>` objects at runtime by the
    :class:`StepTemplateRegistry`.

    Exactly one of ``team`` or ``agents`` must be set (D35). This is
    the same mutual exclusivity rule as :class:`Step`.

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
    """

    name: str

    # Mutually exclusive — exactly one of these two:
    team: str | None = None
    agents: list[str] | None = None

    # Step configuration fields:
    output: list[ArtifactType] | None = None
    parallel: bool = False
    role: str | None = None
    input: list[ArtifactType] | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate mutual exclusivity of team and agents.

        Raises StepMutualExclusionError if both or neither is set.
        """
        specified = sum(
            [
                self.team is not None,
                self.agents is not None,
            ]
        )
        if specified != 1:
            raise StepMutualExclusionError(
                "Exactly one of 'team' or 'agents' must be specified "
                "in a StepTemplate. "
                f"Found {specified} (team={self.team}, "
                f"agents={self.agents})"
            )

    @property
    def template_type(self) -> str:
        """Return 'team' or 'agents' depending on which field is set."""
        if self.team is not None:
            return "team"
        if self.agents is not None:
            return "agents"
        return "unknown"
