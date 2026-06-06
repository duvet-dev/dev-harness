# Wave 24 — Wire Refactoring-Analyser + Rename Constants

**Milestone:** 2 — Quick Wins
**Effort:** 3-5h
**Status:** ✅ Complete
**Depends on:** None
**Blocks:** Nothing

## Summary

The refactoring-analyser (`P11_REFACTORING_ANALYSER` / `REFACTORING_ANALYSER`) was already wired in `assessment.py` — `_run_refactoring_analysis()` exists, scheduled parallel with P10, findings merged via `_merge_agent_output()`, included in synthesis. All opaque P1/P2/.../P11 constant prefixes renamed to descriptive names throughout the codebase.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Add `_run_refactoring_analysis()` in analysis/deep.py | ✅ Complete | Already existed in assessment.py |
| 2 | Schedule refactoring-analyser parallel with critical-reviewer | ✅ Complete | Already scheduled in assess() |
| 3 | Add refactoring-analyser findings merger | ✅ Complete | Already handled in `_merge_agent_output()` |
| 4 | Include refactoring proposals in synthesis output | ✅ Complete | Synthesis iterates all agent results |
| 5 | Rename P1-P11 constant prefixes to descriptive names | ✅ Complete | All P-constants removed from src/ and tests/ |
| 6 | Tests | ✅ Complete | 1 new refactoring-analyser merge test, all 3827 pass |

## Verification

```bash
grep -rn "P1_\|P2_\|P3_\|P4_\|P5_\|P6_\|P7_\|P8_\|P10_\|P11_" src/ tests/ --include="*.py"
# → zero hits
```

Refactoring-analyser wired: `_run_refactoring_analysis()` in assessment.py, scheduled parallel with critical-reviewer in assess(), merged in `_merge_agent_output()`, refactoring proposals included in synthesis output.
