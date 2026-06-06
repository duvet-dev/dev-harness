# Wave 25 — Wire Ripple Engine

**Milestone:** 3 — Analysis Pipeline
**Effort:** 3-5h
**Status:** 📋 Pending
**Depends on:** Wave 22
**Blocks:** Nothing

## Summary

`workflow/ripple_engine.py` (633 lines, 21KB) is imported by **nothing**. Dead code. Wire it into the orchestrator chain so phase transitions trigger ripple detection and propagation.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Import WorkflowRippleEngine into orchestrator | 📋 Pending | Either workflow/orchestrator.py or phase/orchestrator.py |
| 2 | Wire ripple detection into phase transition logic | 📋 Pending | After a phase completes, check for ripple effects |
| 3 | Add RippleEvent emission | 📋 Pending | On phase completion, emit events for downstream consumers |
| 4 | Tests | 📋 Pending | End-to-end detection and event flow |

## Verification

`grep -r "WorkflowRippleEngine\|RippleEvent" src/harness/workflow/orchestrator.py` → imported and wired.
