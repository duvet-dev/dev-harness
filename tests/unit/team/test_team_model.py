"""Tests for AgentTeam dataclass (team/model.py).

V7 §10 — AgentTeam System.
"""

from __future__ import annotations

from harness.team.model import AgentTeam


class TestAgentTeam:
    """Tests for the AgentTeam dataclass."""

    def test_create_with_all_fields(self) -> None:
        """AgentTeam can be created with all fields populated."""
        team = AgentTeam(
            name="test-team",
            description="A test team",
            agents=["agent-a", "agent-b"],
            guidelines="Be excellent to each other",
        )
        assert team.name == "test-team"
        assert team.description == "A test team"
        assert team.agents == ["agent-a", "agent-b"]
        assert team.guidelines == "Be excellent to each other"

    def test_create_minimal(self) -> None:
        """AgentTeam can be created with just a name."""
        team = AgentTeam(name="minimal-team")
        assert team.name == "minimal-team"
        assert team.description is None
        assert team.agents == []
        assert team.guidelines is None

    def test_create_with_none_guidelines(self) -> None:
        """AgentTeam allows None for guidelines."""
        team = AgentTeam(
            name="no-guidelines",
            agents=["agent-x"],
            guidelines=None,
        )
        assert team.guidelines is None

    def test_create_with_empty_agents(self) -> None:
        """AgentTeam allows an empty agents list. Validation of non-empty
        agents is the responsibility of TeamRegistry.resolve_agents."""
        team = AgentTeam(name="empty")
        assert team.agents == []

    def test_repr(self) -> None:
        """AgentTeam has a readable repr."""
        team = AgentTeam(name="foo", description="bar")
        r = repr(team)
        assert "AgentTeam" in r
        assert "name='foo'" in r

    def test_equality(self) -> None:
        """Two AgentTeams with the same fields are equal (dataclass)."""
        t1 = AgentTeam(name="a", agents=["x"])
        t2 = AgentTeam(name="a", agents=["x"])
        assert t1 == t2

    def test_inequality(self) -> None:
        """Two AgentTeams with different names are not equal."""
        t1 = AgentTeam(name="a")
        t2 = AgentTeam(name="b")
        assert t1 != t2
