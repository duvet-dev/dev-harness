"""Tests for StepTemplate dataclass (phase/template.py).

V7 §10.5 — StepTemplate with mutual exclusivity rule for team/agents.
"""

from __future__ import annotations

import pytest

from harness.errors import StepMutualExclusionError
from harness.phase.template import StepTemplate
from harness.artifact.types import ArtifactType


# ── Construction ────────────────────────────────────────────────────────


class TestConstruction:
    """Tests for StepTemplate construction and validation."""

    def test_creates_team_based_template(self) -> None:
        """A template with team: should be valid."""
        template = StepTemplate(
            name="comprehensive-arch-review",
            team="architecture",
            output=[ArtifactType.ARCHITECTURE_DECISION],
        )
        assert template.name == "comprehensive-arch-review"
        assert template.team == "architecture"
        assert template.agents is None
        assert template.template_type == "team"

    def test_creates_agent_based_template(self) -> None:
        """A template with agents: should be valid."""
        template = StepTemplate(
            name="quick-security-scan",
            agents=["security-critic"],
            output=[ArtifactType.ARCHITECTURE_DECISION],
            parallel=False,
        )
        assert template.name == "quick-security-scan"
        assert template.agents == ["security-critic"]
        assert template.team is None
        assert template.template_type == "agents"

    def test_accepts_critic_loop_template_with_loop_steps(self) -> None:
        """A critic loop template with loop+steps is valid, not an error."""
        from harness.phase.model import (
            ConvergenceConfig,
            LoopConfig,
            Step as PhaseStep,
        )
        template = StepTemplate(
            name="design-cycle",
            description="Architect produce -> critic -> gate",
            loop=LoopConfig(
                convergence=ConvergenceConfig(
                    strategy="gate_judgment",
                    max_iterations=3,
                ),
            ),
            steps=[
                PhaseStep(agents=["architect"], role="produce"),
                PhaseStep(agents=["architecture-analyser"], role="critique"),
            ],
            output_artifact_name="final-design",
        )
        assert template.name == "design-cycle"
        assert template.template_type == "critic_loop"

    def test_accepts_critic_loop_template(self) -> None:
        """A critic loop template with loop+steps is valid."""
        from harness.phase.model import (
            ConvergenceConfig,
            LoopConfig,
        )
        template = StepTemplate(
            name="design-cycle",
            description="Architect produce -> critic -> gate",
            loop=LoopConfig(
                convergence=ConvergenceConfig(
                    strategy="gate_judgment",
                    max_iterations=3,
                ),
            ),
            steps=[],
            input_artifact_names=[],
            output_artifact_name="final-design",
        )
        assert template.name == "design-cycle"
        assert template.template_type == "critic_loop"
        assert template.loop is not None
        assert template.team is None
        assert template.agents is None

    def test_default_values(self) -> None:
        """Default values should be correct."""
        template = StepTemplate(
            name="defaults-test",
            agents=["architect"],
        )
        assert template.parallel is False
        assert template.role is None
        assert template.input is None
        assert template.output is None
        assert template.description is None
        assert template.template_type == "agents"

    def test_all_fields_set(self) -> None:
        """All fields should be settable."""
        template = StepTemplate(
            name="full-template",
            agents=["a", "b"],
            parallel=True,
            role="reviewer",
            input=[ArtifactType.REQUIREMENTS_SPEC],
            output=[ArtifactType.ARCHITECTURE_DECISION],
            description="Full review template",
        )
        assert template.parallel is True
        assert template.role == "reviewer"
        assert template.input == [ArtifactType.REQUIREMENTS_SPEC]
        assert template.output == [ArtifactType.ARCHITECTURE_DECISION]
        assert template.description == "Full review template"

    def test_template_type_unknown_when_neither_set(self) -> None:
        """template_type returns 'unknown' when neither team/agents set.

        This bypasses __post_init__ validation to test the fallback
        return path (coverage line 88).
        """
        template = object.__new__(StepTemplate)
        template.name = "fallback-test"
        template.team = None
        template.agents = None
        assert template.template_type == "unknown"
