# Task 2 — Wire ripple detection into phase transition

**Status:** ✅ Complete
**Wave:** 25-wire-ripple-engine
**Dependencies:** Task 1, Wave 22
**Effort:** 1-2h

## Description

After a phase completes, call `WorkflowRippleEngine.detect_ripple()` to check if the change affects downstream phases. If so, mark affected phases as needing update.

## Acceptance Criteria

- [x] `determine_transition()` called after phase completion (enter + advance)
- [x] `determine_ripple_effects()` called after successful phase completion
- [x] Downstream phases flagged via RippleEffect objects
- [x] Artifact tracking via `_artifact_map`
