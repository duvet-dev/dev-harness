# Task 4 — Wire navigation rails on switch_to_phase()

**Status:** 📋 Pending
**Wave:** 22-phase-system-consolidation
**Dependencies:** Task 2
**Effort:** 1h

## Description

`session_orchestrator.py:switch_to_phase()` currently allows jumping to any phase from any phase with no validation. Add navigation rails defining allowable source→destination transitions. Use the phase order from `phases.yaml` as the default rail.

## Acceptance Criteria

- [ ] Navigation rails defined per phase (which phases can be jumped to from here)
- [ ] Illegal transitions return a clear error message
- [ ] Default rails follow phase order from phases.yaml

## Files Affected

- `src/harness/session/session_orchestrator.py`

## Verification

Attempting to jump from `build` to `requirements` returns error. Jumping from `build` to `design` (one phase back) succeeds.
