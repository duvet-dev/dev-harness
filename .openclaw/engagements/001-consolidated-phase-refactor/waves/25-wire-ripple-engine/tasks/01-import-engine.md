# Task 1 — Import WorkflowRippleEngine into orchestrator

**Status:** ✅ Complete
**Wave:** 25-wire-ripple-engine
**Dependencies:** Wave 22
**Effort:** 1h

## Description

Import `WorkflowRippleEngine` from `workflow/ripple_engine.py` into either `workflow/orchestrator.py` or `phase/orchestrator.py` so it can be used during phase transitions.

## Acceptance Criteria

- [x] `WorkflowRippleEngine` imported in `workflow/orchestrator.py`
- [x] Instantiated in `WorkflowOrchestrator.__init__()`
- [x] No circular import issues
