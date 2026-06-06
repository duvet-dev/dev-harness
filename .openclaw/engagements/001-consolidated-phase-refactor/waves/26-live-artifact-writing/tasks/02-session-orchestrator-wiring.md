# Task 2 — Wire into session orchestrator

**Status:** 📋 Pending
**Wave:** 26-live-artifact-writing
**Dependencies:** Task 1, Wave 22
**Effort:** 2-3h

## Description

Wire `ArtifactWriter` into the session orchestrator so artifacts are written immediately during an active session, not deferred to phase end. Replace `_write_phase_artifact()` in helpers.py.

## Acceptance Criteria

- [ ] Artifacts persist during active session
- [ ] Session output shows live artifact paths
- [ ] Compaction does not lose artifact state
