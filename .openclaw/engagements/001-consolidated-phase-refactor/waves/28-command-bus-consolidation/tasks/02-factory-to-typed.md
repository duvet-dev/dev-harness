# Task 2 — Move factory functions to typed commands

**Status:** ✅ Complete
**Wave:** 28-command-bus-consolidation
**Dependencies:** None
**Effort:** 1-2h

## Description

All 32 remaining factory functions in `cli/commands.py` use `dispatch_cli_command()` with string-keyed dispatch. Convert each to a typed command + typed handler pattern. New commands register in setup.py, old factory functions are removed.

## Acceptance Criteria

- [ ] 32 factory functions converted to typed commands
- [ ] All commands registered in setup.py
- [ ] Zero references to old factory functions from any module
