"""Tests for built-in team defaults (team/defaults.py).

V7 §10.1 — 7 built-in teams.
"""

from __future__ import annotations

from harness.team.defaults import get_builtin_teams


class TestBuiltinTeams:
    """Tests for the 7 built-in AgentTeam definitions."""

    def test_returns_exactly_seven_teams(self) -> None:
        """get_builtin_teams returns exactly 7 teams."""
        teams = get_builtin_teams()
        assert len(teams) == 7

    def test_all_team_names_unique(self) -> None:
        """All built-in teams have unique names."""
        teams = get_builtin_teams()
        names = [t.name for t in teams]
        assert len(names) == len(set(names))

    def test_architecture_team_has_expected_agents(self) -> None:
        """Architecture team has the 4 expected agents."""
        teams = {t.name: t for t in get_builtin_teams()}
        arch = teams["architecture"]
        assert arch.description == "Architecture design and review"
        assert arch.agents == [
            "architect",
            "architecture-critic",
            "code-critic",
            "security-critic",
        ]
        assert arch.guidelines is not None
        assert "SOLID" in arch.guidelines
        assert "safety-first" in arch.guidelines

    def test_coding_team_has_expected_agents(self) -> None:
        """Coding team has the 2 expected agents."""
        teams = {t.name: t for t in get_builtin_teams()}
        coding = teams["coding"]
        assert coding.description == "Code implementation and testing"
        assert coding.agents == ["coding-agent", "testing-agent"]
        assert coding.guidelines is not None
        assert "80% test coverage" in coding.guidelines

    def test_testing_team_has_expected_agents(self) -> None:
        """Testing team has the 2 expected agents and guidelines."""
        teams = {t.name: t for t in get_builtin_teams()}
        testing = teams["testing"]
        assert testing.description == "Software testing and quality assurance"
        assert testing.agents == ["testing-agent", "test-coverage-analyser"]
        assert testing.guidelines is not None
        assert "Flag any regressions" in testing.guidelines

    def test_review_team_has_no_guidelines(self) -> None:
        """Review team has no guidelines (None)."""
        teams = {t.name: t for t in get_builtin_teams()}
        review = teams["review"]
        assert review.agents == [
            "design-reviewer",
            "critical-analyser",
            "security-auditor",
        ]
        assert review.guidelines is None

    def test_planning_team_exists(self) -> None:
        """Planning team exists with expected agents."""
        teams = {t.name: t for t in get_builtin_teams()}
        plan = teams["planning"]
        assert plan.description == "Planning and task breakdown"
        assert plan.agents == ["planning-agent", "dependency-analyser"]

    def test_discovery_team_exists(self) -> None:
        """Discovery team exists with expected agents."""
        teams = {t.name: t for t in get_builtin_teams()}
        disco = teams["discovery"]
        assert disco.description == "Research and discovery"
        assert disco.agents == ["discovery-agent", "research-agent"]

    def test_validation_team_exists(self) -> None:
        """Validation team exists with expected agents."""
        teams = {t.name: t for t in get_builtin_teams()}
        validate = teams["validation"]
        assert validate.description == (
            "Validation and requirements conformance"
        )
        assert validate.agents == [
            "validation-agent",
            "example-scenarios-agent",
        ]

    def test_all_teams_have_names(self) -> None:
        """Every team has a non-empty name."""
        for team in get_builtin_teams():
            assert team.name, f"Team missing name: {team}"

    def test_all_teams_have_descriptions(self) -> None:
        """Every team has a description."""
        for team in get_builtin_teams():
            assert team.description, f"Team '{team.name}' missing description"

    def test_all_teams_have_agents(self) -> None:
        """Every team has at least one agent."""
        for team in get_builtin_teams():
            assert len(team.agents) > 0, (
                f"Team '{team.name}' has no agents"
            )
