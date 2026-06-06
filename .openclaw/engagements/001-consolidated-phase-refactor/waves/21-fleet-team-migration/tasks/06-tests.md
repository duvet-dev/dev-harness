# Task 6 — Update tests

**Status:** ✅ Complete
**Wave:** 21-fleet-team-migration
**Dependencies:** Tasks 1-5
**Effort:** 1-2h

## Description

Find and update all test references from `fleet` → `team` naming across the test suite.

## Acceptance Criteria

- [x] All test function names, class names, and string references updated
- [x] No test uses `fleet` in a way that references the old concept

## Files Affected

- Various test files (search broadly)

## Verification

`grep -r "fleet" tests/` → zero hits (for the migrated concept; false positives for unrelated fleet uses OK)
All tests pass
