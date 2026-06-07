# Task 4 — Move value objects to command/values.py

**Status:** ✅ Complete
**Wave:** 29-value-objects
**Dependencies:** Tasks 1-3
**Effort:** 0.5h

## Description

Currently value objects are in `domain/enums.py`. Per the typed command design, they should be in `command/values.py`. Move them: PhaseName, EngStatus, WaveId, SessionType, AutoMode, ReviewDecision, AbortMode, BranchStrategy. Update all imports.

## Acceptance Criteria

- [ ] All value objects in command/values.py
- [ ] All imports updated
- [ ] Tests pass
