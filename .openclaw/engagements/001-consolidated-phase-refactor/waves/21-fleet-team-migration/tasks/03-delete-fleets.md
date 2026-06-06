# Task 3 — Delete fleets.yaml + update paths.py

**Status:** ✅ Complete
**Wave:** 21-fleet-team-migration
**Dependencies:** None
**Effort:** 1h

## Description

Delete `.harness/fleets.yaml`. Remove `_FLEETS_FILE` constant and `get_fleets_path()` function from `paths.py`.

## Acceptance Criteria

- [x] `.harness/fleets.yaml` deleted
- [x] `_FLEETS_FILE` removed from paths.py
- [x] `get_fleets_path()` removed from paths.py

## Files Affected

- `.harness/fleets.yaml` (deleted)
- `src/harness/paths.py`

## Verification

`ls .harness/fleets.yaml 2>/dev/null` → "No such file"
`grep "FLEETS\|fleets.yaml\|get_fleets_path" src/harness/paths.py` → zero hits
