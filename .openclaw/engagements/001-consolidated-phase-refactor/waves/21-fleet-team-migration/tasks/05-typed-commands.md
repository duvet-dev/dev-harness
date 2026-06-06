# Task 5 — Rename typed commands (FleetList → TeamList)

**Status:** ✅ Complete
**Wave:** 21-fleet-team-migration
**Dependencies:** Task 4 (CLI rename)
**Effort:** 1-2h

## Description

Rename the typed command chain: `FleetListCommand` → `TeamListCommand`, `FleetListTypedHandler` → `TeamListTypedHandler`, `FleetListResult` → `TeamListResult`. Update presenter references and setup.py registration.

## Acceptance Criteria

- [x] Command class renamed
- [x] Handler class renamed
- [x] Result class renamed
- [x] Presenter references updated
- [x] setup.py registration updated
- [x] All imports updated

## Files Affected

- `src/harness/command/commands/mgmt.py`
- `src/harness/command/handlers/mgmt_handlers.py`
- `src/harness/command/results/mgmt.py`
- `src/harness/command/presenters/base.py`
- `src/harness/command/setup.py`
- `src/harness/cli/commands.py`

## Verification

`grep "FleetList\|fleet_list" src/harness/command/` → zero hits
`grep "TeamList\|team_list" src/harness/command/` → matches found
All tests pass
