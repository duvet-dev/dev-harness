# Wave 21 — Fleet→Team Migration

**Milestone:** 1 — Foundation
**Effort:** 6-10h
**Status:** ✅ Complete (2026-06-06)
**Built by:** Build Coordinator
**Verification:** `grep -rn "fleets" src/ tests/ .harness/` → zero hits. All tests pass.

## Summary

Migrated the entire `fleet` concept to `teams`. The codebase had `fleets.yaml` alongside `teams.yaml` with live code references throughout — session helpers, health service, paths, CLI, typed commands, tests. All migrated with zero regressions.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Rename `"fleets"` → `"teams"` in helpers.py PHASES dict | ✅ Complete | No-op — lookup already through TeamRegistry |
| 2 | Update health service | ✅ Complete | Replaced `get_fleets_path()` with TeamRegistry |
| 3 | Delete fleets.yaml + update paths.py | ✅ Complete | `_FLEETS_FILE` and `get_fleets_path()` removed |
| 4 | Rename CLI fleet group → team | ✅ Complete | 6 subcommands renamed, imports updated |
| 5 | Rename typed commands (FleetList → TeamList) | ✅ Complete | Handler, result, presenter, setup.py all updated |
| 6 | Update tests | ✅ Complete | All fleet → team references across test suite |
| 7 | Verification | ✅ Complete | Zero `fleets` hits, all 3,812 tests pass |

## Details

See `tasks/` for individual task files.
