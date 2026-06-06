# Task 6 — Tests for Wave 22

**Status:** 📋 Pending
**Wave:** 22-phase-system-consolidation
**Dependencies:** Tasks 1-5
**Effort:** 1-2h

## Description

Ensure all existing tests pass with the unified phase model. Add tests specific to: loading from phases.yaml, navigation rail validation, ContextLoader re-wire.

## Acceptance Criteria

- [ ] All ~3,800 existing tests pass
- [ ] Tests for phases.yaml loading
- [ ] Tests for navigation rail enforcement
- [ ] Tests for ContextLoader with unified model

## Verification

```bash
python -m pytest -q
# → all passing, no regressions
```
