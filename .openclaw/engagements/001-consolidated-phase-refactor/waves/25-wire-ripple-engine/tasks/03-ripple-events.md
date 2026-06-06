# Task 3 — Add RippleEvent emission

**Status:** 📋 Pending
**Wave:** 25-wire-ripple-engine
**Dependencies:** Task 2
**Effort:** 0.5-1h

## Description

Emit `RippleEvent` objects when ripple effects are detected, containing: source phase, affected phases, type of change, impact summary. These events can be consumed by the session orchestrator or logged for user visibility.

## Acceptance Criteria

- [ ] RippleEvent structure defined
- [ ] Events emitted on phase completion with ripple effects
- [ ] Events visible to session orchestrator
