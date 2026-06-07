"""@register decorator — single source of truth for REPL/CLI commands.

Provides the ``@register`` decorator, a module-level ``REGISTRY`` dict,
and builder functions that derive the REPL command map and bus handler
registrations from it.

Usage::

    @click.command()
    @register("engagement create", cmd_cls=CreateEngagementCommand,
              handler=CreateEngagementHandler(), arg_parser=_parse_args)
    def engagement_create(**kwargs):
        ...

See design at .openclaw/engagements/005-command-registry/design/design.md
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from harness.command.bus import CommandBus
from harness.command.types import TypedCommand, TypedHandler


# ── Data model ──────────────────────────────────────────────────────────────


@dataclass
class Registration:
    """Metadata for one registered command.

    Attributes:
        name: The command name string (e.g. "engagement create").
        cmd_cls: The TypedCommand class for REPL dispatch (None for click_only).
        handler: The TypedHandler instance for bus registration (None for click_only).
        arg_parser: Callable that parses raw args into constructor kwargs.
        click_only: If True, command exists only in Click CLI, not in REPL.
    """

    name: str
    cmd_cls: Optional[type[TypedCommand]] = None
    handler: Optional[TypedHandler] = None
    arg_parser: Optional[Callable[[list[str]], dict[str, Any]]] = None
    click_only: bool = False


# ── Registry ────────────────────────────────────────────────────────────────


REGISTRY: dict[str, Registration] = {}
"""Module-level registry populated by @register decorators at import time."""


# ── Decorator ───────────────────────────────────────────────────────────────


def register(
    name: str,
    *,
    cmd_cls: Optional[type[TypedCommand]] = None,
    handler: Optional[TypedHandler] = None,
    arg_parser: Optional[Callable[[list[str]], dict[str, Any]]] = None,
    click_only: bool = False,
) -> Callable:
    """Decorator that registers a command in the central REGISTRY.

    Args:
        name: Command name string (e.g. "engagement create").
        cmd_cls: The TypedCommand class used for REPL dispatch.
        handler: The TypedHandler instance used for bus registration.
        arg_parser: Callable that parses ``list[str]`` into constructor kwargs.
        click_only: If True, the command exists only in Click CLI, not the REPL.

    Returns:
        The decorated function unchanged (Click owns the function).

    Raises:
        ValueError: If ``click_only=False`` and ``cmd_cls`` or ``handler`` is missing.
        ValueError: If ``name`` is already registered.
    """
    if name in REGISTRY:
        raise ValueError(f"Duplicate command registration: {name!r}")

    if not click_only:
        if cmd_cls is None:
            raise ValueError(
                f"@register({name!r}) requires cmd_cls when click_only=False"
            )
        if handler is None:
            raise ValueError(
                f"@register({name!r}) requires handler when click_only=False"
            )

    REGISTRY[name] = Registration(
        name=name,
        cmd_cls=cmd_cls,
        handler=handler,
        arg_parser=arg_parser,
        click_only=click_only,
    )

    def decorator(func: Callable) -> Callable:
        return func

    return decorator


# ── Arg parser functions ──────────────────────────────────────────────────


def _no_args(_args: list[str]) -> dict[str, Any]:
    return {}


def _single_arg(args: list[str]) -> dict[str, str]:
    return {"slug": args[0]} if args else {}


def _engagement_create_args(args: list[str]) -> dict[str, Any]:
    """Parse args for /engagement create <name> [--slug ...] [...]."""
    return {"slug": args[0], "workflow_name": "standard", "session_type": "greenfield", "mode": "auto"} if args else {}


def _session_args(args: list[str]) -> dict[str, Any]:
    """Parse args for /session [--get-well] [phase]."""
    cleaned = [a for a in args if a != "--get-well"]
    phase = cleaned[0] if cleaned else "requirements"
    get_well = "--get-well" in args
    if get_well and phase == "requirements":
        phase = "assessment-triage"
    return {"slug": "", "phase": phase, "get_well": get_well}


def _chat_args(args: list[str]) -> dict[str, Any]:
    return {"slug": "", "prompt": args[0] if args else None}


def _phase_args(args: list[str]) -> dict[str, Any]:
    """Parse /phase [engagement_id] [--list|--navigate|...]."""
    # Extract engagement_id (first positional) and action from flags
    engagement_id = ""
    remaining = list(args)
    if remaining and not remaining[0].startswith("--"):
        engagement_id = remaining.pop(0)
    return {"slug": engagement_id, "action": "list", "root": str(Path.cwd())}


def _work_args(args: list[str]) -> dict[str, Any]:
    """Parse /work <description> [--mode ...]."""
    import re
    description = " ".join(a for a in args if not a.startswith("--"))
    slug = re.sub(r"[^a-z0-9-]", "-", description.lower().strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return {"slug": slug, "workflow_name": "standard", "session_type": "greenfield", "mode": "auto"}


def _init_args(args: list[str]) -> dict[str, Any]:
    """Parse /init [project_dir] [--template ...] [--no-git] [--force]."""
    remaining = [a for a in args if not a.startswith("--")]
    project_dir = remaining[0] if remaining else None
    return {"project_dir": project_dir, "root": Path.cwd()}


def _run_wave_args(args: list[str]) -> dict[str, Any]:
    """Parse /wave run <wave_id> [--no-test] [--backend ...] [--engagement ...]."""
    wave_id = ""
    no_test = False
    backend = None
    i = 0
    while i < len(args):
        if args[i] == "--no-test":
            no_test = True
        elif args[i] == "--backend" and i + 1 < len(args):
            backend = args[i + 1]
            i += 1
        elif args[i] == "--engagement" and i + 1 < len(args):
            pass  # slug handled by caller
            i += 1
        elif not args[i].startswith("--"):
            wave_id = args[i]
        i += 1
    return {"slug": "", "wave_id": wave_id, "no_test": no_test, "backend": backend}


def _finish_args(args: list[str]) -> dict[str, Any]:
    return {"slug": "", "root": str(Path.cwd()), "re_assess": "--re-assess" in args}


def _review_args(args: list[str]) -> dict[str, Any]:
    slug = ""
    decision = "approved"
    i = 0
    while i < len(args):
        if args[i] == "--approve":
            decision = "approved"
        elif args[i] == "--reject":
            decision = "rejected"
        elif args[i] == "--request-changes":
            decision = "request_changes"
        elif not args[i].startswith("--"):
            slug = args[i]
        i += 1
    return {"slug": slug, "decision": decision, "root": str(Path.cwd())}


def _summary_args(args: list[str]) -> dict[str, Any]:
    return {
        "deep": "--deep" in args,
        "assess_flag": "--assess" in args,
        "json_flag": "--json" in args,
        "reconcile": "--reconcile" in args,
        "engagement": None,
    }


def _inspect_args(args: list[str]) -> dict[str, Any]:
    return {"root": args[0] if args else "."}


def _assess_args(args: list[str]) -> dict[str, Any]:
    return {"root": args[0] if args else ".", "deep_flag": True}


def _create_wave_from_assessment_args(args: list[str]) -> dict[str, Any]:
    focus = "high-risk"
    limit = 0
    i = 0
    while i < len(args):
        if args[i] == "--focus" and i + 1 < len(args):
            focus = args[i + 1]
            i += 1
        elif args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 1
        elif args[i] == "--refactoring":
            pass
        i += 1
    return {"focus": focus, "limit": limit, "slug": "", "refactoring": "--refactoring" in args}


def _create_wave_from_finding_args(args: list[str]) -> dict[str, Any]:
    finding_id = args[0] if args else ""
    return {"finding_id": finding_id, "slug": ""}


# ── Builder functions ───────────────────────────────────────────────────────


def build_repl_command_map() -> dict[str, tuple[type[TypedCommand], Callable]]:
    """Build a REPL command map from REGISTRY.

    Returns a ``dict[str, tuple[cmd_cls, arg_parser]]`` matching the structure
    of the current ``COMMAND_TYPES`` dict. Excludes ``click_only=True`` entries.

    Returns:
        The command map, or an empty dict if REGISTRY is empty.
    """
    if not REGISTRY:
        warnings.warn(
            "REGISTRY is empty. Ensure main.py (or cli modules) is imported first.",
            stacklevel=2,
        )
        return {}

    return {
        reg.name: (reg.cmd_cls, reg.arg_parser)
        for reg in REGISTRY.values()
        if not reg.click_only
    }


def register_bus_handlers(bus: CommandBus) -> None:
    """Register all non-click_only handlers from REGISTRY onto a CommandBus.

    Skips duplicate registrations: if two names share a TypedCommand class,
    only one ``bus.register_type()`` call is made.

    Args:
        bus: A CommandBus instance to register handlers onto.
    """
    if not REGISTRY:
        warnings.warn(
            "REGISTRY is empty. Ensure main.py (or cli modules) is imported first.",
            stacklevel=2,
        )
        return

    seen_types: set[type] = set()
    for reg in REGISTRY.values():
        if reg.click_only:
            continue
        if reg.cmd_cls is None or reg.handler is None:
            continue
        if reg.cmd_cls in seen_types:
            continue
        bus.register_type(reg.handler, reg.cmd_cls)
        seen_types.add(reg.cmd_cls)
