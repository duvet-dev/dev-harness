# Wave 04 — Dead Code Removal + Final Verification

**Milestone:** 4 — Cleanup
**Effort:** 1.5h
**Status:** 📋 Pending
**Depends on:** Wave 03
**Blocks:** None (final wave)

## Summary

Remove the 3 dead handler/command classes that are wired to no UI, plus their wireframe handler files if appropriate. Clean up stale test references. Run full test suite. Final grep for any remaining old-system references.

The 3 dead pieces (already unregistered from the bus in Wave 02, now remove the actual files):
- `ResumeEngagementCommand` + `ResumeEngagementHandler` — in `engagement.py` / `engagement_handlers.py`
- `CreateWaveCommand` + `CreateWaveTypedHandler` — in `wave.py` / `wave_handlers.py`
- `ExecuteStepCommand` + `ExecuteStepTypedHandler` — in `wave.py` / `wave_handlers.py`

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Delete dead command classes + update import chains | 📋 Pending | ResumeEngagementCommand, CreateWaveCommand, ExecuteStepCommand |
| 2 | Delete dead handler classes + update import chains | 📋 Pending | ResumeEngagementHandler, CreateWaveTypedHandler, ExecuteStepTypedHandler |
| 3 | Remove/update stale test references | 📋 Pending | `test_typed_command_dispatch.py`, `test_handler_integration.py`, `test_cli_commands.py` |
| 4 | Final cleanup grep + full test suite | 📋 Pending | Verify no dead references remain |

## Verification

- `grep -rn "ResumeEngagement\|CreateWaveCommand\|CreateWaveTypedHandler\|ExecuteStepCommand\|ExecuteStepTypedHandler" src/` → zero hits
- No references to removed classes in any test file
- Full test suite passes: `python -m pytest tests/ -q`
- All 4 sync tests pass
- REPL dispatch still works for all bus-dispatchable commands
