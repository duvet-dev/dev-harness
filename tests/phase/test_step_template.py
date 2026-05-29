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

    def test_rejects_both_team_and_agents(self) -> None:
        """Setting both team: and agents: should raise."""
        with pytest.raises(StepMutualExclusionError) as exc:
            StepTemplate(
                name="invalid",
                team="architecture",
                agents=["architect"],
            )
        assert "Exactly one" in str(exc.value)

    def test_rejects_neither_team_nor_agents(self) -> None:
        """Setting neither team: nor agents: should raise."""
        with pytest.raises(StepMutualExclusionError) as exc:
            StepTemplate(
                name="invalid",
            )
        assert "Exactly one" in str(exc.value)

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
