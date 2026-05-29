"""AgentTeam dataclass — V7 §10.

An AgentTeam is a logical grouping of agents identified by string name.
Teams carry shared guidelines that are injected at step dispatch time,
not agent creation time (D36). See V7 §10 for full specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentTeam:
    """A logical grouping of agents with optional shared guidelines.

    Teams are referenced by name from Step dataclasses (``team:`` field)
    and auto-expand to the list of agents at dispatch time.

    Attributes:
        name: Unique team identifier.
        description: Human-readable description of the team's purpose.
        agents: List of agent string names in this team.
        guidelines: Optional shared guidelines injected at step dispatch
            (D36). Stored here, injected in Wave 2 (StepDispatcher).
    """

    name: str
    description: str | None = None
    agents: list[str] = field(default_factory=list)
    guidelines: str | None = None
