"""Sync tests for the @register decorator / REGISTRY infrastructure.

These tests ensure the REGISTRY (built from @register decorators) stays in
sync with three downstream consumers:

1. The Click CLI command tree (``cli_main.commands``)
2. The REPL command map (``build_repl_command_map()``)
3. The CommandBus handler registrations (``create_bus()``)

Wave 1 note
-----------
Tests 1 and 4 are **skipped** during Wave 1 because no ``@register``
decorators have been deployed yet — the REGISTRY is empty. These tests will
be enabled in Waves 2–3 as decorators are added to each Click command
function. Once all decorators are in place, these skipped tests become the
safety net that prevents drift between the three registration surfaces.

See design at .openclaw/engagements/005-command-registry/design/design.md
"""

from __future__ import annotations

import pytest

# Commands that intentionally exist only in Click CLI and should never
# have a @register decorator. These are excluded from sync checks.
PURE_CLICK_EXEMPTIONS: set[str] = {
    "shell",
}


# ═══════════════════════════════════════════════════════════════════
# Test 1 — Every CLI command has a REGISTRY entry
# ═══════════════════════════════════════════════════════════════════

def _walk_click_commands() -> list[str]:
    """Return a flat list of all Click CLI command names.

    Walks ``cli_main.commands``, flattening group sub-commands into
    ``"group subcommand"`` format. Top-level commands are returned as-is.
    """
    from harness.cli import main as cli_main

    names: list[str] = []
    for name, cmd in cli_main.commands.items():
        if isinstance(cmd, type(cli_main)):  # click.Group
            for sub_name in cmd.commands:
                names.append(f"{name} {sub_name}")
        else:
            names.append(name)
    return names


class TestCLIRegistrationSync:
    """Verify every CLI command has a corresponding REGISTRY entry."""

    def test_all_cli_commands_registered(self):
        """Every CLI command must have a @register (or be in exemptions)."""
        from harness.command._registration import REGISTRY

        click_names = _walk_click_commands()
        unregistered = [
            name for name in click_names
            if name not in REGISTRY and name not in PURE_CLICK_EXEMPTIONS
        ]
        assert not unregistered, (
            f"CLI command(s) missing @register: {unregistered}"
        )


# ═══════════════════════════════════════════════════════════════════
# Test 2 — No orphaned registrations
# ═══════════════════════════════════════════════════════════════════

class TestNoOrphanedRegistrations:
    """Every REGISTRY entry must have a corresponding Click command."""

    def test_no_orphaned_registrations(self):
        """Every REGISTRY name must exist as a Click CLI command."""
        from harness.command._registration import REGISTRY

        click_names = set(_walk_click_commands())
        orphaned = [
            name for name in REGISTRY
            if name not in click_names
        ]
        assert not orphaned, (
            f"Registration(s) have no matching Click command: {orphaned}"
        )


# ═══════════════════════════════════════════════════════════════════
# Test 3 — REPL map entries are instantiable
# ═══════════════════════════════════════════════════════════════════

class TestReplMapInstantiable:
    """Every entry in build_repl_command_map() can be constructed."""

    def test_repl_map_instantiable(self):
        """Call cls(**parser(sample_args)) for each REPL map entry.

        Sample args should be appropriate for each command type:
        - ``["test-slug"]`` for slug-based commands
        - ``[]`` for commands with no required args
        """
        from harness.command._registration import build_repl_command_map
        from harness.cli import main as _unused  # populate REGISTRY via @register

        command_map = build_repl_command_map()

        # Determine appropriate sample args for each command based on name
        # Some commands need more than one positional arg.
        for name, (cls, parser) in command_map.items():
            # Pick sample args appropriate to the command name
            if name == "enter-phase":
                sample_args = ["test-slug", "requirements"]
            elif name == "engagement rename":
                sample_args = ["test-slug", "new-slug"]
            elif name == "engagement set-branch":
                sample_args = ["test-slug", "main"]
            elif name == "changelog annotate":
                sample_args = ["test-slug", "annotation text"]
            elif name == "team set-governance":
                sample_args = ["standard"]
            elif name == "work":
                sample_args = ["test-task"]
            else:
                sample_args = ["test-slug"]

            kwargs = parser(sample_args) if parser else {}
            try:
                instance = cls(**kwargs)
            except TypeError as exc:
                raise AssertionError(
                    f"Cannot instantiate {cls.__name__} (name={name!r}) "
                    f"with kwargs={kwargs!r}: {exc}"
                ) from exc

            # Verify the instance actually exists
            assert instance is not None, (
                f"Instantiation returned None for {name!r}"
            )


# ═══════════════════════════════════════════════════════════════════
# Test 4 — No stale bus handlers (each has a @register)
# ═══════════════════════════════════════════════════════════════════

class TestBusHandlerSync:
    """Every bus handler must have a matching REGISTRY entry."""

    def test_no_stale_bus_handlers(self):
        """Every handler type registered on the bus must have a @register."""
        from harness.command._registration import REGISTRY
        from harness.command.setup import create_bus

        bus = create_bus()
        handler_types = set(bus._type_handlers.keys())

        # Build the set of command classes that are registered
        registered_types: set[type] = set()
        for reg in REGISTRY.values():
            if not reg.click_only and reg.cmd_cls is not None:
                registered_types.add(reg.cmd_cls)

        stale = handler_types - registered_types
        assert not stale, (
            f"Bus handler(s) without @register: "
            f"{[t.__name__ for t in stale]}"
        )
