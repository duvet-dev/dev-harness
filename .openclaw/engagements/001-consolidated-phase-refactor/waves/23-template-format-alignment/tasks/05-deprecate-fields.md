# Task 5 — Deprecate input_artifact_names / output_artifact_name

**Status:** ✅ Complete
**Wave:** 23-template-format-alignment
**Dependencies:** None
**Effort:** 1h

## Description

`StepTemplate` has duplicate fields `input_artifact_names`/`output_artifact_name` alongside the inherited `input`/`output` from `Step`. Add deprecation warnings and migration path.

## Acceptance Criteria

- [x] `input_artifact_names`/`output_artifact_name` marked deprecated
- [x] Any code using them uses the canonical `input`/`output` instead
- [x] Tests updated

## Files Affected

- `src/harness/phase/template.py`
- Any consumers of these fields
