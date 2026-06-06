# Wave 22 — Phase System Consolidation

**Milestone:** 1 — Foundation
**Effort:** 5-8h
**Status:** ✅ Complete
**Depends on:** Wave 21
**Blocks:** Waves 25, 26, 27

## Summary

Migrate the session orchestrator to use `phases.yaml` as the canonical phase source instead of the old PHASES dict in `helpers.py`. Resolves the dual-phase-system problem that blocks all Doc 1 features (live artifacts, ripple effects, phase-specific agents).

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Add missing fields to phases.yaml | ✅ Complete | Added title, reentry, system_prompt per phase |
| 2 | Migrate session orchestrator to phases.yaml | ✅ Complete | PhaseSource bridges phases.yaml → session dict format |
| 3 | Remove old PHASES dict (or compatibility shim) | ✅ Complete | Replaced with PhaseSource + alias-driven resolve_phase() |
| 4 | Wire navigation rails on switch_to_phase() | ✅ Complete | is_transition_allowed() validates source→destination |
| 5 | Re-wire ContextLoader for phase-level bundles | ✅ Complete | ContextLoader was already independent of helpers.py |
| 6 | Tests | ✅ Complete | 3826 pass (3819 existing + 7 new), 0 failures |

## Verification

Session orchestrator has zero references to `helpers.py` PHASES dict. All phase definitions from `phases.yaml`.
