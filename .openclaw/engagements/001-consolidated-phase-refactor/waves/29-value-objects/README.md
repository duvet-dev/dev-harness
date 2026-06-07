# Wave 29 — Value Objects & Type Cleanup

**Milestone:** 3 — Cleanup
**Effort:** 2-3h
**Status:** 📋 Pending
**Depends on:** None (independent)
**Blocks:** Nothing

## Summary

Add missing value objects from the typed command design: `PhaseName`, `EngStatus`, `WaveId`. Fix `ReplPresenter` type-specific formatting. Move value objects to `command/values.py`.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Add PhaseName value object with validation | ✅ Complete | Moved to command/values.py |
| 2 | Add EngStatus enum | ✅ Complete | In command/values.py |
| 3 | Add WaveId value object | ✅ Complete | In command/values.py |
| 4 | Move value objects to command/values.py | ✅ Complete | PhaseName, SessionType, AutoMode, ReviewDecision, AbortMode, BranchStrategy moved from domain/enums.py |
| 5 | Expand ReplPresenter formatting | 📋 Pending | Type-specific formatting for all result types |
| 6 | Tests | 📋 Pending | |

## Verification

`grep "PhaseName\|EngStatus\|WaveId" src/harness/domain/` → exists and used.
