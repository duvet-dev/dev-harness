# Crichton: Final Review — Decorator-Based Command Registration

**Date:** 2026-06-07
**Subject:** `command-registry-decorator-design.md` (design proposal)
**Reference:** `crichton-registry-design-review.md` (previous review, 5 major issues + 10 edge cases)

---

## 1. All 5 Prior Major Issues — Resolved

| # | Original Issue | Resolution in Decorator Design |
|---|---------------|-------------------------------|
| 1 | Phase 1 adds a 4th registration | Single-pass migration (§8). No intermediate state with 4 registrations. |
| 2 | Registry key naming breaks REPL dispatch | `@register(name="engagement status")` — the name IS the REPL key. No mismatch. |
| 3 | `/help` unaddressed | §6: `/help` reads REGISTRY, excludes `click_only=True`. Explicitly addresses the bug. |
| 4 | Auto-arg-parser broken (6 failure modes) | No auto-arg-parser. Existing per-command parsers preserved. Verified: all 16 arg parsers match `(list[str]) -> dict[str, Any]`. |
| 5 | Click-param → TypedCommand-field mapping broken | Click decorators stay as-is. No mapping needed. `@register` is purely additive metadata; Click still owns param handling. |

**Verdict: All 5 major issues are resolved by the simpler design.** The decorator approach avoids the problems by not attempting Click generation or auto-parsing at all — it sidesteps rather than fixes them, which is the correct architectural choice for this scope.

---

## 2. Edge Cases — From 10 to 2

Of the 10 edge cases from my original review (§3):

| Edge Case | Status |
|-----------|--------|
| 3.1 `click.Context` | **Not applicable** — Click stays as-is, bodies unchanged. |
| 3.2 Direct `echo` | **Not applicable** — same reason. |
| 3.3 Mutual exclusion | **Not applicable** — no Click param generation. |
| 3.4 `click.Choice` / coercion | **Not applicable** — no auto-arg-parser. |
| 3.5 Orphaned `presenter` field | **Not applicable** — no presenter field in this design. |
| 3.6 Multi-word group names | **Not applicable** — no Click group generation. |
| 3.7 Dead commands | **Addressed** — §5 explicitly removes dead handlers from `setup.py`. |
| 3.8 REPL built-ins not in registry | **Largely not applicable** — built-ins (`/help`, `/exit`, `/version`, `/exec`, `/shell`, phase commands) are handled before the CommandBus dispatch block. They were never in COMMAND_TYPES. No regression. |
| 3.9 Circular import risk | **Resolved by design** — `_registration.py` imports only abstract types. Verified: the import chain is linear. |
| 3.10 `_RAW_FNS` for Click-only | **Not applicable** — no code generation, no `_RAW_FNS`. |

**That's 8 not applicable, 2 addressed.** This is the strongest signal that the decorator approach is the right scope — it eliminates problems by reducing surface area rather than trying to solve them all within a larger system.

---

## 3. New Findings — 4 Minor Issues

### 3.1 "CLI only" message is unimplemented (minor)

The design table in §6 says typing a `click_only=True` command shows "CLI only." But the only REPL change described is replacing `COMMAND_TYPES` with `self._command_types = build_repl_command_map()`. `build_repl_command_map()` excludes `click_only` entries entirely (it requires `cmd_cls is not None and arg_parser is not None`). The dispatch code would fall through to "Unknown command."

**To actually show "CLI only"**: the REPL dispatch would need a second lookup against raw REGISTRY entries with `click_only=True`. The design doesn't include this lookup.

**Resolution**: Either (a) add a `REGISTRY` fallback after the dispatch loop that checks `click_only=True` and prints "CLI only — use the CLI: `harness engagement list`", or (b) drop the "CLI only" claim and accept "Unknown command" (honest, if less helpful). Either is ~5 lines.

### 3.2 `/help` loses group structure (minor)

Current `/help` is grouped (── General ──, ── Engagement ──, ── Wave ──, ── Special ──). The design's `_build_help_from_registry()` uses flat `sorted(REGISTRY)` — all commands in one alphabetical list. This is a UX degradation: users lose the logical grouping that maps to the CLI's Click groups.

**Resolution**: Trivial to fix — sort REGISTRY entries by group prefix first, then alphabetically within groups. Or keep the existing `_build_command_index()` help structure but filter against REGISTRY for accuracy. ~15 additional lines.

