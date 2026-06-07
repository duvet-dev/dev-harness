# Wave 32 — Health Check & Startup Fixes

**Milestone:** 3 — Cleanup
**Effort:** 1-2h
**Status:** 📋 Pending
**Depends on:** None
**Blocks:** Nothing

## Summary

Four small bugs found during testing — all produce startup warnings or errors when running `harness shell`:

1. **`GitHealthChecker` receives a function where it expects an object** — `health.py` passes raw `read_active_engagement` function instead of wrapping it in an adapter, causing `'function' object has no attribute 'read_active_engagement'` on every invocation.
2. **`.harness-freshness.yaml` is tracked in git but always dirty** — runtime metadata file that changes on every harness operation. Needs to be in `.gitignore`.
3. **8 referenced agent roles missing from `agent_registry.py`** — `code-critic`, `architecture-critic`, `research-agent`, `dependency-analyser`, `test-coverage-analyser`, `design-reviewer`, `security-critic`, `security-auditor` exist in teams/phase/skills config files but have no AgentSpec entries.
4. **`/chat` command passes `provider=` kwarg to wrong constructor** — `ChatTypedHandler` passes the whole provider dict as a `provider=` keyword, but neither `SessionClient` nor `InteractiveClient` accept that — they expect individual fields.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Fix `GitHealthChecker` function-vs-object mismatch | 📋 Pending | `health.py:37` — wrap in `_EngagementStore` adapter |
| 2 | Add `.harness-freshness.yaml` to `.gitignore` | 📋 Pending | Runtime state, not project config |
| 3 | Add 8 missing AgentSpec entries | 📋 Pending | `code-critic`, `architecture-critic`, `research-agent`, `dependency-analyser`, `test-coverage-analyser`, `design-reviewer`, `security-critic`, `security-auditor` |
| 4 | Fix `/chat` command `provider=` kwarg | 📋 Pending | `session_handlers.py:85` — unpack provider dict to correct client API |
| 5 | Update engagement tracking | 📋 Pending | `waves.md`, task status files |
| 6 | Tests | 📋 Pending | All existing tests pass |

## Verification

`harness shell` starts without any warning messages. `/chat` returns a proper error (or session opens correctly). `.harness-freshness.yaml` doesn't show as dirty.
