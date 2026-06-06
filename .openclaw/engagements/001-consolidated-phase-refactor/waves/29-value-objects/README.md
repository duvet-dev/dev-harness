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
| 1 | Add PhaseName value object with validation | 📋 Pending | Reject invalid phase names at construction |
| 2 | Add EngStatus enum | 📋 Pending | created, in_progress, completed, aborted |
| 3 | Add WaveId value object | 📋 Pending | id: str, title: str |
| 4 | Move value objects to command/values.py | 📋 Pending | Or keep in domain/enums.py — decide and be consistent |
| 5 | Expand ReplPresenter formatting | 📋 Pending | Type-specific formatting for all result types |
| 6 | Tests | 📋 Pending | |

## Verification

`grep "PhaseName\|EngStatus\|WaveId" src/harness/domain/` → exists and used.
