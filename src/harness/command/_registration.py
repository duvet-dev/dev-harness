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
