# Task 1 — Single shared CommandBus

**Status:** ✅ Complete
**Wave:** 28-command-bus-consolidation
**Dependencies:** None
**Effort:** 1h

## Description

Create a single shared `CommandBus` instance that lives for the app lifetime. Remove the 13 fresh `create_bus()` calls across CLI and REPL. The bus is created once at startup, used for all dispatches.

## Acceptance Criteria

- [ ] One bus instance, not created per dispatch
- [ ] CLI creates bus once at startup
- [ ] REPL reuses the same bus
- [ ] No regressions in command dispatch
