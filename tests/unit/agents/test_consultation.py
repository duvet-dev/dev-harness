"""Tests for harness.agents.consultation — consultation orchestrator.

Tests ConsultationResult and ConsultationOrchestrator routing, dispatch,
auto-consults, and available questions using AgentTeam + TeamRegistry.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from harness.agents.consultation import (
    ConsultationCapability,
    ConsultationOrchestrator,
    ConsultationResult,
)
from harness.team.model import AgentTeam
from harness.team.registry import TeamRegistry


def _make_registry() -> TeamRegistry:
    """Create a TeamRegistry with consultation capabilities on teams."""
    return TeamRegistry(builtin=[
        AgentTeam(
            name="architecture",
            consultations=[
                {
                    "name": "arch-review",
                    "match_phrases": ["architecture", "design"],
                    "description": "Review architecture decisions",
                    "mode": "advisory",
                    "scope": "cross-phase",
                    "question": "Is the architecture sound?",
                },
                {
                    "name": "blocking-check",
                    "match_phrases": ["must check", "blocking review"],
                    "description": "Blocking review",
                    "mode": "blocking",
                    "scope": "trigger:design",
                    "question": "Blocking check question",
                },
                {
                    "name": "phase-only",
                    "match_phrases": ["phase-specific"],
                    "description": "Only in this phase",
                    "mode": "advisory",
                    "scope": "phase:implementation",
                    "question": "Phase question",
                },
            ],
        ),
        AgentTeam(
            name="coding",
            consultations=[
                {
                    "name": "code-review-request",
                    "match_phrases": ["code review"],
                    "description": "Review code",
                    "mode": "advisory",
                    "scope": "wave-build",
                    "question": "Review the code.",
                },
            ],
        ),
    ])


@pytest.fixture
def registry():
    return _make_registry()


class TestConsultationResult:
    """Tests for ConsultationResult dataclass."""

    def test_defaults(self):
        result = ConsultationResult()
        assert result.question == ""
        assert result.capability is None
        assert result.status == "unmatched"
        assert result.mode == "advisory"
        assert result.resolution is None

    def test_is_blocking_true(self):
        result = ConsultationResult(mode="blocking", status="matched")
        assert result.is_blocking() is True

    def test_is_blocking_false_advisory(self):
        result = ConsultationResult(mode="advisory", status="matched")
        assert result.is_blocking() is False

    def test_is_blocking_false_resolved(self):
        result = ConsultationResult(mode="blocking", status="resolved")
        assert result.is_blocking() is False

    def test_resolve(self):
        result = ConsultationResult(mode="blocking", status="matched")
        result.resolve(resolution="approved", resolved_by="user")
        assert result.resolution == "approved"
        assert result.resolved_by == "user"
        assert result.status == "resolved"
        assert result.is_blocking() is False

    def test_summary(self):
        result = ConsultationResult(
            question="Test?",
            capability="arch-review",
            team_name="architecture",
            status="matched",
        )
        summary = result.summary
        assert "[matched]" in summary
        assert "architecture" in summary

    def test_summary_with_blocking(self):
        result = ConsultationResult(
            question="Test?",
            capability="check",
            team_name="team",
            mode="blocking",
            status="matched",
        )
        assert "blocking" in result.summary

    def test_summary_with_error(self):
        result = ConsultationResult(
            question="Test?",
            status="unavailable",
            error="API timeout",
        )
        assert "API timeout" in result.summary

    def test_summary_with_resolution(self):
        """Summary shows resolved state when resolution is set (line 177)."""
        result = ConsultationResult(
            mode="blocking", status="resolved", resolution="approved"
        )
        summary = result.summary
        assert "resolved: approved" in summary

    def test_response_lines(self):
        result = ConsultationResult(response="Line 1\nLine 2\nLine 3")
        assert result.response_lines == ["Line 1", "Line 2", "Line 3"]


class TestConsultationCapability:
    """Tests for ConsultationCapability."""

    def test_from_dict(self):
        cap = ConsultationCapability.from_dict({
            "name": "test-cap",
            "match_phrases": ["hello"],
            "description": "Test",
            "mode": "blocking",
            "scope": "trigger:design",
            "question": "Test question?",
        })
        assert cap.name == "test-cap"
        assert cap.match_phrases == ["hello"]
        assert cap.mode == "blocking"
        assert cap.scope == "trigger:design"
        assert cap.question == "Test question?"

    def test_from_dict_minimal(self):
        cap = ConsultationCapability.from_dict({"name": "minimal"})
        assert cap.name == "minimal"
        assert cap.match_phrases == []
        assert cap.mode == "advisory"

    def test_matches(self):
        cap = ConsultationCapability(
            name="test",
            match_phrases=["architecture review"],
        )
        assert cap.matches("Can I get an architecture review?") is True
        assert cap.matches("How is the weather?") is False

    def test_matches_case_insensitive(self):
        cap = ConsultationCapability(
            name="test",
            match_phrases=["ARCHITECTURE"],
        )
        assert cap.matches("architecture review") is True
        assert cap.matches("Architecture review") is True


class TestConsultationOrchestrator:
    """Tests for ConsultationOrchestrator."""

    @pytest.fixture
    def orch(self, registry):
        return ConsultationOrchestrator(registry)

    def test_can_answer_matches(self, orch):
        matches = orch.can_answer("Can I get an architecture review?")
        assert len(matches) >= 1
        cap, team_name = matches[0]
        assert cap.name == "arch-review"
        assert team_name == "architecture"

    def test_can_answer_no_match(self, orch):
        matches = orch.can_answer("What is the weather?")
        assert matches == []

    def test_can_answer_with_team_filter(self, orch):
        matches = orch.can_answer("architecture review", team_filter="architecture")
        assert len(matches) >= 1

    def test_can_answer_with_wrong_team_filter(self, orch):
        matches = orch.can_answer("architecture review", team_filter="coding")
        assert matches == []

    def test_can_answer_any_true(self, orch):
        assert orch.can_answer_any("architecture review") is True

    def test_can_answer_any_false(self, orch):
        assert orch.can_answer_any("unrelated question") is False

    def test_route_success(self, orch):
        result = orch.route("What about the architecture design?")
        assert result.status == "matched"
        assert result.capability == "arch-review"
        assert result.team_name == "architecture"

    def test_route_unmatched(self, orch):
        result = orch.route("How's the weather?")
        assert result.status == "unmatched"
        assert "Available questions" in result.response

    def test_route_with_mode_override(self, orch):
        result = orch.route("architecture review", mode="blocking")
        assert result.mode == "blocking"

    def test_route_with_team_filter(self, orch):
        result = orch.route("architecture review", team_filter="architecture")
        assert result.status == "matched"

    def test_route_with_wrong_team(self, orch):
        result = orch.route("architecture review", team_filter="coding")
        assert result.status == "unmatched"

    def test_dispatch_sequential_all_matched(self, orch):
        results = orch.dispatch_sequential([
            "architecture review",
            "design question",
        ])
        assert len(results) == 2
        assert all(r.status == "matched" for r in results)

    def test_dispatch_sequential_mixed(self, orch):
        results = orch.dispatch_sequential([
            "architecture review",
            "unrelated question",
        ])
        assert results[0].status == "matched"
        assert results[1].status == "unmatched"

    def test_auto_consults_cross_phase(self, orch):
        results = orch.auto_consults("implementation")
        assert any(r.capability == "arch-review" for r in results)

    def test_auto_consults_trigger(self, orch):
        results = orch.auto_consults("design")
        assert any(r.capability == "blocking-check" for r in results)

    def test_auto_consults_trigger_wrong_phase(self, orch):
        results = orch.auto_consults("implementation")
        assert not any(r.capability == "blocking-check" for r in results)

    def test_auto_consults_phase_specific_matches(self, orch):
        results = orch.auto_consults("implementation")
        assert any(r.capability == "phase-only" for r in results)

    def test_auto_consults_phase_specific_wrong(self, orch):
        results = orch.auto_consults("design")
        assert not any(r.capability == "phase-only" for r in results)

    def test_auto_consults_always_advisory(self, orch):
        results = orch.auto_consults("design")
        for r in results:
            assert r.mode == "advisory"

    def test_get_available_questions(self, orch):
        questions = orch.get_available_questions()
        assert len(questions) >= 3
        texts = [q[0] for q in questions]
        assert "Is the architecture sound?" in texts

    def test_get_available_questions_with_filter(self, orch):
        questions = orch.get_available_questions(team_filter="architecture")
        assert len(questions) >= 3

    def test_get_available_questions_wrong_filter(self, orch):
        questions = orch.get_available_questions(team_filter="nonexistent")
        assert questions == []


class TestConsultationOrchestratorInit:
    """Tests for ConsultationOrchestrator construction."""

    def test_init_with_team_registry(self):
        """Should accept a TeamRegistry directly."""
        registry = _make_registry()
        orch = ConsultationOrchestrator(registry)
        assert orch._registry is registry
        assert orch.can_answer_any("architecture") is True

    def test_init_with_empty_registry(self):
        """Should handle empty TeamRegistry gracefully."""
        registry = TeamRegistry()
        orch = ConsultationOrchestrator(registry)
        assert orch.can_answer("anything") == []
        result = orch.route("anything")
        assert result.status == "unmatched"


class TestConsultationCapabilityCtor:
    """Tests for from_dict factory."""

    def test_from_dict_with_capability(self, registry):
        """from_dict should work with a real capability dict."""
        cap = ConsultationCapability.from_dict({
            "name": "test",
            "match_phrases": ["hello"],
        })
        assert cap.name == "test"
        assert cap.match_phrases == ["hello"]

    def test_get_team_capabilities_with_instances(self, registry):
        """_get_team_capabilities handles ConsultationCapability instances (line 235)."""
        from harness.team.model import AgentTeam
        cap = ConsultationCapability(
            name="direct-cap",
            match_phrases=["direct"],
            description="Direct instance",
            mode="blocking",
            scope="cross-phase",
            question="Direct?",
        )
        # Create a registry with just this team (uses ConsultationCapability instances)
        registry2 = TeamRegistry(builtin=[
            AgentTeam(
                name="direct-team",
                consultations=[cap],
            ),
        ])
        orch = ConsultationOrchestrator(registry2)
        assert orch.can_answer_any("direct question") is True
        result = orch.route("direct question")
        assert result.status == "matched"
        assert result.capability == "direct-cap"
