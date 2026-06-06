# Task 1 — Rename "fleets" → "teams" in helpers.py PHASES dict

**Status:** ✅ Complete
**Wave:** 21-fleet-team-migration
**Dependencies:** None
**Effort:** 3-5h

## Description

Rename all `"fleets"` keys to `"teams"` in the PHASES dictionary at `src/harness/session/helpers.py`. This is a no-op because the lookup function resolves through TeamRegistry regardless of key name.

## Acceptance Criteria

- [x] All PHASES dict keys changed: lines 31, 61, 88, 120, 164, 203, 232, 257, 337, 376, 423
- [x] `phase.get("fleets", [])` at line 1075 changed to `phase.get("teams", [])`

## Files Affected

- `src/harness/session/helpers.py`

## Verification

`grep '"fleets"' src/harness/session/helpers.py` → zero hits
