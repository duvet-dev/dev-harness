# Task 4 — Tests for Wave 25

**Status:** ✅ Complete
**Wave:** 25-wire-ripple-engine
**Dependencies:** Tasks 1-3
**Effort:** 0.5-1h

## Description

Ensure all existing tests pass. Add tests for: ripple detection on phase transitions, event emission, no false positives.

## Acceptance Criteria

- [x] All existing tests pass (3747 total)
- [x] 6 new tests in `TestRippleDetection`:
  - `test_ripple_detected_after_phase_complete`
  - `test_ripple_detected_after_advance`
  - `test_ripple_event_structure`
  - `test_transition_info_in_result`
  - `test_no_false_positive_ripple_on_non_phase_change`
  - `test_ripple_transition_info_on_failure`
