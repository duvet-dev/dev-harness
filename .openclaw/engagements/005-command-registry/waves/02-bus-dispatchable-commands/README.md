# Wave 02 — Add @register to Bus-Dispatchable Commands + Replace setup.py

**Milestone:** 2 — Wiring
**Effort:** 2h
**Status:** 📋 Pending
**Depends on:** Wave 01
**Blocks:** Wave 03

## Summary

Add the `@register(name="...", cmd_cls=..., handler=..., arg_parser=...)` decorator to all 30 bus-dispatchable Click commands in `main.py`. Replace all explicit `bus.register_type(...)` calls in `setup.py` with a single `register_bus_handlers(bus)` call.

At the end of this wave, the REGISTRY has entries for all 30 bus-dispatchable commands. The bus is populated via the new registration system. The old `COMMAND_TYPES` dict still exists in repl.py and continues to be used for REPL dispatch — the REPL still works identically.

The 3 dead handler registrations (ResumeEngagementHandler, CreateWaveTypedHandler, ExecuteStepTypedHandler) are commented out or removed from setup.py since they have no @register decorator and won't be picked up by `register_bus_handlers()`.

**Key constraint:** Each `@register`'s `arg_parser` must match the existing arg parser function/lambda from COMMAND_TYPES to ensure identical dispatch behaviour.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Add `@register` to engagement lifecycle commands | 📋 Pending | ~8 commands |
| 2 | Add `@register` to phase/session/management commands | 📋 Pending | ~8 commands |
| 3 | Add `@register` to wave/changelog/governance commands | 📋 Pending | ~8 commands |
| 4 | Add `@register` to agent/team/consult/remaining commands | 📋 Pending | ~6 commands |
| 5 | Replace setup.py registrations with `register_bus_handlers(bus)` | 📋 Pending | ~40 lines → 1 line |

## Verification

- All 30 bus-dispatchable commands have `@register(...)` with correct `cmd_cls`, `handler` instances, and `arg_parser` references
- `REGISTRY` contains 30 entries when `main.py` is imported
- `setup.py` uses `register_bus_handlers(bus)` instead of individual `bus.register_type()` calls
- Dead handler registrations are no longer in setup.py (or commented out)
- Existing test suite passes: `python -m pytest tests/ -q`
- Sync test `test_all_cli_commands_registered` has fewer failures (still fails for Click-only commands)
- Sync test `test_no_stale_bus_handlers` passes (no handlers on bus without @register)
