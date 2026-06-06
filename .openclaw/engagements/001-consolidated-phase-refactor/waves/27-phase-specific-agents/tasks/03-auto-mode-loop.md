# Task 3 — Auto mode loop

**Status:** 📋 Pending
**Wave:** 27-phase-specific-agents
**Dependencies:** Wave 22
**Effort:** 1-2h

## Description

Implement auto mode for each phase: creator → critics → convergence check → validator. Loop runs until convergence or max iterations. Then stores artifacts and hands control to user or next phase.

## Acceptance Criteria

- [ ] Auto mode runs the loop automatically
- [ ] Convergence checked after each critic iteration
- [ ] Stops when clean or max iterations hit
- [ ] Artifacts persisted at each loop iteration
