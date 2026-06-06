# Task 5 — Remove `harness agent run sync` CLI command

**Status:** 📋 Pending
**Wave:** 30-openclaw-sync-removal
**Dependencies:** None
**Effort:** 0.3h

## Description

Remove the `harness agent run sync` CLI command from `src/harness/cli/main.py` (lines ~544-560). If the `agent run` subcommand only existed for sync, remove the entire `run` subcommand.

## Acceptance Criteria

- [ ] `agent run sync` no longer exists in CLI
- [ ] `from harness.sync.pipeline import run_sync` removed
- [ ] No leftover sync-related code in CLI

## Verification

```bash
python -m harness.cli.main agent run --help 2>&1
# → no reference to sync
```
