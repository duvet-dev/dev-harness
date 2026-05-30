"""Tests for harness.agents.__init__ — package exports.

Verifies that the expected symbols are exported from the agents package.
"""

from __future__ import annotations

import harness.agents as agents


class TestAgentsExports:
    """Tests for the agents package __init__ exports."""

    def test_agent_registry_exports(self):
        assert hasattr(agents, "AGENTS")
        assert hasattr(agents, "AgentRole")
        assert hasattr(agents, "AgentSpec")
        assert hasattr(agents, "get_agent")
        assert hasattr(agents, "get_agents_by_tag")
        assert hasattr(agents, "list_agent_names")
        assert hasattr(agents, "list_agent_roles")
        assert hasattr(agents, "registry_summary")

    def test_cycle_exports(self):
        assert hasattr(agents, "CycleConvergence")
        assert hasattr(agents, "CycleResult")
        assert hasattr(agents, "CycleRunner")
        assert hasattr(agents, "CycleRunnerDefinition")
        assert hasattr(agents, "CycleStep")
        assert hasattr(agents, "CycleStepResult")
        assert hasattr(agents, "design_cycle_definition")
        assert hasattr(agents, "discovery_cycle_definition")
        assert hasattr(agents, "get_cycle_definition")
        assert hasattr(agents, "is_phase_jump_status")
        assert hasattr(agents, "list_cycle_definitions")
        assert hasattr(agents, "parse_phase_jump_target")
        assert hasattr(agents, "planning_cycle_definition")
        assert hasattr(agents, "review_cycle_definition")
        assert hasattr(agents, "testing_cycle_definition")
        assert hasattr(agents, "wave_cycle_definition")

    def test_fleet_exports(self):
        """Legacy Fleet exports replaced by AgentTeam/TeamRegistry."""
        # Fleet/FleetGuidelines/GovernanceLevel/InclusionRules/builtin_fleets
        # removed — replaced by AgentTeam + TeamRegistry + GovernanceLevel in governance.py
        assert hasattr(agents, "AgentTeam")
        assert hasattr(agents, "TeamRegistry")

    def test_consultation_exports(self):
        assert hasattr(agents, "ConsultationOrchestrator")
        assert hasattr(agents, "ConsultationResult")

    def test_fleet_registry_exports(self):
        """FleetRegistry removed — use TeamRegistry instead."""
        assert hasattr(agents, "TeamRegistry")

    def test_detector_exports(self):
        assert hasattr(agents, "LanguageDetector")
        assert hasattr(agents, "LanguagePatterns")

    def test_sync_agent_export(self):
        assert hasattr(agents, "SYNC_AGENT")

    def test_cycle_definitions_exist(self):
        """All cycle definition functions work."""
        d = agents.design_cycle_definition()
        assert d.name == "arch-loop"

    def test_builtin_fleets_exported(self):
        """builtin_fleets() removed — use get_builtin_teams() from team.defaults."""
        from harness.team.defaults import get_builtin_teams
        teams = get_builtin_teams()
        assert len(teams) == 7

    def test_all_names_match_dunder_all(self):
        """All names in __all__ are actually exported."""
        for name in agents.__all__:
            assert hasattr(agents, name), f"Name '{name}' in __all__ but not exported"
