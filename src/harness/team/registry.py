"""TeamRegistry — V7 §10.3.

Manages AgentTeam definitions with built-in < project < user merge
semantics (D38). Supports team lookup by name, agent list resolution,
and listing all registered teams.

Teams from later sources fully replace teams with the same name
from earlier sources — no partial merge. See V7 §10.2 for the full
merge semantics specification.
"""

from __future__ import annotations

from harness.errors import EmptyTeamError, UnknownTeamError
from harness.team.defaults import get_builtin_teams
from harness.team.model import AgentTeam


class TeamRegistry:
    """Registry of AgentTeam definitions with layered merge semantics.

    Merge order: built-in < project < user. Later sources fully replace
    earlier sources for teams with the same name (full replacement, not
    partial merge). Teams with unique names from any source are preserved.

    Args:
        builtin: Built-in team definitions (lowest priority).
        project: Project-level overrides (medium priority).
            Loaded from ``.harness/teams.yaml``.
        user: User-level overrides (highest priority).
            Loaded from ``~/.harness/teams.yaml``.

    Usage::

        registry = TeamRegistry(
            builtin=get_builtin_teams(),
            project=project_teams,
            user=user_teams,
        )
        team = registry.resolve("architecture")
        agents = registry.resolve_agents("coding")
        names = registry.list_teams()
    """

    def __init__(
        self,
        builtin: list[AgentTeam] | None = None,
        project: list[AgentTeam] | None = None,
        user: list[AgentTeam] | None = None,
    ) -> None:
        self._teams: dict[str, AgentTeam] = {}
        self._merge(builtin or [])
        self._merge(project or [])
        self._merge(user or [])

    def _merge(self, sources: list[AgentTeam]) -> None:
        """Merge a list of teams into the registry.

        Full replacement by name: if a team with the same name already
        exists, it is completely replaced (agents and guidelines both).
        Teams with unique names are simply added.

        Args:
            sources: List of AgentTeam definitions to merge.
        """
        for team in sources:
            self._teams[team.name] = team

    def resolve(self, name: str) -> AgentTeam:
        """Return the full AgentTeam definition by name.

        Args:
            name: The team name to look up.

        Returns:
            The matching AgentTeam.

        Raises:
            UnknownTeamError: If no team with the given name is
                registered.
        """
        if name not in self._teams:
            raise UnknownTeamError(f"Team '{name}' not found in registry")
        return self._teams[name]

    def resolve_agents(self, name: str) -> list[str]:
        """Return the agent list for a team by name.

        Convenience method equivalent to ``resolve(name).agents``.

        Args:
            name: The team name to look up.

        Returns:
            List of agent string names in the team.

        Raises:
            UnknownTeamError: If no team with the given name is
                registered.
            EmptyTeamError: If the team exists but has no agents.
        """
        team = self.resolve(name)
        if not team.agents:
            raise EmptyTeamError(
                f"Team '{name}' has no agents defined"
            )
        return team.agents

    def list_teams(self) -> list[str]:
        """Return all registered team names.

        Returns:
            Sorted list of team names.
        """
        return sorted(self._teams.keys())

    @property
    def count(self) -> int:
        """Return the number of registered teams."""
        return len(self._teams)
