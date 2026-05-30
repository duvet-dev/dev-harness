"""CLI-to-CommandBus command factories and dispatch helper — V7 §12 Wave 8.

Translates Click CLI argument patterns into ``Command`` instances for the
CommandBus. Provides factory functions that accept human-friendly argument
naming and produce the correct ``command_type`` and ``data`` fields.

Usage::

    from harness.cli.commands import (
        create_engagement_command,
        dispatch_cli_command,
    )

    cmd = create_engagement_command(slug="my-eng", workflow="standard")
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

from harness.command.bus import CommandBus
from harness.command.handlers import register_all_handlers
from harness.command.registry import CommandRegistry
from harness.command.types import Command, CommandResult


# ── Command Factory Functions ──────────────────────────────────────────


def create_engagement_command(slug: str, **kwargs: object) -> Command:
    """Create a ``CreateEngagement`` command for the CommandBus.

    Args:
        slug: The engagement slug.
        **kwargs: Additional data fields (e.g. workflow, template).

    Returns:
        A Command with ``command_type="create_engagement"``.
    """
    return Command(slug=slug, command_type="create_engagement", data=dict(kwargs))


def enter_phase_command(slug: str, phase: str) -> Command:
    """Create an ``EnterPhase`` command for the CommandBus.

    Args:
        slug: The engagement slug.
        phase: The phase name to enter (e.g. "design", "requirements").

    Returns:
        A Command with ``command_type="enter_phase"``.
    """
    return Command(slug=slug, command_type="enter_phase", data={"phase": phase})


def next_command(slug: str) -> Command:
    """Create a ``Next`` command for the CommandBus.

    Args:
        slug: The engagement slug.

    Returns:
        A Command with ``command_type="next"``.
    """
    return Command(slug=slug, command_type="next")


def abort_engagement_command(slug: str, mode: str = "graceful") -> Command:
    """Create an ``AbortEngagement`` command for the CommandBus.

    Args:
        slug: The engagement slug.
        mode: Abort mode — ``"graceful"`` (default) or ``"hard"``.

    Returns:
        A Command with ``command_type="abort_engagement"``.
    """
    return Command(slug=slug, command_type="abort_engagement", data={"mode": mode})


def query_status_command(slug: str) -> Command:
    """Create a ``QueryStatus`` command for the CommandBus.

    Args:
        slug: The engagement slug.

    Returns:
        A Command with ``command_type="query_status"``.
    """
    return Command(slug=slug, command_type="query_status")


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
    from pathlib import Path
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


def query_whats_next_command(slug: str) -> Command:
    """Create a ``QueryWhatsNext`` command for the CommandBus.

    Args:
        slug: The engagement slug.

    Returns:
        A Command with ``command_type="query_whats_next"``.
    """
    return Command(slug=slug, command_type="query_whats_next")


def init_project_command(
    project_dir: str | None = None,
    template: str | None = None,
    seed: str | None = None,
    no_git: bool = False,
    force: bool = False,
    root: str | Path | None = None,
) -> Command:
    """Create an ``InitProject`` command for the CommandBus.

    Args:
        project_dir: Subdirectory name (optional).
        template: Template name (optional).
        seed: Context to seed from (optional).
        no_git: Skip git init.
        force: Re-initialise even if already set up.
        root: Project root (default: cwd).

    Returns:
        A Command with ``command_type="init_project"``.
    """
    from pathlib import Path
    data: dict[str, Any] = {
        "root": str(root or Path.cwd()),
        "no_git": no_git,
        "force": force,
    }
    if project_dir is not None:
        data["project_dir"] = project_dir
    if template is not None:
        data["template"] = template
    if seed is not None:
        data["seed"] = seed
    return Command(
        slug="",
        command_type="init_project",
        data=data,
    )


def manage_phase_command(
    slug: str,
    action: str,
    target: str | None = None,
    feedback_reason: str = "",
    force: bool = False,
    root: str | Path | None = None,
) -> Command:
    """Create a ``ManagePhase`` command for the CommandBus.

    Args:
        slug: The engagement slug.
        action: Phase action (list, navigate, feedback, resume, status,
            feedback_list).
        target: Target phase for navigate/feedback.
        feedback_reason: Reason for feedback.
        force: Bypass checkpoint staleness checks.
        root: Project root (default: cwd).

    Returns:
        A Command with ``command_type="manage_phase"``.
    """
    from pathlib import Path
    data: dict[str, Any] = {
        "action": action,
        "root": str(root or Path.cwd()),
        "force": force,
    }
    if target is not None:
        data["target"] = target
    if feedback_reason:
        data["feedback_reason"] = feedback_reason
    return Command(
        slug=slug,
        command_type="manage_phase",
        data=data,
    )


# ── Dispatch Helper ────────────────────────────────────────────────────


def dispatch_cli_command(command: Command) -> CommandResult:
    """Dispatch a command through the CommandBus from a CLI context.

    Creates a fresh ``CommandBus``, registers all delegation-thin handlers,
    and dispatches the command. This is the single entry point for all
    CLI-to-CommandBus interactions.

    Args:
        command: The Command to dispatch.

    Returns:
        A CommandResult from the registered handler.

    Raises:
        harness.errors.UnknownCommandError: If no handler is registered.
    """
    registry = CommandRegistry()
    register_all_handlers(registry)
    bus = CommandBus(registry=registry)
    return bus.dispatch(command)
