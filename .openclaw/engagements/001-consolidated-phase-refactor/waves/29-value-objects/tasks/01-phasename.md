# Task 1 — Add PhaseName value object

**Status:** ✅ Complete
**Wave:** 29-value-objects
**Dependencies:** None
**Effort:** 0.5h

## Description

Add `PhaseName` value object with validation. Rejects invalid phase names at construction. Valid set: requirements, design, build, review, test. Move to `command/values.py`.

## Acceptance Criteria

- [ ] PhaseName class with validation
- [ ] Invalid names raise ValueError
- [ ] Used instead of plain strings where appropriate
