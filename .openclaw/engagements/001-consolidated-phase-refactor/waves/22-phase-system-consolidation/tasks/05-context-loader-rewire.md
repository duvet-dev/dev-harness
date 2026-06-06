# Task 5 — Re-wire ContextLoader for phase-level bundles

**Status:** 📋 Pending
**Wave:** 22-phase-system-consolidation
**Dependencies:** Task 2
**Effort:** 1h

## Description

ContextLoader currently reads phase bundle configuration from helpers.py. Update it to read from `phases.yaml` instead, ensuring 3-tier context bundles are generated correctly for the unified phase model.

## Acceptance Criteria

- [ ] ContextLoader reads phase config from phases.yaml
- [ ] 3-tier bundles still work (Tier 1: tree, Tier 2: summaries, Tier 3: full snippets)
- [ ] No references to old helpers.py config from ContextLoader

## Files Affected

- `src/harness/context/loader.py`

## Verification

`harness session --context-tier 2` works as before with the unified phase model.
