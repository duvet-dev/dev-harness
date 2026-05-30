"""CLI-to-CommandBus command factories and dispatch helper — V7 §12 Wave 8.

Translates Click CLI argument patterns into ``Command`` instances for the
CommandBus. Provides factory functions that accept human-friendly argument
naming and produce the correct ``command_type`` and ``data`` fields.

Usage::

    from harness.cli.commands import (
        dispatch_cli_command,
    )

    result = dispatch_cli_command(cmd)
    if result.success:
        click.echo(result.message)
    else:
        click.echo(f"Error: {result.error}", err=True)

R30 (§6 DDD Layering): CLI is a thin translator — no business logic here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.command.setup import create_bus
from harness.command.types import Command, CommandResult


# ── Factory Functions (non-migrated) ─────────────────────────────────


def next_command(slug: str) -> Command:
    """Create a ``Next`` command for the CommandBus."""
    return Command(slug=slug, command_type="next")


def create_wave_command(slug: str, title: str = "New Wave") -> Command:
    """Create a ``CreateWave`` command for the CommandBus."""
    return Command(slug=slug, command_type="create_wave", data={"title": title})


def execute_step_command(slug: str, step_spec: str = "") -> Command:
    """Create an ``ExecuteStep`` command for the CommandBus."""
    return Command(slug=slug, command_type="execute_step", data={"step": step_spec})


def query_status_command(slug: str) -> Command:
    """Create a ``QueryStatus`` command for the CommandBus."""
    return Command(slug=slug, command_type="query_status")


def query_whats_next_command(slug: str) -> Command:
    """Create a ``QueryWhatsNext`` command for the CommandBus."""
    return Command(slug=slug, command_type="query_whats_next")


def finish_engagement_command(
    slug: str,
    root: str | Path,
    re_assess: bool = False,
) -> Command:
    """Create a ``FinishEngagement`` command for the CommandBus.

    Args:
        slug: The engagement slug.
        root: Project root directory path.
        re_assess: Whether to run post-engagement observer analysis.

    Returns:
        A Command with ``command_type="finish_engagement"``.
    """
    return Command(
        slug=slug,
        command_type="finish_engagement",
        data={"root": str(root), "re_assess": re_assess},
    )


def review_engagement_command(
    slug: str,
    decision: str,
    root: str | Path | None = None,
    feedback_items: list[dict] | None = None,
    notes: str = "",
) -> Command:
    """Create a ``ReviewEngagement`` command for the CommandBus.

    Args:
        slug: The engagement slug.
        decision: Review decision — "approved", "rejected", or
            "request_changes".
        root: Project root directory (default: cwd).
        feedback_items: Optional structured feedback items.
        notes: Optional review notes.

    Returns:
        A Command with ``command_type="review_engagement"``.
    """
    data: dict[str, Any] = {
        "decision": decision,
        "root": str(root or Path.cwd()),
    }
    if feedback_items:
        data["feedback_items"] = feedback_items
    if notes:
        data["notes"] = notes
    return Command(
        slug=slug,
        command_type="review_engagement",
        data=data,
    )


# ── Wave F: RunWave / Session / Chat ────────────────────────────────


def run_wave_command(
    slug: str,
    wave_id: str,
    no_test: bool = False,
    backend: str | None = None,
) -> Command:
    """Create a ``RunWave`` command for the CommandBus.

    Args:
        slug: The engagement slug.
        wave_id: The wave ID to run.
        no_test: Skip automated test execution.
        backend: Optional agent backend name.

    Returns:
        A Command with ``command_type="run_wave"``.
    """
    return Command(
        slug=slug,
        command_type="run_wave",
        data={"wave_id": wave_id, "no_test": no_test, "backend": backend},
    )


def session_command(
    slug: str,
    phase: str = "requirements",
    session_type: str | None = None,
    context_tier: int = 2,
    get_well: bool = False,
) -> Command:
    """Create a ``Session`` command for the CommandBus.

    Args:
        slug: The engagement slug.
        phase: Starting phase name.
        session_type: Session type (greenfield, brownfield, refactoring).
        context_tier: Context load tier (1-3).
        get_well: Get-well remediation mode.

    Returns:
        A Command with ``command_type="session"``.
    """
    return Command(
        slug=slug,
        command_type="session",
        data={
            "phase": phase,
            "session_type": session_type,
            "context_tier": context_tier,
            "get_well": get_well,
        },
    )


def chat_command(
    slug: str,
    prompt: str | None = None,
    phase: str = "design",
    context_tier: int = 2,
) -> Command:
    """Create a ``Chat`` command for the CommandBus.

    Args:
        slug: The engagement slug.
        prompt: Optional one-shot prompt text.
        phase: Phase context.
        context_tier: Context load tier (1-3).

    Returns:
        A Command with ``command_type="chat"``.
    """
    return Command(
        slug=slug,
        command_type="chat",
        data={"prompt": prompt, "phase": phase, "context_tier": context_tier},
    )


# ── Wave G: Summary / Inspect / Assess ──────────────────────────────


def summary_command(
    deep: bool = False,
    assess_flag: bool = False,
    engagement: str | None = None,
    json_flag: bool = False,
    reconcile: bool = False,
) -> Command:
    """Create a ``Summary`` command for the CommandBus."""
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
    """Create an ``Inspect`` command for the CommandBus."""
    return Command(slug="", command_type="inspect", data={"root": root})


def assess_command(root: str = ".", deep_flag: bool = True) -> Command:
    """Create an ``Assess`` command for the CommandBus."""
    return Command(
        slug="",
        command_type="assess",
        data={"root": root, "deep_flag": deep_flag},
    )


# ── Wave H: Batch + Lower Priority ─────────────────────────────────


def create_waves_from_assessment_command(
    focus: str = "high-risk",
    limit: int = 0,
    slug: str = "",
    refactoring: bool = False,
) -> Command:
    """Create a ``CreateWavesFromAssessment`` command."""
    return Command(
        slug=slug,
        command_type="create_waves_from_assessment",
        data={"focus": focus, "limit": limit, "refactoring": refactoring},
    )


def create_wave_from_finding_command(
    finding_id: str,
    slug: str = "",
) -> Command:
    """Create a ``CreateWaveFromFinding`` command."""
    return Command(
        slug=slug,
        command_type="create_wave_from_finding",
        data={"finding_id": finding_id},
    )


def list_waves_command(slug: str = "") -> Command:
    """Create a ``ListWaves`` command."""
    return Command(slug=slug, command_type="list_waves")


def wave_status_command(slug: str = "") -> Command:
    """Create a ``WaveStatus`` command."""
    return Command(slug=slug, command_type="wave_status")


def generate_docs_command(root: str = ".") -> Command:
    """Create a ``GenerateDocs`` command."""
    return Command(slug="", command_type="generate_docs", data={"root": root})


def annotate_changelog_command(
    slug: str,
    wave: str,
    text: str,
) -> Command:
    """Create an ``AnnotateChangelog`` command."""
    return Command(
        slug=slug,
        command_type="annotate_changelog",
        data={"wave": wave, "text": text},
    )


# ── Wave I: Thin Wrappers ───────────────────────────────────────────


def rename_engagement_command(
    old_slug: str,
    new_slug: str,
    branch_strategy: str = "keep",
    dry_run: bool = False,
) -> Command:
    """Create a ``RenameEngagement`` command."""
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
    """Create a ``SetBranch`` command."""
    return Command(
        slug=slug,
        command_type="set_branch",
        data={"branch": branch},
    )


def fix_engagement_command(slug: str, fix_type: str = "metadata") -> Command:
    """Create a ``FixEngagement`` command."""
    return Command(
        slug=slug,
        command_type="fix_engagement",
        data={"fix_type": fix_type},
    )


def refresh_agents_command(
    project_dir: str | None = None,
    force: bool = False,
) -> Command:
    """Create a ``RefreshAgents`` command."""
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
    """Create a ``SetGovernance`` command."""
    return Command(
        slug=slug,
        command_type="set_governance",
        data={"level": level},
    )


def agent_list_command() -> Command:
    """Create an ``AgentList`` command."""
    return Command(slug="", command_type="agent_list")


def fleet_list_command() -> Command:
    """Create a ``FleetList`` command."""
    return Command(slug="", command_type="fleet_list")


def consult_command(question: str = "") -> Command:
    """Create a ``Consult`` command."""
    return Command(
        slug="",
        command_type="consult",
        data={"question": question},
    )


# ── Dispatch Helper ────────────────────────────────────────────────────


def dispatch_cli_command(command: Command) -> CommandResult:
    """Dispatch a command through the CommandBus from a CLI context.

    Creates a fresh ``CommandBus`` via ``create_bus()`` with all registered
    handlers (both legacy and typed), and dispatches the command.

    Args:
        command: The Command to dispatch.

    Returns:
        A CommandResult from the registered handler.

    Raises:
        harness.errors.UnknownCommandError: If no handler is registered.
    """
    bus = create_bus()
    return bus.dispatch(command)
