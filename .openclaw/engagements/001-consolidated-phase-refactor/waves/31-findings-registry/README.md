# Wave 31 — Findings Registry

**Milestone:** 3 — Cleanup
**Effort:** 3-5h
**Status:** 📋 Pending
**Depends on:** None (independent)
**Blocks:** Nothing

## Summary

Issues raised by any feedback loop — observer analysis, architecture critic loop, develop-test-validate loop, human review — currently produce one-shot reports with no memory between runs. No issue IDs, no resolution tracking, no regression detection. Create a persistent Findings Registry.

**Design:** See `design/design.md §4.4` for full schema and lifecycle.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Create FindingsStore class | 📋 Pending | Reads/writes findings.yaml at `.harness/engagements/<slug>/findings/` |
| 2 | Wire synthesis agent to persist findings | 📋 Pending | Replace one-shot report with registry write |
| 3 | Add delta detection | 📋 Pending | New, resolved, regressed, wont-fix-regression |
| 4 | Add human sign-off flag | 📋 Pending | `resolved/pending_verification` until confirmed |
| 5 | Wire wave-plan to declare resolved findings | 📋 Pending | Wave metadata: `resolves: ["F-001", "F-003"]` |
| 6 | Tests | 📋 Pending | Persistence across runs, deltas, regression, sign-off |

## Verification

After running observer twice with 2 fixes in between: new findings have IDs, resolved findings appear in delta, unfixed findings remain open.
