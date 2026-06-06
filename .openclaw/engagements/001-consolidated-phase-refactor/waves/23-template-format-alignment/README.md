# Wave 23 — Template Format Alignment

**Milestone:** 2 — Quick Wins
**Effort:** 4-6h
**Status:** ✅ Complete
**Depends on:** After Wave 21 (preferable)
**Blocks:** Nothing

## Summary

Fix 7 format gaps between `phases.yaml` inline steps and `step_templates.yaml`. Quick wins that improve correctness immediately.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | FMT-1: Add `input:` to all 9 simple templates | ✅ Complete | Templates can't participate in data-flow without it |
| 2 | FMT-5: Add `loop:` example to phases.yaml | ✅ Complete | Exercise the critic loop code path that's currently untested |
| 3 | FMT-2: Update Step.role docstring | ✅ Complete | Document loop-only semantics |
| 4 | FMT-4: Add sub_steps to LoopConfig | ✅ Complete | Remove context-injection hack from template_registry and step_executor |
| 5 | Deprecate input_artifact_names / output_artifact_name | ✅ Complete | Duplicates of input/output from Step |
| 6 | Tests | ✅ Complete | |

## Verification

All simple templates have `input:` declarations. `loop:` step exists in phases.yaml. `sub_steps` field on LoopConfig.
