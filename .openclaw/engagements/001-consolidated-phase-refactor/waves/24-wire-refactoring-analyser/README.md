# Wave 24 — Wire Refactoring-Analyser + Rename Constants

**Milestone:** 2 — Quick Wins
**Effort:** 3-5h
**Status:** 📋 Pending
**Depends on:** None
**Blocks:** Nothing

## Summary

The refactoring-analyser is fully defined at `analysis/agents.py:792-987` but never called. Dead code. Also rename all opaque P1/P2/.../P11 constant prefixes to descriptive names throughout the codebase.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Add `_run_refactoring_analysis()` in analysis/deep.py | 📋 Pending | |
| 2 | Schedule refactoring-analyser parallel with critical-reviewer | 📋 Pending | After project-profiler→documentation-reviewer, before synthesis |
| 3 | Add refactoring-analyser findings merger | 📋 Pending | In `_merge_agent_output()` |
| 4 | Include refactoring proposals in synthesis output | 📋 Pending | |
| 5 | Rename P1-P11 constant prefixes to descriptive names | 📋 Pending | In `analysis/agents.py` and all imports |
| 6 | Tests | 📋 Pending | |

## Verification

`grep -r "_REFACTORING_ANALYSER\|_run_refactoring_analysis" src/harness/analysis/` → wired into pipeline. Zero `P1_`/`P2_`/etc. constants remain.
