# Wave 03 — REPL Rewiring + Click-Only Commands

**Milestone:** 3 — Integration
**Effort:** 2h
**Status:** 📋 Pending
**Depends on:** Wave 02
**Blocks:** Wave 04

## Summary

The big cutover. This wave replaces the old COMMAND_TYPES static dict with the dynamically-generated `build_repl_command_map()`, adds `@register(click_only=True)` to all Click-only commands, replaces `/help` with a REGISTRY-based generation, and adds the "CLI only" fallback message.

**Crichton notes #1, #2, #3 resolved:**
- #1: "CLI only" fallback added to REPL dispatch
- #2: `/help` preserves group structure (── Engagement ──, ── Wave ──, etc.)
- #3: Brief descriptions fetched from Click Command objects

**Also:** move the arg parser functions (`_single_arg`, `_engagement_create_args`, etc.) from `repl.py` to `_registration.py` to break the circular import risk — `main.py` now imports arg parsers from `_registration.py`.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Move arg parsers from repl.py to _registration.py | 📋 Pending | ~16 functions |
| 2 | Add `@register(click_only=True)` to all Click-only commands | 📋 Pending | ~11 commands |
| 3 | Replace `COMMAND_TYPES` with `build_repl_command_map()` | 📋 Pending | ~200 lines deleted |
| 4 | Replace `/help` with REGISTRY-based generation (grouped) | 📋 Pending | Crichton notes #2, #3 |
| 5 | Add "CLI only" fallback to REPL dispatch | 📋 Pending | Crichton note #1 |
| 6 | Remove dead arg parsers + unused imports from repl.py | 📋 Pending | Cleanup |

## Verification

- All 4 sync tests pass (Click-only commands now have `@register`)
- REPL `/help` shows correct commands, grouped, no broken commands
- Typing a Click-only command shows "CLI only — use: harness <command>"
- All COMMAND_TYPES entries are gone — dispatch goes through `build_repl_command_map()`
- REPL built-ins (`/help`, `/exit`, `/version`, `/exec`, `/shell`) still work
- Existing test suite passes
