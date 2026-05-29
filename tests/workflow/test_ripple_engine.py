"""Tests for workflow/ripple_engine.py: WorkflowRippleEngine.

Tests cover:
- TransitionType enum
- PhaseTransition dataclass
- determine_transition: linear flow
- determine_transition: end of workflow
- determine_transition: failed phase → re-entry
- determine_transition: conditional transitions
- ArtifactConditionRule
- FailureConditionRule
- Optional phase skipping
- Ripple effect detection
- Artifact passing between phases
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from harness.phase.strategy.base import PhaseResult
from harness.workflow.model import (
    WorkflowState,
    WorkflowStatus,
)
from harness.workflow.ripple_engine import (
    ArtifactConditionRule,
    FailureConditionRule,
    PhaseTransition,
    RippleEffect,
    TransitionType,
    WorkflowRippleEngine,
)


# ── TransitionType & PhaseTransition Tests ──────────────────────────


class TestTransitionType:
    """TransitionType enum tests."""

    def test_enum_values(self) -> None:
        assert TransitionType.LINEAR == "linear"
        assert TransitionType.CONDITIONAL == "conditional"
        assert TransitionType.OPTIONAL_SKIP == "optional_skip"
        assert TransitionType.END_OF_WORKFLOW == "end_of_workflow"


class TestPhaseTransition:
    """PhaseTransition dataclass tests."""

    def test_minimal(self) -> None:
        t = PhaseTransition(transition_type=TransitionType.LINEAR)
        assert t.transition_type == TransitionType.LINEAR
        assert t.next_phase is None
        assert t.reason == ""
        assert t.artifacts_passed == []
        assert t.conditional_result is None
        assert not t.re_enter_current

    def test_with_next_phase(self) -> None:
        t = PhaseTransition(
            transition_type=TransitionType.LINEAR,
            next_phase="design",
            reason="Standard progression",
        )
        assert t.next_phase == "design"
        assert t.reason == "Standard progression"

    def test_re_enter_current(self) -> None:
        t = PhaseTransition(
            transition_type=TransitionType.CONDITIONAL,
            next_phase="build",
            re_enter_current=True,
        )
        assert t.re_enter_current


# ── Linear Flow Tests ───────────────────────────────────────────────


class TestLinearFlow:
    """Basic linear phase-to-phase transitions."""

    def test_determine_transition_linear(self) -> None:
        state = WorkflowState(
            workflow_name="standard",
            slug="test",
            pending_phases=["a", "b", "c"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")

        engine = WorkflowRippleEngine()
        transition = engine.determine_transition(state)

        assert transition.transition_type == TransitionType.LINEAR
        assert transition.next_phase == "b"
        assert "Linear progression" in transition.reason

    def test_determine_transition_last_phase_to_end(self) -> None:
        state = WorkflowState(
            workflow_name="standard",
            slug="test",
            pending_phases=["a"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")

        engine = WorkflowRippleEngine()
        transition = engine.determine_transition(state)

        assert transition.transition_type == TransitionType.END_OF_WORKFLOW
        assert transition.next_phase is None
        assert "All phases complete" in transition.reason

    def test_determine_transition_multiple_steps(self) -> None:
        state = WorkflowState(
            workflow_name="standard",
            slug="test",
            pending_phases=["a", "b", "c"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")
        state.mark_phase_started("b")
        state.mark_phase_completed("b")

        engine = WorkflowRippleEngine()
        transition = engine.determine_transition(state)

        assert transition.next_phase == "c"

    def test_determine_transition_no_completed_phases(self) -> None:
        state = WorkflowState(
            workflow_name="standard",
            slug="test",
            pending_phases=["a", "b"],
        )

        engine = WorkflowRippleEngine()
        transition = engine.determine_transition(state)

        assert transition.transition_type == TransitionType.LINEAR
        assert transition.next_phase == "a"
        assert "Starting first phase" in transition.reason

    def test_determine_transition_no_pending_and_no_current(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            slug="test",
            completed_phases=["a"],
            status=WorkflowStatus.COMPLETED,
        )

        engine = WorkflowRippleEngine()
        transition = engine.determine_transition(state)

        assert transition.transition_type == TransitionType.END_OF_WORKFLOW
        assert transition.next_phase is None


# ── Conditional Transition Tests ────────────────────────────────────


class TestConditionalTransitions:
    """Conditional phase-to-phase transitions."""

    def test_artifact_condition_rule_matches(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            slug="test",
            pending_phases=["a", "b", "c"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")

        engine = WorkflowRippleEngine()
        rule = ArtifactConditionRule(
            target_phase="c",
            artifact_type="code_diff",
            description="Skip to c if code_diff produced",
        )
        engine.add_conditional_rule("a", rule)

        artifact_map = {
            "a": [{"type": "code_diff", "content": "..."}]
        }
        transition = engine.determine_transition(
            state,
            artifact_map=artifact_map,
        )

        assert transition.transition_type == TransitionType.CONDITIONAL
        assert transition.next_phase == "c"
        assert transition.conditional_result is not None
        assert "code_diff" in transition.conditional_result

    def test_artifact_condition_rule_not_matched(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            slug="test",
            pending_phases=["a", "b", "c"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")

        engine = WorkflowRippleEngine()
        rule = ArtifactConditionRule(
            target_phase="c",
            artifact_type="review_report",
        )
        engine.add_conditional_rule("a", rule)

        artifact_map = {
            "a": [{"type": "code_diff", "content": "..."}]
        }
        transition = engine.determine_transition(
            state,
            artifact_map=artifact_map,
        )

        assert transition.transition_type == TransitionType.LINEAR
        assert transition.next_phase == "b"

    def test_artifact_condition_no_artifact_map(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            slug="test",
            pending_phases=["a", "b"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")

        engine = WorkflowRippleEngine()
        rule = ArtifactConditionRule(
            target_phase="b",
            artifact_type="code_diff",
        )
        engine.add_conditional_rule("a", rule)

        transition = engine.determine_transition(state)

        assert transition.transition_type == TransitionType.LINEAR
        assert transition.next_phase == "b"

    def test_multiple_rules_first_match_wins(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            slug="test",
            pending_phases=["a", "b", "c", "d"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")

        engine = WorkflowRippleEngine()
        engine.add_conditional_rules("a", [
            ArtifactConditionRule(
                target_phase="c",
                artifact_type="review_report",
            ),
            ArtifactConditionRule(
                target_phase="d",
                artifact_type="code_diff",
            ),
        ])

        artifact_map = {
            "a": [
                {"type": "review_report", "content": "..."},
                {"type": "code_diff", "content": "..."},
            ]
        }
        transition = engine.determine_transition(
            state,
            artifact_map=artifact_map,
        )

        # First matching rule wins → should go to 'c'
        assert transition.next_phase == "c"

    def test_failure_condition_rule(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            slug="test",
            pending_phases=["a", "b"],
        )
        state.mark_phase_started("a")
        state.mark_phase_failed("a")

        engine = WorkflowRippleEngine()
        rule = FailureConditionRule(
            target_phase="b",
            description="Jump to recovery on failure",
        )
        engine.add_conditional_rule("a", rule)

        phase_result = PhaseResult(
            success=False,
            error="Something went wrong",
        )
        transition = engine.determine_transition(
            state,
            phase_result=phase_result,
        )

        assert transition.transition_type == TransitionType.CONDITIONAL
        assert transition.next_phase == "b"
        assert "failed" in (transition.conditional_result or "")
        assert transition.reason == "Jump to recovery on failure"

    def test_failure_condition_rule_not_triggered_on_success(
        self,
    ) -> None:
        state = WorkflowState(
            workflow_name="test",
            slug="test",
            pending_phases=["a", "b"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")

        engine = WorkflowRippleEngine()
        rule = FailureConditionRule(
            target_phase="b",
        )
        engine.add_conditional_rule("a", rule)

        phase_result = PhaseResult(success=True)
        transition = engine.determine_transition(
            state,
            phase_result=phase_result,
        )

        assert transition.transition_type == TransitionType.LINEAR
        assert transition.next_phase == "b"

    def test_get_rules_for_phase(self) -> None:
        engine = WorkflowRippleEngine()
        rule1 = ArtifactConditionRule(
            target_phase="c", artifact_type="code_diff"
        )
        rule2 = FailureConditionRule(target_phase="d")
        engine.add_conditional_rules("a", [rule1, rule2])

        rules = engine.get_rules_for_phase("a")
        assert len(rules) == 2
        assert rules[0] is rule1
        assert rules[1] is rule2

    def test_get_rules_for_phase_empty(self) -> None:
        engine = WorkflowRippleEngine()
        rules = engine.get_rules_for_phase("nonexistent")
        assert rules == []

    def test_artifact_rule_with_object_artifact(
        self,
    ) -> None:
        """Test rule matching on artifact objects with .artifact_type."""
        state = WorkflowState(
            workflow_name="test",
            slug="test",
            pending_phases=["a", "b", "c"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")

        engine = WorkflowRippleEngine()
        rule = ArtifactConditionRule(
            target_phase="c",
            artifact_type="planning_doc",
        )
        engine.add_conditional_rule("a", rule)

        # Simulate an artifact object with artifact_type attr
        class FakeArtifact:
            def __init__(self, artifact_type: str) -> None:
                self.artifact_type = artifact_type

        artifact_map = {
            "a": [FakeArtifact(artifact_type="planning_doc")]
        }
        transition = engine.determine_transition(
            state, artifact_map=artifact_map
        )

        assert transition.transition_type == TransitionType.CONDITIONAL
        assert transition.next_phase == "c"


# ── Optional Phase Tests ────────────────────────────────────────────


class TestOptionalPhases:
    """Optional phase support."""

    def test_optional_phase_by_prefix(self) -> None:
        engine = WorkflowRippleEngine()
        state = WorkflowState(
            workflow_name="test",
            pending_phases=["a", "optional-review", "b"],
        )

        assert engine.is_phase_optional("optional-review", state)
        assert not engine.is_phase_optional("a", state)

    def test_optional_phase_by_metadata(self) -> None:
        engine = WorkflowRippleEngine()
        state = WorkflowState(
            workflow_name="test",
            pending_phases=["review"],
            metadata={"optional_phases": ["review"]},
        )

        assert engine.is_phase_optional("review", state)

    def test_optional_phase_not_optional(self) -> None:
        engine = WorkflowRippleEngine()
        state = WorkflowState(
            workflow_name="test",
            pending_phases=["review"],
        )

        assert not engine.is_phase_optional("review", state)

    def test_skip_optional_phase(self) -> None:
        engine = WorkflowRippleEngine()
        state = WorkflowState(
            workflow_name="test",
            pending_phases=["a", "optional-x", "b"],
        )

        transition = engine.skip_optional_phase("optional-x", state)
        assert transition.transition_type == TransitionType.OPTIONAL_SKIP
        # After removing "optional-x", the first pending phase is "a"
        assert transition.next_phase == "a"
        assert "optional-x" not in state.pending_phases

    def test_skip_last_optional_phase(
        self,
    ) -> None:
        engine = WorkflowRippleEngine()
        state = WorkflowState(
            workflow_name="test",
            pending_phases=["optional-x"],
        )

        transition = engine.skip_optional_phase("optional-x", state)
        assert transition.transition_type == TransitionType.OPTIONAL_SKIP
        assert transition.next_phase is None

    def test_skip_unknown_phase_raises(self) -> None:
        engine = WorkflowRippleEngine()
        state = WorkflowState(
            workflow_name="test",
            pending_phases=["a"],
        )

        with pytest.raises(ValueError, match="not in pending"):
            engine.skip_optional_phase("unknown", state)


# ── Ripple Effect Tests ─────────────────────────────────────────────


class TestRippleEffects:
    """Ripple effect detection."""

    def test_detect_downstream_effect(self) -> None:
        engine = WorkflowRippleEngine()
        effects = engine.determine_ripple_effects(
            changed_phase="design",
            completed_phases=["discover", "design"],
            pending_phases=["build", "test"],
            artifact_map={
                "design": [{"type": "architecture_decision"}],
            },
        )

        assert len(effects) >= 1
        assert effects[0].source_phase == "design"
        assert "build" in effects[0].affected_phases
        assert "test" in effects[0].affected_phases

    def test_no_downstream_phases_no_effect(self) -> None:
        engine = WorkflowRippleEngine()
        effects = engine.determine_ripple_effects(
            changed_phase="build",
            completed_phases=["build"],
            pending_phases=[],
            artifact_map={"build": [{"type": "code_diff"}]},
        )

        assert len(effects) == 0

    def test_change_at_start_affects_all(self) -> None:
        engine = WorkflowRippleEngine()
        effects = engine.determine_ripple_effects(
            changed_phase="discover",
            completed_phases=["discover"],
            pending_phases=["design", "build", "test"],
            artifact_map={
                "discover": [{"type": "requirements_spec"}],
            },
        )

        assert len(effects) == 1
        assert effects[0].affected_phases == [
            "design", "build", "test",
        ]

    def test_change_in_middle(self) -> None:
        engine = WorkflowRippleEngine()
        effects = engine.determine_ripple_effects(
            changed_phase="build",
            completed_phases=["discover", "design", "build"],
            pending_phases=["test", "deliver"],
            artifact_map={
                "build": [{"type": "implementation"}],
            },
        )

        assert len(effects) == 1
        assert effects[0].affected_phases == [
            "test", "deliver",
        ]

    def test_no_source_artifacts(self) -> None:
        engine = WorkflowRippleEngine()
        effects = engine.determine_ripple_effects(
            changed_phase="build",
            completed_phases=["discover", "design", "build"],
            pending_phases=["test"],
            artifact_map={},
        )

        # Even without artifacts, downstream phases may be affected
        assert len(effects) >= 1

    def test_ripple_effect_dataclass(self) -> None:
        effect = RippleEffect(
            source_phase="design",
            affected_phases=["build", "test"],
            description="Design change affects build and test",
            severity="warning",
        )
        assert effect.source_phase == "design"
        assert effect.affected_phases == ["build", "test"]
        assert effect.severity == "warning"

    def test_ripple_effect_default_severity(self) -> None:
        effect = RippleEffect(
            source_phase="design",
            affected_phases=["build"],
        )
        assert effect.severity == "info"


# ── Artifact Passing Tests ──────────────────────────────────────────


class TestArtifactPassing:
    """Artifact passing between phases."""

    def test_artifacts_passed_cumulatively(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            slug="test",
            pending_phases=["a", "b"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")

        engine = WorkflowRippleEngine()
        artifact_map = {
            "a": [{"type": "requirements_spec", "content": "reqs"}],
        }
        transition = engine.determine_transition(
            state, artifact_map=artifact_map
        )

        assert len(transition.artifacts_passed) == 1
        assert transition.artifacts_passed[0]["type"] == "requirements_spec"

    def test_artifacts_accumulated(self) -> None:
        """Artifacts from multiple previous phases should be passed."""
        state = WorkflowState(
            workflow_name="test",
            slug="test",
            pending_phases=["a", "b", "c"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")
        state.mark_phase_started("b")
        state.mark_phase_completed("b")

        engine = WorkflowRippleEngine()
        artifact_map = {
            "a": [{"type": "requirements_spec"}],
            "b": [{"type": "architecture_decision"}],
        }
        transition = engine.determine_transition(
            state, artifact_map=artifact_map
        )

        assert len(transition.artifacts_passed) == 2
        types = {a["type"] for a in transition.artifacts_passed}
        assert "requirements_spec" in types
        assert "architecture_decision" in types

    def test_no_artifacts_passed_if_none_produced(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            slug="test",
            pending_phases=["a", "b"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")

        engine = WorkflowRippleEngine()
        transition = engine.determine_transition(state)

        assert transition.artifacts_passed == []


# ── Transition State Handling Tests ─────────────────────────────────


class TestTransitionStateHandling:
    """Edge cases and error handling."""

    def test_failed_phase_re_entry(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            slug="test",
            pending_phases=["a", "b"],
        )
        state.mark_phase_started("a")
        state.mark_phase_failed("a")

        engine = WorkflowRippleEngine()
        phase_result = PhaseResult(
            success=False,
            error="Build failed",
        )
        transition = engine.determine_transition(
            state, phase_result=phase_result
        )

        assert transition.re_enter_current
        assert transition.next_phase == "a"

    def test_successful_phase_no_re_entry(self) -> None:
        state = WorkflowState(
            workflow_name="test",
            slug="test",
            pending_phases=["a", "b"],
        )
        state.mark_phase_started("a")
        state.mark_phase_completed("a")

        engine = WorkflowRippleEngine()
        phase_result = PhaseResult(success=True)
        transition = engine.determine_transition(
            state, phase_result=phase_result
        )

        assert not transition.re_enter_current
        assert transition.next_phase == "b"
