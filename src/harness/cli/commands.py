"""CLI-to-CommandBus command factories and dispatch helper.

Provides factory functions that accept human-friendly argument
naming and produce the correct typed command instances.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.command.setup import create_bus
from harness.command.types import CommandResult, TypedCommand


# ── Command Factory Functions ──────────────────────────────────────────


def summary_command(
    deep: bool = False,
    assess_flag: bool = False,
    engagement: str | None = None,
    json_flag: bool = False,
    reconcile: bool = False,
) -> TypedCommand:
    """Create a Summary command."""
    from harness.command.commands.analysis import SummaryCommand
    return SummaryCommand(
        slug=engagement or "",
        deep=deep,
        assess_flag=assess_flag,
        json_flag=json_flag,
        reconcile=reconcile,
    )


def inspect_command(root: str = ".") -> TypedCommand:
    """Create an Inspect command."""
    from harness.command.commands.analysis import InspectCommand
    return InspectCommand(slug="", root=root)


def assess_command(root: str = ".", deep_flag: bool = True) -> TypedCommand:
    """Create an Assess command."""
    from harness.command.commands.analysis import AssessCommand
    return AssessCommand(slug="", root=root, deep_flag=deep_flag)


def create_waves_from_assessment_command(
    focus: str = "high-risk",
    limit: int = 0,
    slug: str = "",
    refactoring: bool = False,
) -> TypedCommand:
    """Create a CreateWavesFromAssessment command."""
    from harness.command.commands.batch import CreateWavesFromAssessmentCommand
    return CreateWavesFromAssessmentCommand(
        slug=slug,
        focus=focus,
        limit=limit,
        refactoring=refactoring,
    )


def create_wave_from_finding_command(
    finding_id: str,
    slug: str = "",
) -> TypedCommand:
    """Create a CreateWaveFromFinding command."""
    from harness.command.commands.batch import CreateWaveFromFindingCommand
    return CreateWaveFromFindingCommand(slug=slug, finding_id=finding_id)


def list_waves_command(slug: str = "") -> TypedCommand:
    """Create a ListWaves command."""
    from harness.command.commands.batch import ListWavesCommand
    return ListWavesCommand(slug=slug)


def wave_status_command(slug: str = "") -> TypedCommand:
    """Create a WaveStatus command."""
    from harness.command.commands.batch import WaveStatusCommand
    return WaveStatusCommand(slug=slug)


def generate_docs_command(root: str = ".") -> TypedCommand:
    """Create a GenerateDocs command."""
    from harness.command.commands.batch import GenerateDocsCommand
    return GenerateDocsCommand(slug="", root=root)


def annotate_changelog_command(
    slug: str,
    wave: str,
    text: str,
) -> TypedCommand:
    """Create an AnnotateChangelog command."""
    from harness.command.commands.batch import AnnotateChangelogCommand
    return AnnotateChangelogCommand(slug=slug, wave=wave, text=text)


def rename_engagement_command(
    old_slug: str,
    new_slug: str,
    branch_strategy: str = "keep",
    dry_run: bool = False,
) -> TypedCommand:
    """Create a RenameEngagement command."""
    from harness.command.commands.mgmt import RenameEngagementCommand
    return RenameEngagementCommand(
        slug=old_slug,
        new_slug=new_slug,
        branch_strategy=branch_strategy,
        dry_run=dry_run,
    )


def set_branch_command(slug: str, branch: str) -> TypedCommand:
    """Create a SetBranch command."""
    from harness.command.commands.mgmt import SetBranchCommand
    return SetBranchCommand(slug=slug, branch=branch)


def fix_engagement_command(slug: str, fix_type: str = "metadata") -> TypedCommand:
    """Create a FixEngagement command."""
    from harness.command.commands.mgmt import FixEngagementCommand
    return FixEngagementCommand(slug=slug, fix_type=fix_type)


def refresh_agents_command(
    project_dir: str | None = None,
    force: bool = False,
) -> TypedCommand:
    """Create a RefreshAgents command."""
    from harness.command.commands.mgmt import RefreshAgentsCommand
    return RefreshAgentsCommand(slug="", project_dir=project_dir, force=force)


def set_governance_command(
    level: str = "standard",
    slug: str = "",
) -> TypedCommand:
    """Create a SetGovernance command."""
    from harness.command.commands.mgmt import SetGovernanceCommand
    return SetGovernanceCommand(slug=slug, level=level)


def agent_list_command() -> TypedCommand:
    """Create an AgentList command."""
    from harness.command.commands.mgmt import AgentListCommand
    return AgentListCommand(slug="")


def team_list_command() -> TypedCommand:
    """Create a TeamList command."""
    from harness.command.commands.mgmt import TeamListCommand
    return TeamListCommand(slug="")


def consult_command(question: str = "") -> TypedCommand:
    """Create a Consult command."""
    from harness.command.commands.mgmt import ConsultCommand
    return ConsultCommand(slug="", question=question)


# ── Dispatch Helper ────────────────────────────────────────────────────


def dispatch_cli_command(command: TypedCommand) -> CommandResult:
    """Dispatch a command through the CommandBus from a CLI context.

    Creates a fresh ``CommandBus`` via ``create_bus()`` with all
    typed handlers registered, and dispatches the command.
    """
    bus = create_bus()
    return bus.dispatch(command)
