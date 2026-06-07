# Decorator-Based Command Registration Design

**Date:** 2026-06-07
**Status:** Design Proposal
**Author:** Architect (subagent)
**Supersedes:** `command-registry-design.md` — the 1,700-line `CommandDef` registry was over-scoped per Crichton review

---

## 1. Problem

Every REPL-dispatchable command is registered in three places:

| # | Location | Failure if Missing |
|---|----------|--------------------|
| 1 | `main.py` — `@click.command()` | Not discoverable |
| 2 | `repl.py` — `COMMAND_TYPES` dict | "Unknown command" in REPL |
| 3 | `setup.py` — `bus.register_type()` | Runtime `UnknownCommandError` |

**12 of 39 CLI commands fail in the REPL** (missing from #2). Adding a command requires touching all three with no guardrails.

---

## 2. Solution: `@register` Decorator

A single decorator that lives on each existing Click command function. It records metadata at import time — nothing more. No Click param generation, no function transformation, no code generation.

### 2.1 Core Module

```python
# src/harness/command/_registration.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Optional

from harness.command.types import TypedCommand, TypedHandler


@dataclass
class Registration:
    name: str                           # REPL command name, e.g. "engagement status"
    cmd_cls: Optional[type] = None      # TypedCommand, None for Click-only
    handler: Optional[TypedHandler] = None
    arg_parser: Optional[Callable] = None
    click_only: bool = False


REGISTRY: dict[str, Registration] = {}


def register(
    name: str,
    *,
    cmd_cls: Optional[type[TypedCommand]] = None,
    handler: Optional[TypedHandler] = None,
    arg_parser: Optional[Callable[[list[str]], dict[str, Any]]] = None,
    click_only: bool = False,
) -> Callable:
    if not click_only and (cmd_cls is None or handler is None):
        raise ValueError(
            f"@register('{name}'): provide cmd_cls+handler or click_only=True"
        )
    def decorator(fn: Callable) -> Callable:
        if name in REGISTRY:
            raise ValueError(f"Duplicate registration: '{name}'")
        REGISTRY[name] = Registration(
            name=name, cmd_cls=cmd_cls, handler=handler,
            arg_parser=arg_parser, click_only=click_only,
        )
        return fn  # unchanged — Click still owns the fn
    return decorator
```

Only ~35 lines. Imports nothing concrete — `TypedCommand` and `TypedHandler` are abstract types.

### 2.2 Usage

**Bus-dispatchable command:**
```python
@engagement_group.command()
@click.argument("slug")
@register(name="engagement status", cmd_cls=EngagementStatusCommand,
          handler=EngagementStatusHandler(), arg_parser=_single_arg)
def engagement_status(slug):
    ...
```

**Click-only command (intentionally no TypedCommand):**
```python
@engagement_group.command(name="list")
@register(name="engagement list", click_only=True)
def list_engagements():
    ...
```

The existing Click decorators (`@command()`, `@argument()`, `@option()`) are untouched. The `@register` decorator is purely additive — it records metadata and returns the function unchanged.

### 2.3 Semantics

| Rule | Behaviour |
|------|-----------|
| Duplicate names | Raises `ValueError` |
| Missing handler | Raises `ValueError` at import unless `click_only=True` |
| Returns fn unchanged | Other decorators still control the function |
| Import order | `main.py` imported first → all `@register` decorators fire before REPL or bus modules are loaded |

---

## 3. Registry Module Structure

```
src/harness/command/
  _registration.py   # @register decorator + REGISTRY + builder functions
```

**Import chain:**
```
main.py ──imports──> _registration.py    (decorator + REGISTRY dict)
                         │
                         │ (REGISTRY populated by decorators
                         │  as each command module is imported)
                         ▼
repl.py ──imports──> _registration.py    (reads REGISTRY → builds REPL map)
setup.py ──imports──> _registration.py   (reads REGISTRY → registers handlers)
```

No circular imports: `_registration.py` imports only `typing` + `TypedCommand`/`TypedHandler` (abstract bases). Concrete command/handler classes are imported by `main.py`, which imports `_registration.py` first.

---

## 4. Replacing `COMMAND_TYPES`

### Builder function in `_registration.py`:
```python
def build_repl_command_map() -> dict[str, tuple[type, Callable]]:
    """Same structure as current repl.py:COMMAND_TYPES."""
    result = {}
    for name, reg in REGISTRY.items():
        if reg.cmd_cls is not None and reg.arg_parser is not None:
            result[name] = (reg.cmd_cls, reg.arg_parser)
    return result
```

### In `repl.py`:
Delete the static `COMMAND_TYPES` dict (~200 lines). In `HarnessREPL.__init__`:
```python
from harness.command._registration import build_repl_command_map
self._command_types = build_repl_command_map()
```

Replace `COMMAND_TYPES` references with `self._command_types`. The tuple structure `(class, arg_parser)` is identical — dispatch logic doesn't change.

---

## 5. Replacing `setup.py` Handler Registration

### Builder function in `_registration.py`:
```python
def register_bus_handlers(bus: CommandBus) -> None:
    """Register all handlers from REGISTRY. Skips duplicates."""
    for reg in REGISTRY.values():
        if reg.cmd_cls is not None and reg.handler is not None:
            if reg.cmd_cls not in bus._type_handlers:
                bus.register_type(reg.handler, reg.cmd_cls)
```

### In `setup.py`:
Replace 40 lines of `bus.register_type(...)` with one line:
```python
from harness.command._registration import register_bus_handlers
register_bus_handlers(bus)
```

No-double-registration: if two REPL names share a TypedCommand class, only one bus registration is created. Remove the three dead handlers (`ResumeEngagementHandler`, `CreateWaveTypedHandler`, `ExecuteStepTypedHandler`) from setup.py — they have no `@register`.

---

## 6. Registry-Aware `/help`

Replace the current `/help` generation (which walks `cli_main.commands` — the Click tree) with one that reads `REGISTRY`:

```python
def _build_help_from_registry(self) -> list[str]:
    lines = ["Available commands:\n"]
    for name in sorted(REGISTRY):
        reg = REGISTRY[name]
        if reg.click_only:
            continue  # CLI-only: don't show in REPL help
        brief = self._get_short_help(name)
        lines.append(f"  /{name:<20s} {brief}")
    lines.append("")
    lines.append("── Special ──")
    lines.append("  /help      Show this help")
    lines.append("  /exit      Exit the REPL")
    lines.append("  /version   Show version info")
    return lines
```

| Command has `@register(...)` | Appears in `/help`? | Works in REPL? |
|---|---|---|
| `cmd_cls=X, handler=Y` | ✅ Yes | ✅ Yes |
| `click_only=True` | ❌ No (CLI-only) | ❌ Shows "CLI only" |
| No `@register` at all | ❌ No | ❌ "Unknown command" |
| Built-in (`/help`, `/exit`) | ✅ Under "Special" | ✅ Hardcoded |

This eliminates the current bug where `/help` lists commands that fail with "Unknown command."

---

## 7. Sync Test

Single pytest file, <100ms runtime, no IO:

```python
# tests/unit/command/test_registration.py

PURE_CLICK_EXEMPTIONS = {
    "shell",            # Runs REPL itself
    "workflows",        # Pure help text
    "team add-agent",   # Informational YAML edit instruction
    "team remove-agent",
}


def _cli_commands() -> set[str]:
    from harness.cli import main as cli_main
    cmds = set()
    for name, cmd in cli_main.main.commands.items():
        if isinstance(cmd, click.Group):
            for sub in cmd.commands:
                cmds.add(f"{name} {sub}")
        else:
            cmds.add(name)
    return cmds


def test_all_cli_commands_registered():
    """Every CLI command needs @register or explicit exemption."""
    missing = _cli_commands() - set(REGISTRY) - PURE_CLICK_EXEMPTIONS
    assert not missing, (
        f"Commands missing @register: {sorted(missing)}"
    )


def test_no_orphaned_registrations():
    """Every registered command must have a Click function."""
    extras = set(REGISTRY) - _cli_commands()
    assert not extras, f"Registered but no Click function: {sorted(extras)}"


def test_repl_map_instantiable():
    """Every REPL command's arg_parser produces valid kwargs."""
    from harness.command._registration import build_repl_command_map
    from harness.command.commands.analysis import AssessCommand
    # ... import all command classes ...
    for name, (cls, parser) in build_repl_command_map().items():
        sample = ["test-slug"] if parser is _single_arg else []
        try:
            cls(**parser(sample))
        except TypeError as e:
            pytest.fail(f"'{name}': kwargs don't match {cls.__name__}: {e}")


def test_no_stale_bus_handlers():
    """Every bus handler has a matching @register."""
    from harness.command.setup import create_bus
    bus = create_bus()
    registered_types = {r.cmd_cls for r in REGISTRY.values() if r.cmd_cls}
    for cmd_type in bus._type_handlers:
        assert cmd_type in registered_types, (
            f"Bus has handler for {cmd_type.__name__} but no @register"
        )
```

---

## 8. Migration — Single Pass

Not multi-phase. One coordinated change:

| Step | Action | Lines |
|------|--------|-------|
| 1 | Create `_registration.py` | ~60 add |
| 2 | Add `@register(...)` to each existing Click command | ~80 add |
| 3 | Replace `COMMAND_TYPES` in `repl.py` | ~200 delete, ~10 add |
| 4 | Replace `setup.py` registrations with `register_bus_handlers(bus)` | ~40 delete, ~1 add |
| 5 | Replace `/help` generation | ~60 delete, ~30 add |
| 6 | Add `test_registration.py` | ~80 add |
| 7 | Remove dead handler registrations from setup.py | ~5 delete |

**Net: +~180 lines of infrastructure, -~305 lines of deleted duplication.**

### What Stays the Same
- Click decorators (`@command()`, `@argument()`, `@option()`)
- Click command bodies (all function implementations)
- Arg parsers (`_single_arg`, `_engagement_create_args`, etc.)
- TypedCommand classes, TypedHandler classes, CommandBus
- CLI `--help` (Click still owns this)
- REPL dispatch logic (still uses `(class, parser)` tuples)

### What Is Deleted
- `COMMAND_TYPES` dict in `repl.py`
- All explicit `bus.register_type()` calls in `setup.py`
- Dead handler registrations (`ResumeEngagementHandler` etc.)
- Click-tree-based `/help` generation

---

## 9. Risks

| Risk | Mitigation |
|------|------------|
| New command without `@register` → missing from REPL | Sync test catches at CI time |
| TypedCommand kwargs mismatched with arg parser | `test_repl_map_instantiable` validates |
| Stale `@register` after Click function removed | `test_no_orphaned_registrations` catches |
| Duplicate `name` in two decorators | `ValueError` at import |
| Circular import | `_registration.py` imports only abstract types — nothing concrete |
| Missing `click_only=True` on Click-only command | `ValueError` at import (no handler) |
| Two REPL names share one TypedCommand | `register_bus_handlers` skips duplicates — one bus registration |

---

## 10. Comparison with Superseded Design

| Aspect | 1,700-line `CommandDef` Registry | ~250-line Decorator (this) |
|--------|----------------------------------|---------------------------|
| Click generation | Custom Click-param DSL → auto-generates CLI | None — Click decorators stay as-is |
| Auto arg parser | Custom parser (6 failure modes per Crichton) | None — existing parsers preserved |
| Migration phases | 3 phases over weeks | Single pass |
| Circular import risk | High (registry imports everything) | None (`_registration.py` imports nothing concrete) |
| Developer burden | Learn 4 sub-dataclasses | Add one `@register(...)` line |
| Lines of infrastructure | ~800 (dataclass + generator + parser) | ~60 (decorator + REGISTRY + builders) |

---

## 11. Key Architecture Decisions

**Why not generate Click from the registry?** — Would require re-expressing every Click feature (`pass_context`, `Choice`, `IntRange`, mutual exclusion, custom types) in a registry DSL, doubling complexity surface. Click stays as Click. The registry is purely metadata.

**Why `click_only=True`?** — Some commands have no TypedCommand/handler (pure file I/O, table formatting). Creating indirection wrappers offers no benefit. `click_only=True` makes the choice explicit.

**Why doesn't `@register` auto-import handlers?** — Explicit handler instances allow dependency injection and guarantee single instantiation.

**Why no auto-arg-parser?** — Per Crichton §2.4, custom arg parsers have multiple failure modes (`nargs=-1`, `=` syntax, short options, flag pairs, optional args, `multiple=True` flags). The existing per-command arg parsers work correctly for all 30 REPL commands. Replacing them is a separate concern with zero benefit for this migration.
