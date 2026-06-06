# Wave 22 — Phase System Consolidation

**Milestone:** 1 — Foundation
**Effort:** 5-8h
**Status:** 📋 Pending
**Depends on:** Wave 21
**Blocks:** Waves 25, 26, 27

## Summary

Migrate the session orchestrator to use `phases.yaml` as the canonical phase source instead of the old PHASES dict in `helpers.py`. Resolves the dual-phase-system problem that blocks all Doc 1 features (live artifacts, ripple effects, phase-specific agents).

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Add missing fields to phases.yaml | 📋 Pending | Need `chat_agent`, `reentry`, `system_prompt` per phase |
| 2 | Migrate session orchestrator to phases.yaml | 📋 Pending | Replace `helpers.py` PHASES dict reference with PhaseBuilder |
| 3 | Remove old PHASES dict (or compatibility shim) | 📋 Pending | If removal is too much, shim is OK as intermediate step |
| 4 | Wire navigation rails on switch_to_phase() | 📋 Pending | Allowable source→destination transitions |
| 5 | Re-wire ContextLoader for phase-level bundles | 📋 Pending | Must read from phases.yaml instead of helpers dict |
| 6 | Tests | 📋 Pending | All ~3,800+ tests pass |

## Verification

Session orchestrator has zero references to `helpers.py` PHASES dict. All phase definitions from `phases.yaml`.
