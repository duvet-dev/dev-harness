"""Tests for harness.agents.fleet — fleet data model.

Tests Fleet, FleetGuidelines, InclusionRules, ConsultationCapability,
GovernanceLevel, and builtin_fleets.
"""

from __future__ import annotations

import pytest

from harness.agents.fleet import (
    ConsultationCapability,
    Fleet,
    FleetGuidelines,
    GovernanceLevel,
    InclusionRules,
    builtin_fleets,
)


class TestGovernanceLevel:
    """Tests for GovernanceLevel enum."""

    def test_values(self):
        assert GovernanceLevel.EXPLORATION.value == "exploration"
        assert GovernanceLevel.STANDARD.value == "standard"
        assert GovernanceLevel.STRICT.value == "strict"

    def test_from_string(self):
        assert GovernanceLevel("exploration") == GovernanceLevel.EXPLORATION
        assert GovernanceLevel("strict") == GovernanceLevel.STRICT


class TestConsultationCapability:
    """Tests for ConsultationCapability."""

    def test_defaults(self):
        cap = ConsultationCapability(
            name="test-cap",
            match_phrases=["help"],
        )
        assert cap.name == "test-cap"
        assert cap.mode == "advisory"
        assert cap.scope == "cross-phase"
        assert cap.description == ""

    def test_matches_case_insensitive(self):
        cap = ConsultationCapability(
            name="arch-review",
            match_phrases=["architecture review", "arch review"],
        )
        assert cap.matches("Can I get an Architecture Review?") is True
        assert cap.matches("need arch review please") is True
        assert cap.matches("unrelated question") is False

    def test_matches_substring(self):
        cap = ConsultationCapability(
            name="test",
            match_phrases=["quality assessment"],
        )
        assert cap.matches("What is the quality assessment of this code?") is True

    def test_custom_values(self):
        cap = ConsultationCapability(
            name="blocking-review",
            match_phrases=["must review"],
            description="Blocking review",
            mode="blocking",
            scope="phase:design",
            question="Is this design acceptable?",
        )
        assert cap.mode == "blocking"
        assert cap.scope == "phase:design"
        assert cap.question == "Is this design acceptable?"


class TestFleetGuidelines:
    """Tests for FleetGuidelines."""

    def test_defaults(self):
        g = FleetGuidelines()
        assert g.input_protocol["format"] == "markdown"
        assert "context" in g.input_protocol["required_sections"]
        assert g.output_protocol["format"] == "markdown"
        assert "proposal" in g.output_protocol["required_sections"]
        assert g.cooperation == []
        assert g.phases == []


class TestFleet:
    """Tests for Fleet dataclass."""

    def test_minimal(self):
        fleet = Fleet(name="test-fleet", lead_role="test-agent")
        assert fleet.name == "test-fleet"
        assert fleet.lead_role == "test-agent"
        assert fleet.builtin is True
        assert fleet.consultations == []

    def test_matches_agent_lead(self):
        fleet = Fleet(name="arch", lead_role="architect")
        assert fleet.matches_agent("architect") is True

    def test_matches_agent_sub(self):
        fleet = Fleet(name="arch", lead_role="lead",
                       sub_agents=["sub-a", "sub-b"])
        assert fleet.matches_agent("sub-a") is True
        assert fleet.matches_agent("sub-b") is True
        assert fleet.matches_agent("sub-c") is False

    def test_matches_agent_names(self):
        fleet = Fleet(name="coding", lead_role="coding-agent",
                       agent_names=["coder"])
        assert fleet.matches_agent("coder") is True

    def test_has_consultation_for(self):
        fleet = Fleet(
            name="test",
            lead_role="test-agent",
            consultations=[
                ConsultationCapability(
                    name="q1",
                    match_phrases=["architecture"],
                ),
            ],
        )
        assert fleet.has_consultation_for("architecture review") is True
        assert fleet.has_consultation_for("coding question") is False

    def test_get_active_agents_exploration(self):
        fleet = Fleet(
            name="test",
            lead_role="lead",
            sub_agents=["sub1", "sub2"],
        )
        active = fleet.get_active_agents(
            governance=GovernanceLevel.EXPLORATION,
        )
        assert active == ["lead"]

    def test_get_active_agents_standard(self):
        fleet = Fleet(
            name="test",
            lead_role="lead",
            sub_agents=["sub1", "sub2"],
        )
        active = fleet.get_active_agents(
            governance=GovernanceLevel.STANDARD,
        )
        assert "lead" in active
        assert "sub1" in active
        assert "sub2" in active

    def test_get_active_agents_strict(self):
        fleet = Fleet(
            name="test",
            lead_role="lead",
            sub_agents=["sub1", "sub2"],
        )
        active = fleet.get_active_agents(
            governance=GovernanceLevel.STRICT,
        )
        assert "lead" in active
        assert "sub1" in active
        assert "sub2" in active

    def test_get_active_agents_with_project_type_filter(self):
        fleet = Fleet(
            name="test",
            lead_role="lead",
            sub_agents=["sub1", "sub2", "sub3"],
            inclusion_rules=InclusionRules(
                project_type={
                    "ddd-backend": ["sub1", "sub2"],
                    "cli-tool": ["sub3"],
                },
            ),
        )
        active = fleet.get_active_agents(
            governance=GovernanceLevel.STANDARD,
            project_type="ddd-backend",
        )
        assert "sub1" in active
        assert "sub2" in active
        assert "sub3" not in active

    def test_get_active_agents_with_governance_minimum(self):
        fleet = Fleet(
            name="test",
            lead_role="lead",
            sub_agents=["sub-strict"],
            inclusion_rules=InclusionRules(
                governance_minimum={
                    "sub-strict": GovernanceLevel.STRICT,
                },
            ),
        )
        # STANDARD level is below STRICT minimum
        active = fleet.get_active_agents(
            governance=GovernanceLevel.STANDARD,
        )
        assert "sub-strict" not in active

        # STRICT level meets minimum
        active = fleet.get_active_agents(
            governance=GovernanceLevel.STRICT,
        )
        assert "sub-strict" in active


class TestBuiltinFleets:
    """Tests for builtin_fleets()."""

    def test_returns_seven_fleets(self):
        fleets = builtin_fleets()
        assert len(fleets) == 7

    def test_fleet_names(self):
        fleets = builtin_fleets()
        names = {f.name for f in fleets}
        expected = {"discovery", "planning", "architecture", "coding",
                     "testing", "review", "validation"}
        assert names == expected

    def test_all_fleets_have_lead_role(self):
        for fleet in builtin_fleets():
            assert fleet.lead_role, f"Fleet {fleet.name} missing lead_role"

    def test_all_fleets_have_consultations(self):
        for fleet in builtin_fleets():
            assert len(fleet.consultations) >= 1, (
                f"Fleet {fleet.name} has no consultations"
            )

    def test_builtin_flag(self):
        for fleet in builtin_fleets():
            assert fleet.builtin is True

    def test_architecture_fleet_lead(self):
        fleets = {f.name: f for f in builtin_fleets()}
        assert fleets["architecture"].lead_role == "architect"

    def test_coding_fleet_lead(self):
        fleets = {f.name: f for f in builtin_fleets()}
        assert fleets["coding"].lead_role == "coding-agent"

    def test_review_fleet_lead(self):
        fleets = {f.name: f for f in builtin_fleets()}
        assert fleets["review"].lead_role == "critical-analyser"
