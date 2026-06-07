# Task 3 — Add RippleEvent emission

**Status:** ✅ Complete
**Wave:** 25-wire-ripple-engine
**Dependencies:** Task 2
**Effort:** 0.5-1h

## Description

Emit `RippleEvent` objects when ripple effects are detected, containing: source phase, affected phases, type of change, impact summary. These events can be consumed by the session orchestrator or logged for user visibility.

## Acceptance Criteria

- [x] `RippleEvent` dataclass defined in `engagement_events.py`
- [x] Exported from `domain/events/__init__.py`
- [x] Published via `EventBus` from `WorkflowOrchestrator._detect_and_emit_ripple()`
- [x] Events visible to session orchestrator via EventBus subscription
- [x] RippleEvent fields: slug, source_phase, affected_phases, description, severity, detected_at
