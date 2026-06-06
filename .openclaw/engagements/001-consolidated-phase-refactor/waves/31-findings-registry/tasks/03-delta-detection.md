# Task 3 — Add delta detection

**Status:** 📋 Pending
**Wave:** 31-findings-registry
**Dependencies:** Task 1
**Effort:** 1h

## Description

On each analysis run, compare registry against current state:
- **New**: Not in registry → added as `open`
- **Resolved**: Previously `open`, no longer detected → `resolved`
- **Regression**: Previously `resolved`, detected again → `regression`
- **Wont-fix regression**: Previously `wont_fix`, detected again → flag for human review

## Acceptance Criteria

- [ ] Delta detection runs after each analysis
- [ ] New findings added with auto-generated IDs
- [ ] Resolved findings marked resolved
- [ ] Regressions flagged
- [ ] Delta summary available
