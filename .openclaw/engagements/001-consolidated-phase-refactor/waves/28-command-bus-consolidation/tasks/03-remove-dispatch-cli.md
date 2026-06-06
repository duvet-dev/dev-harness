# Task 3 — Remove dispatch_cli_command()

**Status:** ✅ Complete
**Wave:** 28-command-bus-consolidation
**Dependencies:** Task 2
**Effort:** 0.5h

## Description

With all commands now typed, remove `dispatch_cli_command()`. All 45 commands go through `bus.dispatch()`. Delete the function from `cli/commands.py`.

## Acceptance Criteria

- [ ] `dispatch_cli_command()` no longer exists
- [ ] All CLI commands dispatch through `bus.dispatch()`
- [ ] Tests pass
