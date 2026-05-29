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


def query_whats_next_command(slug: str) -> Command:
    """Create a ``QueryWhatsNext`` command for the CommandBus.

    Args:
        slug: The engagement slug.

    Returns:
        A Command with ``command_type="query_whats_next"``.
    """
    return Command(slug=slug, command_type="query_whats_next")


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
