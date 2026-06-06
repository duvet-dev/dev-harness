"""Tests for harness.session.commands — pure command routing and handlers.

Every command handler is a pure function that takes state and returns
a ``CommandResult``. No IO, no terminal output — pure logic.
"""

from __future__ import annotations

import pytest

from harness.session.commands import (
    CommandResult,
    route_chat_command,
    route_session_command,
)


class TestRouteChatCommand:
    """Tests for route_chat_command() — chat-loop command dispatch."""

    def make_state(self, **overrides) -> dict:
        state = {
            "root": "/tmp/test",
            "provider": {"name": "deepseek", "api_key": "sk-xxx"},
            "model": "deepseek-v4-pro",
            "engagement_slug": "test-eng",
            "last_response": "Some assistant output\n## File: main.py\nprint('hi')\n",
            "client_messages": [{"role": "system", "content": "be helpful"}],
            "system_prompt": "be helpful",
        }
        state.update(overrides)
        return state

    def test_exit(self):
        result = route_chat_command("exit", self.make_state())
        assert result.exit_loop is True

    def test_quit(self):
        result = route_chat_command("quit", self.make_state())
        assert result.exit_loop is True

    def test_help(self):
        result = route_chat_command("help", self.make_state())
        assert result.set_in_session is False

    def test_save(self):
        result = route_chat_command("save", self.make_state())
        assert result.save_transcript is True

    def test_write_with_content(self):
        result = route_chat_command("write", self.make_state())
        assert result.capture_artifact == "Some assistant output\n## File: main.py\nprint('hi')\n"

    def test_write_no_content(self):
        state = self.make_state(last_response=None)
        result = route_chat_command("write", state)
        assert result.capture_artifact is None
        assert any("No assistant response" in l for l in result.display_lines)

    def test_apply_with_content(self):
        result = route_chat_command("apply", self.make_state())
        assert result.auto_apply is not None
        assert "Some assistant output" in result.auto_apply

    def test_apply_no_content(self):
        state = self.make_state(last_response=None)
        result = route_chat_command("apply", state)
        assert result.auto_apply is None
        assert any("No assistant response" in l for l in result.display_lines)

    def test_phase_switch_found(self):
        result = route_chat_command("phase design", self.make_state())
        assert result.switch_to_phase_with_history == "design"
        assert "Switched to phase" in result.display_lines[0]

    def test_phase_switch_not_found(self):
        result = route_chat_command("phase nonexistent", self.make_state())
        assert result.switch_to_phase_with_history is None
        assert any("Unknown phase" in l for l in result.display_lines)

    def test_models(self):
        result = route_chat_command("models", self.make_state())
        assert "__list_providers__" in result.display_lines

    def test_model_switch(self):
        result = route_chat_command("model claude", self.make_state())
        assert result.new_provider is not None
        assert result.new_provider["target_name"] == "claude"

    def test_model_switch_with_alias(self):
        result = route_chat_command("model deepseek deepseek-v4-pro", self.make_state())
        assert result.new_provider["target_name"] == "deepseek"
        assert result.new_provider["target_alias"] == "deepseek-v4-pro"

    def test_new_conversation(self):
        result = route_chat_command("new", self.make_state())
        assert result.reset_conversation is True

    def test_consult_empty_question(self):
        result = route_chat_command("consult ", self.make_state())
        assert any("Usage" in l for l in result.display_lines)

    def test_version(self):
        result = route_chat_command("version", self.make_state())
        assert any("dev-harness" in l for l in result.display_lines)
        assert any("build:" in l for l in result.display_lines)

    def test_version(self):
        result = route_session_command("version", self.make_state())
        assert any("dev-harness" in l for l in result.display_lines)
        assert any("build:" in l for l in result.display_lines)

    def test_unknown_command(self):
        result = route_chat_command("unknown", self.make_state())
        assert any("Unknown command" in l for l in result.display_lines)


