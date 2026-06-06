# Task 2 — Wire ripple detection into phase transition

**Status:** 📋 Pending
**Wave:** 25-wire-ripple-engine
**Dependencies:** Task 1, Wave 22
**Effort:** 1-2h

## Description

After a phase completes, call `WorkflowRippleEngine.detect_ripple()` to check if the change affects downstream phases. If so, mark affected phases as needing update.

## Acceptance Criteria

- [ ] Ripple detection runs after phase completion
- [ ] Downstream phases flagged if affected
- [ ] No false positives for non-ripple changes