### 3.3 `_get_short_help()` is undefined (minor)

The `/help` code in §6 references `_get_short_help(name)` but doesn't define it. The current code extracts brief help from `cmd.help` or `cmd.short_help` on the Click Command object. The decorator design doesn't wire Click Command objects into REGISTRY (only `Registration` dataclass with no help field).

**Resolution**: `_get_short_help(name)` needs a source. Options: (a) add an optional `help` field to `Registration`, (b) look up the Click Command from `cli_main` (imports already available in REPL `__init__`), or (c) omit brief descriptions and only show command names. Option (b) is simplest — the REPL already has access to the Click tree via `cli_main`.

### 3.4 Import ordering assumption is undocumented (minor)

§2.3 states "`main.py` imported first → all `@register` decorators fire before REPL or bus modules are loaded." This is correct for the happy path, but if a test or script imports `repl.py` or `setup.py` without first importing `main.py`, the REGISTRY is empty.

**Resolution**: Document the constraint. Alternatively, have `build_repl_command_map()` and `register_bus_handlers()` emit a warning (or raise) when REGISTRY is empty. ~5 lines.

---

## 4. What the Design Gets Right

Beyond resolving all 5 major issues, the design makes several correct choices:

1. **Preserves existing Click decorators** — No reimplementation of Click's parameter DSL. This is the key insight: the registry doesn't need to know about Click, it just needs to record which commands exist.

2. **Explicit `click_only=True`** — Makes intentional exclusion visible rather than implicit. Exactly the pattern I praised in the original design's `bus=None, repl=None`.

3. **No auto-arg-parser** — Correctly recognizes that parsing is a separate, solved concern in this codebase. The 16 existing parsers are battle-tested.

4. **Duplicate-name check at import time** — `ValueError` if two decorators claim the same name. Fast feedback, no runtime surprise.

5. **No-double-registration on the bus** — `register_bus_handlers` checks `cmd_cls not in bus._type_handlers` before registering, handling the case where two REPL names share a TypedCommand.

6. **Sync test covers cross-referencing** — `test_all_cli_commands_registered`, `test_no_orphaned_registrations`, `test_repl_map_instantiable`, `test_no_stale_bus_handlers`. Four tests that prevent drift in both directions.

7. **Single-pass migration** — No intermediate state with parallel registries. The migration is additive then subtractive in one coordinated change.

8. **Scope discipline** — ~60 lines of infrastructure vs the original's ~800. The decorator solves the registration problem and only the registration problem.

---

## 5. Minor Implementation Notes (Not Issues)

These are observations for the implementer, not design flaws:

1. **`bus._type_handlers` is a private attribute** accessed from `register_bus_handlers()`. Confirmed `_type_handlers` is indeed a `dict[type, ...]` on the CommandBus class. Works, but slightly unclean. If a public `has_handler(cls)` method existed, it'd be cleaner. Not worth adding one just for this.

2. **`REGISTRY` is a module-level mutable dict.** Standard Python pattern. Thread safety is not a concern here (import-time only, single-threaded).

3. **Tab completion uses the Click tree**, not COMMAND_TYPES. No change needed — tab completion is unaffected by the registry migration. It'll continue to suggest commands that exist in the CLI, including `click_only=True` ones that don't work in the REPL — but that's the same as current behavior, not a regression.

4. **Phase commands** (`assess`, `requirements`, etc.) are not in REGISTRY. They're handled before the CommandBus dispatch block. The design's help "Special" section only lists `/help`, `/exit`, `/version` — the current help lists 9 special commands. The design should either include all special commands or document that the help example is simplified.

---

## 6. Final Verdict

**APPROVED.**

The decorator-based design resolves all 5 major issues from the original review. It eliminates 8 of 10 edge cases by virtue of being simpler — it doesn't generate Click, doesn't auto-parse, doesn't abstract param types, and doesn't require a multi-phase migration. What's left (350 lines of design) is proportional to the problem (12 broken REPL commands from a 3-registration anti-pattern).

The 4 minor findings in §3 are implementation polish — each is under 15 lines to address. None is a structural concern that would invalidate the approach.

**Recommended**: brief the build coordinator with the design as-is, flagging §3.1–§3.4 as "implementation notes" rather than design changes. All four can be resolved during coding without revisiting the architecture.

---

*Append to project file and CNS change queue.*
