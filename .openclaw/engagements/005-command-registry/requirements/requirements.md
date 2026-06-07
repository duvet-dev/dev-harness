# Dev Harness — Requirements (REPL Command Wiring)

> **Purpose:** Single view of all requirements, from original capture through detailed specs.
> **Engagement:** 005-command-registry
> **Updated:** 2026-06-07

---

## 0. Domain Language

| Term | Definition |
|------|------------|
| Click CLI | The command-line interface defined via `@click.command()` decorators in `cli/main.py` |
| REPL | Interactive shell (`harness shell`) with slash-commands like `/engagement list` |
| COMMAND_TYPES | Static dict in `repl.py:224` mapping command names to `(TypedCommand, arg_parser)` tuples |
| CommandBus | Central dispatch for typed commands via `bus.dispatch()` |
| TypedCommand | Dataclass subclass of `TypedCommand` with typed fields |
| TypedHandler | Class with `handle(command) -> TypedResult` registered on the bus |
| `@register` decorator | Proposed single-source-of-truth decorator on Click functions |
| Click-only command | A command with no TypedCommand/handler (pure Click implementation) |
| Dead handler | A handler registered on the bus but wired to no UI command |

## 1. Core Requirements

| # | Requirement | Status | Source | Wave |
|---|-------------|--------|--------|------|
| R1 | Every REPL-accessible command must have a single registration point | Pending | Andy — startup error investigation | TBD |
| R2 | Commands must not show up in `/help` if they can't be executed from the REPL | Pending | Andy — `/engagement list` fails | TBD |
| R3 | Sync tests must detect drift between Click CLI, REPL map, and handler registry | Pending | Crichton — structural analysis | TBD |
| R4 | Dead handlers must be removed from the bus | Pending | Crichton — gap matrix | TBD |
| R5 | The migration must be single-pass (not multi-phase with parallel registrations) | Pending | Crichton — design review issue #1 | TBD |
| R6 | REPL dispatch must remain backward-compatible | Pending | Architect — design constraint | TBD |
| R7 | Click-only commands must be explicitly documented, not accidentally omitted | Pending | Crichton — design review recommendation | TBD |

## 2. Detailed Specs

### R1 — Single Registration Point

A `@register(...)` decorator added to each existing Click command function. The decorator records metadata at import time and returns the function unchanged. From this registry, both the REPL command map and bus handler registrations are derived.

**Key design:**
- `@register(name="engagement list", cmd_cls=ListEngagementsCommand, handler=..., arg_parser=...)` for bus-dispatchable commands
- `@register(name="engagement list", click_only=True)` for CLI-only commands
- Duplicate names raise `ValueError` at import time
- Missing `cmd_cls`/`handler` raises `ValueError` unless `click_only=True`

**File:** `src/harness/command/_registration.py`

### R2 — Registry-Aware Help

Replace Click-tree-based `/help` generation with REGISTRY-based generation:
- Commands with `click_only=True` are excluded from REPL `/help`
- Commands with a full `@register(...)` appear in `/help`
- Group structure (── Engagement ──, ── Wave ──) is preserved

### R3 — Sync Tests

Four tests in `tests/unit/command/test_registration.py`:
1. **`test_all_cli_commands_registered`** — every Click CLI command has `@register` or is in `PURE_CLICK_EXEMPTIONS`
2. **`test_no_orphaned_registrations`** — every `@register` has a corresponding Click function
3. **`test_repl_map_instantiable`** — every REPL command's arg parser produces valid kwargs for its TypedCommand
4. **`test_no_stale_bus_handlers`** — every bus handler has a matching `@register`

Exemptions list: `shell` (runs REPL itself), `workflows` (pure help text), `team add-agent`, `team remove-agent` (informational YAML edit instructions).

### R4 — Dead Handler Removal

Three handlers registered on the bus but wired to no UI command:
- `ResumeEngagementHandler` / `ResumeEngagementCommand`
- `CreateWaveTypedHandler` / `CreateWaveCommand`
- `ExecuteStepTypedHandler` / `ExecuteStepCommand`

Remove from `setup.py`. Verify no test depends on them.

### R5 — Single-Pass Migration

The migration is additive-then-subtractive in one coordinated change:
1. Create `_registration.py` (additive)
2. Add `@register(...)` to each Click command (additive)
3. Replace `COMMAND_TYPES` with `build_repl_command_map()` (deletive)
4. Replace `setup.py` registrations with `register_bus_handlers(bus)` (deletive)
5. Replace `/help` generation (deletive)
6. Add sync tests (additive)

No intermediate state where both old and new registrations exist.

## 3. Coverage Map

| Requirement | Status | Wave(s) |
|-------------|--------|---------|
| R1 — Single registration (`@register` decorator) | Pending | TBD |
| R2 — Registry-aware `/help` | Pending | TBD |
| R3 — Sync tests | Pending | TBD |
| R4 — Dead handler removal | Pending | TBD |
| R5 — Single-pass migration | Pending | TBD |
| R6 — Backward compatibility | Pending | TBD |
| R7 — Explicit Click-only commands | Pending | TBD |
