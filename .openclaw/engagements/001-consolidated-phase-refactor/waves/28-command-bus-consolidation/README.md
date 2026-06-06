# Wave 28 — Command Bus & Presenter Consolidation

**Milestone:** 3 — Cleanup
**Effort:** 5-8h
**Status:** 🔧 In Progress
**Depends on:** None (independent of phase changes)
**Blocks:** Nothing

## Summary

The typed command architecture was built bottom-up (types, bus, handlers) but top-down wiring was never finished. 32/45 commands still use old factory dispatch. A fresh bus is created per dispatch (13x). REPL has COMMAND_MAP + Click fallback. `cli/main.py` is 2,408 lines (target ~800).

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Single shared CommandBus | ✅ Complete | One per app lifetime |
| 2 | Move factory functions to typed commands | ✅ Complete | All 32 converted in cli/main.py |
| 3 | Remove dispatch_cli_command() | 🔧 In Progress | From cli/main.py (REPL refs remain) |
| 4 | Expand CliPresenter | 📋 Pending | Type-specific formatting for all result types |
| 5 | Expand ReplPresenter | 📋 Pending | ANSI formatting, not just emoji |
| 6 | Remove COMMAND_MAP and Click fallback | ✅ Complete | From repl.py |
| 7 | Delete cli/commands.py | 📋 Pending | |
| 8 | Tests | 📋 Pending | All pass, coverage maintained |

## Verification

`cli/main.py` ~800 lines. `grep "dispatch_cli_command" src/` → zero hits. `grep "COMMAND_MAP" src/` → zero hits.
