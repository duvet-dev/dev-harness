"""CLI-to-CommandBus command factories and dispatch helper.

Provides factory functions that accept human-friendly argument
naming and produce the correct ``command_type`` and ``data`` fields.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.command.setup import create_bus
from harness.command.types import Command, CommandResult


# ── Command Factory Functions (remaining, for dispatch_cli_command) ──


def summary_command(
    deep: bool = False,
    assess_flag: bool = False,
    engagement: str | None = None,
    json_flag: bool = False,
    reconcile: bool = False,
) -> Command:
    """Create a Summary command."""
    return Command(
        slug=engagement or "",
        command_type="summary",
        data={
            "deep": deep,
            "assess_flag": assess_flag,
            "json_flag": json_flag,
            "reconcile": reconcile,
        },
    )


def inspect_command(root: str = ".") -> Command:
    """Create an Inspect command."""
    return Command(slug="", command_type="inspect", data={"root": root})


def assess_command(root: str = ".", deep_flag: bool = True) -> Command:
    """Create an Assess command."""
    return Command(
        slug="",
        command_type="assess",
        data={"root": root, "deep_flag": deep_flag},
    )


def create_waves_from_assessment_command(
    focus: str = "high-risk",
    limit: int = 0,
    slug: str = "",
    refactoring: bool = False,
) -> Command:
    """Create a CreateWavesFromAssessment command."""
    return Command(
        slug=slug,
        command_type="create_waves_from_assessment",
        data={"focus": focus, "limit": limit, "refactoring": refactoring},
    )


def create_wave_from_finding_command(
    finding_id: str,
    slug: str = "",
) -> Command:
    """Create a CreateWaveFromFinding command."""
    return Command(
        slug=slug,
        command_type="create_wave_from_finding",
        data={"finding_id": finding_id},
    )


def list_waves_command(slug: str = "") -> Command:
    """Create a ListWaves command."""
    return Command(slug=slug, command_type="list_waves")


def wave_status_command(slug: str = "") -> Command:
    """Create a WaveStatus command."""
    return Command(slug=slug, command_type="wave_status")


def generate_docs_command(root: str = ".") -> Command:
    """Create a GenerateDocs command."""
    return Command(slug="", command_type="generate_docs", data={"root": root})


def annotate_changelog_command(
    slug: str,
    wave: str,
    text: str,
) -> Command:
    """Create an AnnotateChangelog command."""
    return Command(
        slug=slug,
        command_type="annotate_changelog",
        data={"wave": wave, "text": text},
    )


def rename_engagement_command(
    old_slug: str,
    new_slug: str,
    branch_strategy: str = "keep",
    dry_run: bool = False,
) -> Command:
    """Create a RenameEngagement command."""
    return Command(
        slug=old_slug,
        command_type="rename_engagement",
        data={
            "new_slug": new_slug,
            "branch_strategy": branch_strategy,
            "dry_run": dry_run,
        },
    )


def set_branch_command(slug: str, branch: str) -> Command:
    """Create a SetBranch command."""
    return Command(
        slug=slug,
        command_type="set_branch",
        data={"branch": branch},
    )


def fix_engagement_command(slug: str, fix_type: str = "metadata") -> Command:
    """Create a FixEngagement command."""
    return Command(
        slug=slug,
        command_type="fix_engagement",
        data={"fix_type": fix_type},
    )


def refresh_agents_command(
    project_dir: str | None = None,
    force: bool = False,
) -> Command:
    """Create a RefreshAgents command."""
    return Command(
        slug="",
        command_type="refresh_agents",
        data={
            "project_dir": project_dir,
            "force": force,
        },
    )


def set_governance_command(
    level: str = "standard",
    slug: str = "",
) -> Command:
    """Create a SetGovernance command."""
    return Command(
        slug=slug,
        command_type="set_governance",
        data={"level": level},
    )


def agent_list_command() -> Command:
    """Create an AgentList command."""
    return Command(slug="", command_type="agent_list")


def fleet_list_command() -> Command:
    """Create a FleetList command."""
    return Command(slug="", command_type="fleet_list")


def consult_command(question: str = "") -> Command:
    """Create a Consult command."""
    return Command(
        slug="",
        command_type="consult",
        data={"question": question},
    )


# ── Dispatch Helper ────────────────────────────────────────────────────


def dispatch_cli_command(command: Command) -> CommandResult:
    """Dispatch a command through the CommandBus from a CLI context.

    Creates a fresh ``CommandBus`` via ``create_bus()`` with all
    typed handlers registered, and dispatches the command.
    """
    bus = create_bus()
    return bus.dispatch(command)
