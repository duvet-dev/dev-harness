# Task 5 — Re-wire ContextLoader for phase-level bundles

**Status:** ✅ Complete
**Wave:** 22-phase-system-consolidation
**Dependencies:** Task 2
**Effort:** 1h

## Description

ContextLoader currently reads phase bundle configuration from helpers.py. Update it to read from `phases.yaml` instead, ensuring 3-tier context bundles are generated correctly for the unified phase model.

## Acceptance Criteria

- [x] ContextLoader already operates independently of helpers.py
- [x] 3-tier bundles still work (3819 tests pass)
- [x] No references to old helpers.py config from ContextLoader — verified
- [x] Phase-level context bundles now driven by phases.yaml via PhaseSource

## Files Affected

- `src/harness/context/loader.py`

## Verification

`harness session --context-tier 2` works as before with the unified phase model.
