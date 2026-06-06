# Task 6 — Remove COMMAND_MAP and Click fallback

**Status:** ✅ Complete
**Wave:** 28-command-bus-consolidation
**Dependencies:** Tasks 1-2
**Effort:** 1h

## Description

REPL currently has two dispatch paths: `COMMAND_MAP` at `repl.py:203` for most commands, and a Click fallback at `repl.py:595-596` for unknown commands. Remove both. All commands dispatch through `bus.dispatch()`.

## Acceptance Criteria

- [ ] `COMMAND_MAP` removed from repl.py
- [ ] Click fallback path removed from repl.py
- [ ] All REPL commands go through bus.dispatch()
- [ ] `/help`, `/exit`, `/quit` still work (these are REPL-level, not bus commands)
