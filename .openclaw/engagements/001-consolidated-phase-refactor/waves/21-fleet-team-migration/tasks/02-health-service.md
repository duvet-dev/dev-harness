# Task 2 — Update health service

**Status:** ✅ Complete
**Wave:** 21-fleet-team-migration
**Dependencies:** None
**Effort:** 1-2h

## Description

Update `application/services/health_service.py` to use TeamRegistry instead of `get_fleets_path()` for agent role validation.

## Acceptance Criteria

- [x] No references to `get_fleets_path()` remain
- [x] Agent role validation uses TeamRegistry

## Files Affected

- `src/harness/application/services/health_service.py`

## Verification

`grep "fleet" src/harness/application/` → zero hits