class TestRouteSessionCommand:
    """Tests for route_session_command() — session-loop command dispatch."""

    def make_state(self, **overrides) -> dict:
        from harness.session.phase_source import get_phases
        phases_list = get_phases()
        state = {
            "root": "/tmp/test",
            "phase_def": {"name": "implementation", "title": "Implementation"},
            "blocking_consults": {},
            "last_response": "## File: src/main.py\nprint('hello')\n",
            "transcript": None,
            "provider": {"name": "deepseek", "api_key": "sk-xxx"},
            "model": "deepseek-v4-pro",
            "engagement_slug": "test-eng",
            "jump_counts": {},
            "phase_artifacts": [],
            "phase_name": "implementation",
            "current_phase_index": 3,
            "_phase_list": phases_list,
        }
        state.update(overrides)
        return state

    def test_help(self):
        result = route_session_command("help", self.make_state())
        assert result.set_in_session is True

    def test_next_advances(self):
        result = route_session_command("next", self.make_state())
        assert result.advance_phase is True
        assert result.approved is False
        assert result.save_transcript is True
        assert result.capture_artifact is not None

    def test_approve(self):
        result = route_session_command("approve", self.make_state())
        assert result.advance_phase is True
        assert result.approved is True

    def test_next_blocked_by_consult(self):
        from harness.agents.consultation import ConsultationResult
        blocking = ConsultationResult(
            question="test", team_name="arch", status="pending",
            mode="blocking",
        )
        state = self.make_state(
            blocking_consults={"implementation": [blocking]}
        )
        result = route_session_command("next", state)
        assert result.advance_phase is False
        assert any("Cannot advance" in l for l in result.display_lines)

    def test_save(self):
        result = route_session_command("save", self.make_state())
        assert result.save_transcript is True

    def test_models(self):
        result = route_session_command("models", self.make_state())
        assert "__list_providers__" in result.display_lines

    def test_model_switch(self):
        result = route_session_command("model claude", self.make_state())
        assert result.new_provider["target_name"] == "claude"

    def test_write_deprecated(self):
        """Test /write now returns a deprecation message."""
        result = route_session_command("write", self.make_state())
        assert "/write is deprecated" in "\n".join(result.display_lines)

    def test_apply_deprecated(self):
        """Test /apply now returns a deprecation message."""
        result = route_session_command("apply", self.make_state())
        assert "/apply is deprecated" in "\n".join(result.display_lines)

    def test_changes_with_reason(self):
        result = route_session_command("changes needs more tests", self.make_state())
        assert "Changes requested" in result.display_lines[0]
        assert "needs more tests" in result.display_lines[1]
        assert result.switch_to_phase is not None
        assert result.phase_jump_allowed is True

    def test_changes_no_reason(self):
        result = route_session_command("changes", self.make_state())
        assert "Changes requested" in result.display_lines[0]
        assert result.phase_jump_allowed is True

    def test_navigate_found(self):
        result = route_session_command("navigate design", self.make_state())
        assert result.switch_to_phase == "design"
        assert result.phase_jump_allowed is True

    def test_navigate_not_found(self):
        result = route_session_command("navigate nonexistent", self.make_state())
        assert result.switch_to_phase is None
        assert any("Unknown phase" in l for l in result.display_lines)

    def test_navigate_blocked_by_limit(self):
        from harness.session.helpers import MAX_PHASE_JUMPS_PER_PHASE
        state = self.make_state(
            jump_counts={"build→design": MAX_PHASE_JUMPS_PER_PHASE}
        )
        result = route_session_command("navigate design", state)
        assert result.phase_jump_allowed is False
        assert any("blocked" in l for l in result.display_lines)

    def test_feedback_valid(self):
        result = route_session_command("feedback discover missing spec", self.make_state())
        assert result.switch_to_phase == "discover"
        assert result.phase_jump_allowed is True

    def test_feedback_missing_target(self):
        result = route_session_command("feedback", self.make_state())
        assert any("Usage" in l for l in result.display_lines)

    def test_feedback_unknown_target(self):
        result = route_session_command("feedback nowhere", self.make_state())
        assert any("Unknown" in l for l in result.display_lines)

    def test_resume(self):
        result = route_session_command("resume", self.make_state())
        assert "__resume_checkpoint__" in result.display_lines

    def test_resume_force(self):
        result = route_session_command("resume-force", self.make_state())
        assert "__resume_checkpoint__" in result.display_lines

    def test_exit(self):
        result = route_session_command("exit", self.make_state())
        assert result.exit_loop is True

    def test_quit(self):
        result = route_session_command("quit", self.make_state())
        assert result.exit_loop is True

    def test_phase_diagram(self):
        result = route_session_command("phase", self.make_state())
        assert "__show_phase_diagram__" in result.display_lines

    def test_phase_switch(self):
        result = route_session_command("phase design", self.make_state())
        assert result.switch_to_phase_with_history == "design"

    def test_phase_switch_custom_list(self):
        """Test /phase works with custom phase lists (e.g. get-well)."""
        custom_phases = [
            {"name": "assessment-triage", "title": "Assessment Triage"},
            {"name": "architecture-design", "title": "Architecture Design"},
        ]
        state = self.make_state(_phase_list=custom_phases)
        result = route_session_command("phase architecture-design", state)
        assert result.switch_to_phase_with_history == "architecture-design"

    def test_phase_switch_fallback_to_global(self):
        """Test /phase falls back to phase list for standard names."""
        custom_phases = [
            {"name": "assessment-triage", "title": "Assessment Triage"},
        ]
        state = self.make_state(_phase_list=custom_phases)
        result = route_session_command("phase design", state)
        assert result.switch_to_phase_with_history == "design"

    def test_consult_resolve_valid(self):
        from harness.agents.consultation import ConsultationResult
        consult = ConsultationResult(
            question="test", team_name="arch", status="pending"
        )
        state = self.make_state(
            blocking_consults={"implementation": [consult]}
        )
        result = route_session_command(
            "consult-resolve 0 done", state
        )
        assert result.consult_resolved is True

    def test_consult_resolve_invalid_index(self):
        result = route_session_command(
            "consult-resolve 99 done", self.make_state()
        )
        assert result.consult_resolved is False
        assert any("Invalid consult" in l for l in result.display_lines)

    def test_consult_resolve_missing_index(self):
        result = route_session_command("consult-resolve", self.make_state())
        assert any("Usage" in l for l in result.display_lines)

    def test_version(self):
        result = route_chat_command("version", self.make_state())
        assert any("dev-harness" in l for l in result.display_lines)
        assert any("build:" in l for l in result.display_lines)

    def test_version(self):
        result = route_session_command("version", self.make_state())
        assert any("dev-harness" in l for l in result.display_lines)
        assert any("build:" in l for l in result.display_lines)

    def test_unknown_command(self):
        result = route_session_command("unknown", self.make_state())
        assert any("Unknown command" in l for l in result.display_lines)
