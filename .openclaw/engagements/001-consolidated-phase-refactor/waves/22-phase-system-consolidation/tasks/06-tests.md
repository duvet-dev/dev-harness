# Task 6 — Tests for Wave 22

**Status:** ✅ Complete
**Wave:** 22-phase-system-consolidation
**Dependencies:** Tasks 1-5
**Effort:** 1-2h

## Description

Ensure all existing tests pass with the unified phase model. Add tests specific to: loading from phases.yaml, navigation rail validation, ContextLoader re-wire.

## Acceptance Criteria

- [x] All 3,826 tests pass (3819 original + 7 new)
- [x] Tests for phases.yaml loading in test_helpers.py
- [x] Tests for navigation rail enforcement in test_helpers.py
- [x] ContextLoader already independent of helpers.py

## Verification

```bash
python -m pytest -q
# → all passing, no regressions
```
