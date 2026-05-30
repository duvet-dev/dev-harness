"""Typed commands for simple engagement operations.

Covers: rename_engagement, set_branch, fix_engagement, refresh_agents,
set_governance.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness.command.types import TypedCommand


@dataclass(frozen=True)
class RenameEngagementCommand(TypedCommand):
    """Rename an existing engagement."""

    slug: str = ""
    new_slug: str = ""
    branch_strategy: str = "keep"
    dry_run: bool = False


@dataclass(frozen=True)
class SetBranchCommand(TypedCommand):
    """Set the branch for an engagement."""

    slug: str = ""
    branch: str = ""


@dataclass(frozen=True)
class FixEngagementCommand(TypedCommand):
    """Fix engagement metadata and state issues."""

    slug: str = ""
    fix_type: str = "metadata"


@dataclass(frozen=True)
class RefreshAgentsCommand(TypedCommand):
    """Refresh agent profiles."""

    slug: str = ""
    project_dir: str | None = None
    force: bool = False


@dataclass(frozen=True)
class SetGovernanceCommand(TypedCommand):
    """Set governance level."""

    slug: str = ""
    level: str = "standard"


@dataclass(frozen=True)
class AgentListCommand(TypedCommand):
    """List all registered agent roles."""

    slug: str = ""


@dataclass(frozen=True)
class FleetListCommand(TypedCommand):
    """List all registered teams."""

    slug: str = ""


@dataclass(frozen=True)
class ConsultCommand(TypedCommand):
    """Route a consultation question to matching teams."""

    slug: str = ""
    question: str = ""
    team_filter: str | None = None
    mode: str = "advisory"


__all__ = [
    "RenameEngagementCommand",
    "SetBranchCommand",
    "FixEngagementCommand",
    "RefreshAgentsCommand",
    "SetGovernanceCommand",
    "AgentListCommand",
    "FleetListCommand",
    "ConsultCommand",
]
