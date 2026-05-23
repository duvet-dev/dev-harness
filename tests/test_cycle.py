"""Tests for harness.agents.cycle — multi-agent iteration engine.

Tests dataclasses, built-in definitions, convergence checks, phase jump
helpers, and the CycleRunner engine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.agents.cycle import (
    AGENT_ARCHITECT,
    AGENT_ARCHITECTURE_ANALYSER,
    AGENT_CODER,
    AGENT_TESTER,
    ARTIFACT_DESIGN,
    ARTIFACT_IMPLEMENTATION,
    ARTIFACT_TESTING,
    BUILTIN_CYCLE_DEFINITIONS,
    CONVERGENCE_AGENT_JUDGMENT,
    CONVERGENCE_TIMEOUT_BEST_EFFORT,
    CONVERGENCE_TIMEOUT_FAIL,
    CYCLE_DESIGN_CRITIC,
    CYCLE_TESTING,
    STEP_CONSULT,
    STEP_CRITIQUE,
    STEP_GATE,
    STEP_PRODUCE,
    CycleConvergence,
    CycleResult,
    CycleRunner,
    CycleRunnerDefinition,
    CycleStep,
    CycleStepResult,
    design_cycle_definition,
    discovery_cycle_definition,
    domain_interface_cycle_definition,
    format_phase_jump_status,
    get_cycle_definition,
    is_phase_jump_status,
    list_cycle_definitions,
    parse_phase_jump_target,
    planning_cycle_definition,
    review_cycle_definition,
    self_test_cycle_definition,
    testing_cycle_definition,
    wave_cycle_definition,
    _format_artifacts_for_context,
)


class TestCycleStep:
    """Tests for CycleStep."""

    def test_defaults(self):
        step = CycleStep(agent="architect", step_type="produce")
        assert step.agent == "architect"
        assert step.step_type == "produce"
        assert step.artifact is None
        assert step.max_retries == 1

    def test_is_produce(self):
        assert CycleStep(agent="a", step_type="produce").is_produce() is True
        assert CycleStep(agent="a", step_type="critique").is_produce() is False

    def test_is_critique(self):
        assert CycleStep(agent="a", step_type="critique").is_critique() is True

    def test_is_gate(self):
        assert CycleStep(agent="a", step_type="gate").is_gate() is True

    def test_is_consult(self):
        assert CycleStep(agent="a", step_type="consult").is_consult() is True


class TestCycleConvergence:
    """Tests for CycleConvergence."""

    def test_defaults(self):
        c = CycleConvergence()
        assert c.condition == "all_gates_pass"
        assert c.max_iterations == 3
        assert c.on_timeout == "best_effort"
        assert c.test_command == ""

    def test_reached_timeout(self):
        c = CycleConvergence(max_iterations=3)
        assert c.reached_timeout(3) is True
        assert c.reached_timeout(2) is False


class TestCycleStepResult:
    """Tests for CycleStepResult."""

    def test_defaults(self):
        r = CycleStepResult(agent="architect", step_type="produce", artifact=None)
        assert r.agent == "architect"
        assert r.artifacts == {}
        assert r.status == "success"
        assert r.iteration == 0
        assert r.artifact is None


class TestCycleResult:
    """Tests for CycleResult."""

    def test_defaults(self):
        r = CycleResult()
        assert r.status == "complete"
        assert r.artifacts == {}
        assert r.iterations == 0

    def test_is_phase_jump_true(self):
        r = CycleResult(status="phase_jump:design")
        assert r.is_phase_jump is True
        assert r.jump_target == "design"

    def test_is_phase_jump_false(self):
        r = CycleResult(status="complete")
        assert r.is_phase_jump is False
        assert r.jump_target is None


class TestCycleRunnerDefinition:
    """Tests for CycleRunnerDefinition."""

    def test_defaults(self):
        d = CycleRunnerDefinition(name="test", steps=[])
        assert d.name == "test"
        assert d.steps == []
        assert isinstance(d.convergence, CycleConvergence)
        assert d.initial_phase_artifact == ""
        assert d.final_artifact == ""


class TestBuiltinDefinitions:
    """Tests for built-in cycle definitions."""

    def test_design_cycle_definition(self):
        d = design_cycle_definition()
        assert d.name == "arch-loop"
        assert len(d.steps) == 3
        assert d.steps[0].agent == AGENT_ARCHITECT
        assert d.steps[0].step_type == STEP_PRODUCE
        assert d.steps[1].agent == AGENT_ARCHITECTURE_ANALYSER
        assert d.steps[1].step_type == STEP_CRITIQUE
        assert d.steps[2].step_type == STEP_GATE
        assert d.convergence.condition == CONVERGENCE_AGENT_JUDGMENT
        assert d.convergence.max_iterations == 3
        assert d.final_artifact == ARTIFACT_DESIGN

    def test_wave_cycle_definition(self):
        d = wave_cycle_definition()
        assert d.name == "wave"
        assert len(d.steps) == 6
        assert d.steps[0].agent == AGENT_CODER
        assert d.steps[0].step_type == STEP_PRODUCE
        # Has a consult step
        assert d.steps[2].step_type == STEP_CONSULT
        # Last step is gate
        assert d.steps[5].step_type == STEP_GATE

    def test_discovery_cycle_definition(self):
        d = discovery_cycle_definition()
        assert d.name == "discovery-loop"
        assert len(d.steps) == 3
        assert d.final_artifact == "requirements.md"

    def test_testing_cycle_definition(self):
        d = testing_cycle_definition()
        assert d.name == CYCLE_TESTING
        assert len(d.steps) == 4
        assert d.steps[1].agent == "requirements-conformance-reviewer"

    def test_review_cycle_definition(self):
        d = review_cycle_definition()
        assert d.name == "review-loop"
        assert len(d.steps) == 6

    def test_planning_cycle_definition(self):
        d = planning_cycle_definition()
        assert d.name == "planning-loop"
        assert len(d.steps) == 3

    def test_self_test_cycle_definition(self):
        d = self_test_cycle_definition(
            max_iterations=5,
            task_description="Implement feature",
            test_command="pytest",
        )
        assert d.name == "self-test-loop"
        assert d.convergence.max_iterations == 5
        assert d.convergence.test_command == "pytest"
        assert d.convergence.condition == "test_gate"
        # Should have 3 steps
        assert len(d.steps) == 3

    def test_domain_interface_cycle_definition(self):
        d = domain_interface_cycle_definition()
        assert d.name == "domain-int-loop"
        assert len(d.steps) == 1
        assert d.steps[0].agent == "domain-interface-tester"

    def test_get_cycle_definition(self):
        d = get_cycle_definition("arch-loop")
        assert d is not None
        assert d.name == "arch-loop"

    def test_get_cycle_definition_nonexistent(self):
        d = get_cycle_definition("nonexistent")
        assert d is None

    def test_list_cycle_definitions(self):
        names = list_cycle_definitions()
        assert "arch-loop" in names
        assert "wave" in names
        assert "testing-loop" in names
        assert len(names) >= 8

    def test_builtin_definitions_constant(self):
        assert isinstance(BUILTIN_CYCLE_DEFINITIONS, dict)
        assert "arch-loop" in BUILTIN_CYCLE_DEFINITIONS


class TestPhaseJumpHelpers:
    """Tests for phase jump helper functions."""

    def test_is_phase_jump_status_true(self):
        assert is_phase_jump_status("phase_jump:design") is True
        assert is_phase_jump_status("phase_jump:") is True

    def test_is_phase_jump_status_false(self):
        assert is_phase_jump_status("complete") is False
        assert is_phase_jump_status("") is False
        assert is_phase_jump_status(None) is False

    def test_parse_phase_jump_target(self):
        assert parse_phase_jump_target("phase_jump:design") == "design"
        assert parse_phase_jump_target("complete") is None

    def test_format_phase_jump_status(self):
        assert format_phase_jump_status("design") == "phase_jump:design"


class TestForamtArtifacts:
    """Tests for _format_artifacts_for_context()."""

    def test_empty(self):
        assert _format_artifacts_for_context({}) == ""

    def test_single_artifact(self):
        text = _format_artifacts_for_context({"plan": "Build feature X"})
        assert "--- plan ---" in text
        assert "Build feature X" in text

    def test_multiple_artifacts(self):
        text = _format_artifacts_for_context({
            "design": "Use hexagonal architecture",
            "review": "Looks good",
        })
        assert "design" in text
        assert "review" in text

    def test_skips_internal_keys(self):
        text = _format_artifacts_for_context({
            "plan": "Do this",
            "_internal": "secret",
        })
        assert "Do this" in text
        assert "secret" not in text

    def test_truncates_large_content(self):
        content = "x" * 5000
        text = _format_artifacts_for_context({"big": content})
        # Should be truncated to 2000 chars
        assert len(text) < 5000


class TestCycleRunnerBasicChecks:
    """Tests for CycleRunner's convergence check methods."""

    @pytest.fixture
    def runner(self):
        return CycleRunner()

    def test_check_all_gates_passing(self, runner):
        results = [
            CycleStepResult(agent="a", step_type="gate", artifact=None, status="success",
                            artifacts={"output": "All good"}),
        ]
        assert runner._check_all_gates_passing(results) is True

    def test_check_all_gates_passing_fails(self, runner):
        results = [
            CycleStepResult(agent="a", step_type="gate", artifact=None, status="success",
                            artifacts={"output": ""}),
        ]
        assert runner._check_all_gates_passing(results) is False

    def test_check_all_gates_passing_no_gates(self, runner):
        results = [
            CycleStepResult(agent="a", step_type="produce", artifact=None),
        ]
        assert runner._check_all_gates_passing(results) is False

    def test_check_agent_judgment_keyword_found(self, runner):
        results = [
            CycleStepResult(agent="a", step_type="gate", artifact=None, status="success",
                            artifacts={"output": "converged after review"}),
        ]
        assert runner._check_agent_judgment(results) is True

    def test_check_agent_judgment_no_keyword(self, runner):
        results = [
            CycleStepResult(agent="a", step_type="gate", artifact=None, status="success",
                            artifacts={"output": "Needs more work"}),
        ]
        assert runner._check_agent_judgment(results) is False

    def test_check_agent_judgment_from_critique(self, runner):
        results = [
            CycleStepResult(agent="a", step_type="critique", artifact=None, status="success",
                            artifacts={"output": "no new issues found"}),
        ]
        assert runner._check_agent_judgment(results) is True

    def test_check_no_changes_first_iteration(self, runner):
        """First iteration should not converge."""
        artifacts = {"design": "Initial design"}
        results = [
            CycleStepResult(agent="a", step_type="produce", artifact="design",
                            artifacts={"output": "Initial design"}),
        ]
        # First iteration: no history, so should return False
        assert runner._check_no_changes(results, artifacts) is False

    def test_detect_test_command(self, runner, tmp_path):
        """_detect_test_command detects pytest."""
        (tmp_path / "pytest.ini").write_text("[pytest]\n")
        cmd = runner._detect_test_command(tmp_path)
        assert cmd is not None
        assert "pytest" in " ".join(cmd)

    def test_detect_test_command_none(self, runner, tmp_path):
        """_detect_test_command returns None for unknown projects."""
        cmd = runner._detect_test_command(tmp_path)
        assert cmd is None

    def test_resolve_project_root_finds_git(self, runner, tmp_path):
        """_resolve_project_root finds root with .git."""
        (tmp_path / ".git").mkdir()
        root = runner._resolve_project_root()
        assert root is not None

    def test_convergence_default_check(self, runner):
        """Default check returns False for unknown condition."""
        definition = CycleRunnerDefinition(
            name="test",
            steps=[],
            convergence=CycleConvergence(condition="approval"),
        )
        assert runner._check_convergence(definition, [], {}) is False
