# Task 2 — Schedule refactoring-analyser parallel with critical-reviewer

**Status:** 📋 Pending
**Wave:** 24-wire-refactoring-analyser
**Dependencies:** Task 1
**Effort:** 0.5h

## Description

Schedule the refactoring-analyser to run in parallel with the critical-reviewer (after project-profiler→documentation-reviewer sequential phase, before synthesis).

## Acceptance Criteria

- [ ] Both agents dispatch concurrently
- [ ] Both outputs are available for synthesis
- [ ] No race conditions or shared state issues
