"""Tests for phase/model.py: Step, LoopConfig, Phase dataclasses."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from harness.artifact.types import ArtifactType
from harness.errors import StepMutualExclusionError
from harness.phase.model import LoopConfig, Phase, Step


class TestLoopConfig:
    """LoopConfig dataclass tests."""

    def test_defaults(self) -> None:
        config = LoopConfig()
        assert config.count == 1
        assert config.description == ""

    def test_custom_values(self) -> None:
        config = LoopConfig(count=3, description="Review loop")
        assert config.count == 3
        assert config.description == "Review loop"

    def test_zero_count(self) -> None:
        """Zero count is valid (no-op loop)."""
        config = LoopConfig(count=0)
        assert config.count == 0


class TestStepMutexValidation:
    """Step mutual exclusivity validation tests."""

    def test_agents_only(self) -> None:
        step = Step(agents=["architect"])
        assert step.agents == ["architect"]
        assert step.team is None
        assert step.loop is None
        assert step.phase is None
        assert step.step_type == "agent"

    def test_team_only(self) -> None:
        step = Step(team="architecture")
        assert step.team == "architecture"
        assert step.step_type == "team"

    def test_loop_only(self) -> None:
        step = Step(loop=LoopConfig(count=3))
        assert step.loop is not None
        assert step.loop.count == 3
        assert step.step_type == "loop"

    def test_phase_only(self) -> None:
        step = Step(phase="build")
        assert step.phase == "build"
        assert step.step_type == "phase"

    def test_no_fields_raises(self) -> None:
        with pytest.raises(StepMutualExclusionError) as exc:
            Step()
        assert "Exactly one of" in str(exc.value)
        assert "Found 0" in str(exc.value)

    def test_two_fields_raises(self) -> None:
        with pytest.raises(StepMutualExclusionError) as exc:
            Step(agents=["a"], team="b")
        assert "Found 2" in str(exc.value)

    def test_three_fields_raises(self) -> None:
        with pytest.raises(StepMutualExclusionError):
            Step(agents=["a"], team="b", loop=LoopConfig())

    def test_all_four_fields_raises(self) -> None:
        with pytest.raises(StepMutualExclusionError):
            Step(
                agents=["a"],
                team="b",
                loop=LoopConfig(),
                phase="c",
            )

    def test_phase_included_in_mutex(self) -> None:
        """V5 review blocker: phase: must be in mutex check."""
        with pytest.raises(StepMutualExclusionError):
            Step(agents=["a"], phase="build")


class TestStepCommonFields:
    """Step common field tests."""

    def test_defaults(self) -> None:
        step = Step(agents=["coder"])
        assert step.parallel is False
        assert step.lead is None
        assert step.serial_lead is None
        assert step.input is None
        assert step.output is None
        assert step.role is None
        assert step.action is None
        assert step.auto is None

    def test_parallel_flag(self) -> None:
        step = Step(agents=["a", "b"], parallel=True)
        assert step.parallel is True

    def test_lead_agent(self) -> None:
        step = Step(
            agents=["a", "b"],
            parallel=True,
            lead="review-coordinator",
        )
        assert step.lead == "review-coordinator"

    def test_serial_lead(self) -> None:
        step = Step(
            agents=["a", "b"],
            serial_lead="lead-agent",
        )
        assert step.serial_lead == "lead-agent"

    def test_input_output(self) -> None:
        step = Step(
            agents=["architect"],
            input=[ArtifactType.REQUIREMENTS_SPEC],
            output=[ArtifactType.ARCHITECTURE_DECISION],
        )
        assert step.input == [ArtifactType.REQUIREMENTS_SPEC]
        assert step.output == [ArtifactType.ARCHITECTURE_DECISION]

    def test_role_and_action(self) -> None:
        step = Step(
            agents=["tester"],
            role="lead-tester",
            action="Run integration tests",
        )
        assert step.role == "lead-tester"
        assert step.action == "Run integration tests"

    def test_auto_flag(self) -> None:
        step = Step(agents=["builder"], auto=True)
        assert step.auto is True

    def test_output_as_string_normalised(self) -> None:
        """String output is normalised to list[str] (line 185)."""
        step = Step(agents=["coder"], output="single-line-output")
        assert isinstance(step.output, list)
        assert step.output == ["single-line-output"]

    def test_step_type_template(self) -> None:
        """step_type returns 'template' when template is set (lines 198-199)."""
        step = Step(template="review-template")
        assert step.step_type == "template"

    def test_step_type_unknown(self) -> None:
        """step_type returns 'unknown' as fallback (line 200)."""
        # Bypass __post_init__ mutex check by using super().__init__
        step = Step.__new__(Step)
        assert step.step_type == "unknown"


class TestPhase:
    """Phase dataclass tests."""

    def test_minimal_phase(self) -> None:
        phase = Phase(
            name="design",
            lead_agent="design-coordinator",
            chat_agent="technical-conversationalist",
        )
        assert phase.name == "design"
        assert phase.lead_agent == "design-coordinator"
        assert phase.chat_agent == "technical-conversationalist"
        assert phase.steps == []
        assert phase.reentry is None

    def test_phase_with_steps(self) -> None:
        phase = Phase(
            name="build",
            lead_agent="coding-agent",
            chat_agent="technical-conversationalist",
            steps=[
                Step(agents=["architect"]),
                Step(team="coding", parallel=True),
            ],
        )
        assert len(phase.steps) == 2
        assert phase.steps[0].agents == ["architect"]
        assert phase.steps[1].team == "coding"

    def test_reentry_resume(self) -> None:
        phase = Phase(
            name="test",
            lead_agent="testing-agent",
            chat_agent="technical-conversationalist",
            reentry="resume",
        )
        assert phase.reentry == "resume"

    def test_reentry_restart(self) -> None:
        phase = Phase(
            name="validate",
            lead_agent="validation-agent",
            chat_agent="technical-conversationalist",
            reentry="restart",
        )
        assert phase.reentry == "restart"
