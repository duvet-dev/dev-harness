# Wave 30 — OpenClaw Sync Removal

**Milestone:** 3 — Cleanup
**Effort:** 1.5h
**Status:** 📋 Pending
**Depends on:** None (independent)
**Blocks:** Nothing

## Summary

The harness must not know about OpenClaw. Delete the entire sync module: ~1,700 lines of source + tests with zero dependencies.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Delete src/harness/sync/ | 📋 Pending | 5 files, 724 lines |
| 2 | Delete src/harness/agents/builtin/sync_agent.py | 📋 Pending | 21 lines |
| 3 | Remove sync agent from agents/__init__.py | 📋 Pending | Import + __all__ |
| 4 | Remove sync agent from agent_registry.py | 📋 Pending | SYNC_AGENT AgentSpec block |
| 5 | Remove `harness agent run sync` CLI command | 📋 Pending | cli/main.py:544-560 |
| 6 | Delete tests/unit/sync/ | 📋 Pending | 5 files, 915 lines |
| 7 | Verification | 📋 Pending | |

## Verification

```bash
grep -r "sync_agent\|SYNC_AGENT\|harness.sync\|openclaw" src/ tests/  → zero hits
find src/harness/sync -type f  → directory gone
find tests/unit/sync -type f   → directory gone
```
