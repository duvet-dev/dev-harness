# Wave 25 — Wire Ripple Engine

**Milestone:** 3 — Analysis Pipeline
**Effort:** 3-5h
**Status:** ✅ Complete
**Depends on:** Wave 22
**Blocks:** Nothing

## Summary

`workflow/ripple_engine.py` (633 lines, 21KB) is imported by **nothing**. Dead code. Wire it into the orchestrator chain so phase transitions trigger ripple detection and propagation.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Import WorkflowRippleEngine into orchestrator | ✅ Done | Imported into workflow/orchestrator.py |
| 2 | Wire ripple detection into phase transition logic | ✅ Done | determine_transition/ripple_effects called on phase completion |
| 3 | Add RippleEvent emission | ✅ Done | RippleEvent created and published via EventBus |
| 4 | Tests | ✅ Done | 6 new tests, 3747 total pass |

## Verification

```bash
grep "WorkflowRippleEngine" src/harness/workflow/orchestrator.py  # → imported and called
grep "RippleEvent" src/harness/workflow/orchestrator.py           # → emitted
make ci                                                           # → clean
```

### Results

```
$ grep -n "WorkflowRippleEngine\|RippleEvent" src/harness/workflow/orchestrator.py
23:from harness.domain.events import EventBus, RippleEvent
35:    WorkflowRippleEngine,
145:                events (e.g., RippleEvent).
151:        self._ripple_engine = WorkflowRippleEngine()
556:        RippleEvent is published via the event bus (if configured).
589:                # Emit RippleEvent via event bus if configured
592:                        RippleEvent(

$ make ci
3747 passed in 24.74s
All checks passed!
```
