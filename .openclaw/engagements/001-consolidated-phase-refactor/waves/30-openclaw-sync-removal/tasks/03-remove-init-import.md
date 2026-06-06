# Task 3 — Remove sync agent from agents/__init__.py

**Status:** 📋 Pending
**Wave:** 30-openclaw-sync-removal
**Dependencies:** Task 2
**Effort:** 0.1h

## Description

Remove the `SYNC_AGENT` import and `__all__` entry from `src/harness/agents/__init__.py`.

## Acceptance Criteria

- [ ] `from harness.agents.builtin.sync_agent import SYNC_AGENT` removed
- [ ] `"SYNC_AGENT"` removed from `__all__`
