"""AgentTeam system — logical groupings of agents.

Built-in, project, and user teams with full-replacement merge semantics.
See V7 §10 for the design specification.
"""

from harness.team.model import AgentTeam
from harness.team.defaults import get_builtin_teams
from harness.team.registry import TeamRegistry

__all__ = [
    "AgentTeam",
    "TeamRegistry",
    "get_builtin_teams",
]
