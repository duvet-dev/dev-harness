"""Tests for harness.refactor.loop."""

import pytest
import time

from harness.refactor.loop import (
    PHASE_PROMPTS,
    REFACTOR_PHASE_LABELS,
    REFACTOR_PHASE_ORDER,
    RefactorPhase,
    RefactorSessionConfig,
    RefactorSessionLoop,
    RefactorSessionResult,
    RefactorSessionState,
    validate_transition,
)


class TestRefactorPhase:
    def test_values(self):
        assert RefactorPhase.INTENT_DISCOVERY.value == "intent-discovery"
        assert RefactorPhase.SUMMARY.value == "summary"

    def test_str_representation(self):
        assert str(RefactorPhase.VERIFICATION) == "verification"


class TestValidateTransition:
    def test_valid_forward_transition(self):
        assert validate_transition(RefactorPhase.INTENT_DISCOVERY, RefactorPhase.ARCHITECTURE_PROPOSAL) is True

    def test_invalid_skip(self):
        assert validate_transition(RefactorPhase.INTENT_DISCOVERY, RefactorPhase.SUMMARY) is False

    def test_verification_loops_back(self):
        assert validate_transition(RefactorPhase.VERIFICATION, RefactorPhase.INTENT_DISCOVERY) is True

    def test_summary_is_terminal(self):
        assert validate_transition(RefactorPhase.SUMMARY, RefactorPhase.INTENT_DISCOVERY) is False
        assert validate_transition(RefactorPhase.SUMMARY, RefactorPhase.VERIFICATION) is False


class TestRefactorSessionConfig:
    def test_defaults(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        assert config.context_tier == 2
        assert config.max_verification_loops == 3
        assert config.auto_confirm_boundaries is False


class TestRefactorSessionState:
    def test_initial_state(self):
        state = RefactorSessionState()
        assert state.current_phase == RefactorPhase.INTENT_DISCOVERY
        assert state.completed_phases == set()
        assert state.artifacts == {}
        assert state.elapsed_seconds == 0.0

    def test_mark_completed(self):
        state = RefactorSessionState()
        state.mark_completed(RefactorPhase.ARCHITECTURE_PROPOSAL)
        assert RefactorPhase.ARCHITECTURE_PROPOSAL in state.completed_phases

    def test_record_artifact(self):
        state = RefactorSessionState()
        state.record_artifact(RefactorPhase.INTENT_DISCOVERY, "analysis")
        assert state.artifacts["intent-discovery"] == "analysis"

    def test_elapsed_seconds(self):
        state = RefactorSessionState(start_time=time.time() - 5)
        assert state.elapsed_seconds >= 4.0


class TestRefactorSessionResult:
    def test_defaults(self):
        result = RefactorSessionResult()
        assert result.success is False
        assert result.boundary_test_count == 0
        assert result.verification_passed is False

    def test_properties(self):
        result = RefactorSessionResult(
            success=True,
            completed_phases=["intent-discovery"],
            boundary_test_count=5,
            loop_count=1,
        )
        assert result.success is True
        assert len(result.completed_phases) == 1


class TestRefactorSessionLoop:
    def test_initial_phase(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        assert loop.current_phase == RefactorPhase.INTENT_DISCOVERY

    def test_get_phase_prompt(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        prompt = loop.get_phase_prompt(RefactorPhase.INTENT_DISCOVERY)
        assert "INTENT DISCOVERY" in prompt

    def test_get_phase_prompt_current(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        prompt = loop.get_phase_prompt()
        assert loop.current_phase.value.replace('-', ' ').upper() in prompt

    def test_get_phase_prompt_fallback(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        # Unknown phase should get fallback
        assert "INTENT DISCOVERY" in loop.get_phase_prompt(RefactorPhase.INTENT_DISCOVERY)

    def test_get_next_phase_returns_next(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        next_phase = loop.get_next_phase()
        assert next_phase == RefactorPhase.ARCHITECTURE_PROPOSAL

    def test_get_next_phase_returns_none_at_end(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        loop.state.current_phase = RefactorPhase.SUMMARY
        assert loop.get_next_phase() is None

    def test_can_advance(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        assert loop.can_advance() is True

    def test_can_advance_at_end(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        loop.state.current_phase = RefactorPhase.SUMMARY
        assert loop.can_advance() is False

    def test_advance_moves_forward(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        new_phase = loop.advance()
        assert new_phase == RefactorPhase.ARCHITECTURE_PROPOSAL
        assert RefactorPhase.INTENT_DISCOVERY in loop.state.completed_phases
        assert loop.current_phase == RefactorPhase.ARCHITECTURE_PROPOSAL

    def test_advance_from_terminal(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        loop.state.current_phase = RefactorPhase.SUMMARY
        assert loop.advance() is None

    def test_loop_back_to_intent(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        loop.state.current_phase = RefactorPhase.VERIFICATION
        result = loop.loop_back_to_intent()
        assert result is True
        assert loop.current_phase == RefactorPhase.INTENT_DISCOVERY
        assert loop.state.verification_loop_count == 1

    def test_loop_back_only_from_verification(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        result = loop.loop_back_to_intent()  # current is INTENT_DISCOVERY
        assert result is False

    def test_loop_back_respects_max(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test", max_verification_loops=2)
        loop = RefactorSessionLoop(config)
        loop.state.current_phase = RefactorPhase.VERIFICATION
        loop.loop_back_to_intent()
        loop.loop_back_to_intent()
        result = loop.loop_back_to_intent()
        assert result is False

    def test_record_and_get_artifact(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        loop.record_artifact("some content")
        assert loop.get_artifact(RefactorPhase.INTENT_DISCOVERY) == "some content"

    def test_get_artifact_empty(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        assert loop.get_artifact(RefactorPhase.INTENT_DISCOVERY) == ""

    def test_build_result(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        result = loop.build_result(success=True, boundary_test_count=3)
        assert result.success is True
        assert result.boundary_test_count == 3

    def test_phases_remaining(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        loop.state.current_phase = RefactorPhase.WAVE_EXECUTION
        remaining = loop.phases_remaining()
        assert RefactorPhase.INTENT_DISCOVERY in remaining
        assert RefactorPhase.SUMMARY in remaining

    def test_phase_progress(self):
        config = RefactorSessionConfig(root=__file__, engagement_slug="test")
        loop = RefactorSessionLoop(config)
        progress = loop.phase_progress()
        assert "Refactoring session" in progress
        assert "INTENT_DISCOVERY" in progress or "intent-discovery" in progress


class TestPhasePrompts:
    def test_all_phases_have_prompts(self):
        for phase in RefactorPhase:
            assert phase in PHASE_PROMPTS, f"Missing prompt for {phase}"

    def test_prompts_are_strings(self):
        for prompt in PHASE_PROMPTS.values():
            assert isinstance(prompt, str)
            assert len(prompt) > 50
