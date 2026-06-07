# Dev Harness — Waves Plan (REPL Command Wiring)

> **Purpose:** Single view of all waves — completed and planned.
> **Engagement:** 005-command-registry
> **Updated:** 2026-06-07
> **Principle:** Single-pass migration — additive then subtractive, no intermediate state with parallel registrations.
> **Source:** Decorator-based `@register` design (Crichton — APPROVED, 2026-06-07)

---

## Wave Plan

4 waves, ~1.5-2h each.

### Dependency Flow

```
Wave 1: Registration Infrastructure + Sync Tests
  Creates _registration.py + sync test suite.
  Purely additive — no deletions. All tests pass.
    ↓
Wave 2: @register on Bus-Dispatchable Commands + Replace setup.py
  Adds @register to all 30 bus-dispatchable commands.
  Replaces explicit bus.register_type() → register_bus_handlers(bus).
  Dead handler imports remain but their lines are commented out.
    ↓
Wave 3: REPL Rewiring + Click-Only Commands
  Replaces COMMAND_TYPES dict with build_repl_command_map().
  Adds @register(click_only=True) to all 11 Click-only commands.
  Replaces /help with REGISTRY-based generation (grouped).
  Adds "CLI only" fallback. Crichton notes #1-#3 resolved.
    ↓
Wave 4: Dead Code Removal + Final Verification
  Deletes 3 dead handler/command classes + wireframe handlers/commands.
  Removes stale test references. Cleanup verification.
  Full test suite. Crichton note #4 import ordering already done in W1.
```

### Wave Details

| Wave | Name | Effort | Depends On | Crichton Notes |
|------|------|--------|------------|----------------|
| 01 | Registration Infrastructure + Sync Tests | 1.5h | — | Note #4 (empty REGISTRY warning) |
| 02 | Bus-Dispatchable Commands + setup.py | 2h | W1 | — |
| 03 | REPL Rewiring + Click-Only Commands | 2h | W2 | Notes #1, #2, #3 |
| 04 | Dead Code Removal + Final Verification | 1.5h | W3 | — |

---

## Crichton Implementation Notes — Coverage Map

| # | Note | Resolved In | Resolution |
|---|------|-------------|-----------|
| 1 | "CLI only" message unimplemented | Wave 03 | Click-only fallback after main dispatch loop |
| 2 | `/help` loses group structure | Wave 03 | Sort by group prefix, preserve section headers |
| 3 | `_get_short_help()` undefined | Wave 03 | Use Click Command objects from `cli_main` |
| 4 | Import ordering assumption undocumented | Wave 01 | Empty-REGISTRY warning/raise in builder functions |

---

## Requirements Coverage Map

| # | Requirement | Wave(s) |
|---|-------------|---------|
| R1 | Single registration point (`@register` decorator) | W1 + W2 + W3 |
| R2 | Registry-aware `/help` | W3 |
| R3 | Sync tests detect drift | W1 |
| R4 | Dead handlers removed from bus | W2 (setup.py) + W4 (files + tests) |
| R5 | Single-pass migration | All waves (coordinated additive-then-subtractive) |
| R6 | Backward compatible REPL dispatch | W2 + W3 (COMMAND_TYPES → build_repl_command_map() preserves tuple structure) |
| R7 | Explicit Click-only commands | W3 |

---

## Target State

After all 4 waves:

```
src/harness/command/_registration.py     # @register decorator + REGISTRY + builder functions (~60 lines)
src/harness/shell/repl.py                 # ~200 fewer lines (COMMAND_TYPES + Click-tree help deleted)
src/harness/command/setup.py              # ~40 fewer lines (single register_bus_handlers() call)
src/harness/command/handlers/             # 3 less files (dead handler classes deleted)
tests/unit/command/test_registration.py   # 4 sync tests (~80 lines)
```

### What's Deleted
- `COMMAND_TYPES` dict (~200 lines from repl.py)
- Explicit `bus.register_type()` calls (~40 lines from setup.py)
- Click-tree-based `/help` generation (~60 lines from repl.py)
- 3 dead handler registrations (ResumeEngagementHandler, CreateWaveTypedHandler, ExecuteStepTypedHandler)
- Their 3 command dataclasses + their test cases

### What Stays the Same
- Click decorators (`@command()`, `@argument()`, `@option()`) — unchanged
- Click command bodies (all function implementations) — unchanged
- TypedCommand classes, TypedHandler classes, CommandBus — unchanged
- CLI `--help` — Click still owns this, unchanged
- REPL dispatch logic — still uses `(class, parser)` tuples, unchanged
- Arg parser functions — moved to `_registration.py`, unchanged signatures

### Net Change
+~60 lines infrastructure + ~80 lines tests
-~305 lines deleted duplication
= **~165 lines net reduction** + guaranteed sync forever.
