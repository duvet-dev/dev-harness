# Dev Harness — Design (REPL Command Wiring)

> **Purpose:** Single evolving design document. Updated through review cycles.
> **Engagement:** 005-command-registry
> **Status:** Reviewed (Crichton — APPROVED)
> **Last reviewed:** 2026-06-07

---

## 0. Executive Summary

Every REPL-dispatchable command must currently be registered in three independent places:
Click CLI → `COMMAND_TYPES` dict → handler registry. This has produced 12 broken REPL
commands, 3 pieces of dead code, and a `/help` that lies to users.

This design introduces a `@register` decorator — a single source of truth metadata tag
on each existing Click function. From it, the REPL command map, bus handler registrations,
and `/help` text are all derived. The migration is single-pass: additive then subtractive
in one coordinated change.

## 1. Architecture Overview

### 1.1 High-Level Flow

```
@click.command() + @register(...)
         │
         ├── records metadata in REGISTRY dict (import time)
         │
         ├── build_repl_command_map() → REPL COMMAND_TYPES replacement
         ├── register_bus_handlers(bus) → replaces setup.py registrations
         ├── REGISTRY-aware /help → replaces Click-tree-based generation
         └── Sync tests → CI guardrail against drift
```

### 1.2 Core Modules

```
src/harness/command/
  _registration.py   # @register decorator + REGISTRY + builder functions (~60 lines)
  registry.py        # (future: typed command registry, not this engagement)

src/harness/shell/
  repl.py            # Uses build_repl_command_map() instead of COMMAND_TYPES
```

### 1.3 Import Chain

```
main.py ──imports──> _registration.py    (decorator + REGISTRY dict populated)
                         │
repl.py ──imports──> _registration.py    (reads REGISTRY → builds REPL map, /help)
setup.py ──imports──> _registration.py   (reads REGISTRY → registers handlers)
```

No circular imports: `_registration.py` imports only abstract base types
(`TypedCommand`, `TypedHandler`). Concrete command/handler classes are imported by
`main.py`, which imports `_registration.py` first.

## 2. Data Model

### 2.1 `@register` Decorator

```python
def register(
    name: str,
    *,
    cmd_cls: Optional[type[TypedCommand]] = None,
    handler: Optional[TypedHandler] = None,
    arg_parser: Optional[Callable[[list[str]], dict[str, Any]]] = None,
    click_only: bool = False,
) -> Callable
```

**Rules:**
- `click_only=True`: command exists only in Click CLI, not in REPL. `cmd_cls`/`handler` not required.
- `click_only=False` (default): requires `cmd_cls`, `handler`, and `arg_parser`. Raises `ValueError` if missing.
- Duplicate `name` raises `ValueError` at import.
- Decorator returns the function unchanged — Click still owns the function.

### 2.2 `Registration` Dataclass

```python
@dataclass
class Registration:
    name: str
    cmd_cls: Optional[type] = None
    handler: Optional[TypedHandler] = None
    arg_parser: Optional[Callable] = None
    click_only: bool = False
```

### 2.3 Builder Functions

```python
def build_repl_command_map() -> dict[str, tuple[type, Callable]]:
    """Same structure as current COMMAND_TYPES dict.
    Excludes click_only entries. Each entry is (cmd_cls, arg_parser)."""
    ...

def register_bus_handlers(bus: CommandBus) -> None:
    """Register all handlers from REGISTRY. Skips duplicates."""
    ...
```

## 3. Key Systems

### 3.1 REPL Command Map Replacement

Delete the static `COMMAND_TYPES` dict (~200 lines from `repl.py`).

In `HarnessREPL.__init__`:
```python
from harness.command._registration import build_repl_command_map
self._command_types = build_repl_command_map()
```

Replace any remaining `from harness.shell.repl import COMMAND_TYPES` with
instance attribute access.

### 3.2 Handler Registration Replacement

In `setup.py`, replace ~40 lines of explicit `bus.register_type(...)` calls with:
```python
from harness.command._registration import register_bus_handlers
register_bus_handlers(bus)
```

No-double-registration: if two REPL names share a TypedCommand (unlikely but possible),
only one bus registration is created.

### 3.3 Registry-Aware `/help`

Replace the current help generation (which walks `cli_main.commands`) with one
that reads `REGISTRY` directly:

- Commands with full `@register(...)` appear in `/help` with brief description
- Commands with `click_only=True` are excluded from REPL `/help`
- REPL built-ins (`/help`, `/exit`, `/version`) are hardcoded
- Group structure is preserved by sorting by group prefix

**Implementation note:** Brief descriptions come from the Click Command object
(via `cli_main`) rather than from the registry — avoids duplicating help text.

### 3.4 Click-Only Commands

Typing a `click_only=True` command in the REPL should show:
```
"CLI only — use: harness engagement list"
```

This requires a second lookup against REGISTRY for `click_only` entries after
the main dispatch loop fails. ~5 lines.

## 4. Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | `@register` decorator, not `CommandDef` registry dataclass | ~60 lines of infrastructure vs ~800. No Click generation, no auto-parsing, no multi-phase migration. |
| D2 | No auto-arg-parser | Existing 16 per-command parsers are battle-tested. Auto-parser had 6 failure modes (Crichton §2.4). |
| D3 | No Click generation from registry | Would require reimplementing Click features (`Choice`, `IntRange`, mutual exclusion, `pass_context`). Click stays as Click. |
| D4 | Single-pass migration | No intermediate state with parallel registrations. Sync test added at same time. |
| D5 | `click_only=True` for intentional exemptions | Makes exclusion visible. Prevents accidentally-omitted commands from being indistinguishable from intentionally-CLI-only ones. |
| D6 | Help descriptions from Click objects, not registry | Avoids duplicating help text. Registry is metadata, not content. |

## 5. Review History

| Date | Scope | Reviewer | Outcome |
|------|-------|----------|---------|
| 2026-06-07 | Full decorator design | Crichton | **APPROVED** — 4 minor implementation notes (sub-15 lines each) |

## 6. Implementation Notes (from Crichton Review)

1. **"CLI only" message**: design claims it but REPL dispatch doesn't implement the `click_only` fallback. ~5 lines to add.

2. **Help group structure**: flat sorting loses `── Engagement ──` / `── Wave ──` sections. Trivial: sort by group prefix. ~15 lines.

3. **`_get_short_help()` undefined**: design references it but doesn't define it. Get brief descriptions from the Click Command object. ~5 lines.

4. **Import ordering**: `main.py` must be imported before `repl.py`/`setup.py`. Document constraint. Consider a warning/raise when REGISTRY is empty. ~5 lines.
