"""Typed results for simple engagement operations.

Covers: rename_engagement, set_branch, fix_engagement, refresh_agents,
set_governance, agent_list, team_list, consult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.command.types import TypedResult


@dataclass(frozen=True)
class RenameEngagementResult(TypedResult):
    """Result of renaming an engagement."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    changes_made: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False
    error: str = ""


@dataclass(frozen=True)
class SetBranchResult(TypedResult):
    """Result of setting a branch."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    old_branch: str = ""
    new_branch: str = ""
    error: str = ""


@dataclass(frozen=True)
class FixEngagementResult(TypedResult):
    """Result of fixing an engagement."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    slug: str = ""
    messages: list[str] = field(default_factory=list)
    error: str = ""


@dataclass(frozen=True)
class RefreshAgentsResult(TypedResult):
    """Result of refreshing agent profiles."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)
    error: str = ""


@dataclass(frozen=True)
class SetGovernanceResult(TypedResult):
    """Result of setting governance level."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    level: str = ""
    scope: str = ""
    error: str = ""


@dataclass(frozen=True)
class AgentListResult(TypedResult):
    """Result of listing agents."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    agents: list[dict[str, Any]] = field(default_factory=list)
    count: int = 0
    error: str = ""


@dataclass(frozen=True)
class TeamListResult(TypedResult):
    """Result of listing teams."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    teams: list[dict[str, Any]] = field(default_factory=list)
    count: int = 0
    error: str = ""


@dataclass(frozen=True)
class ConsultResult(TypedResult):
    """Result of consultation."""

    success: bool = True
    message: str = ""
    error_code: str | None = None
    status: str = ""
    capability: str = ""
    team_name: str = ""
    mode: str = ""
    response: str = ""
    error: str = ""


__all__ = [
    "RenameEngagementResult",
    "SetBranchResult",
    "FixEngagementResult",
    "RefreshAgentsResult",
    "SetGovernanceResult",
    "AgentListResult",
    "TeamListResult",
    "ConsultResult",
]
