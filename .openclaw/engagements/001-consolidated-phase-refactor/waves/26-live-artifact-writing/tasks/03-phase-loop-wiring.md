# Task 3 — Wire into phase loop

**Status:** ✅ Complete
**Wave:** 26-live-artifact-writing
**Dependencies:** Task 1
**Effort:** 2-3h

## Description

Wire `ArtifactWriter` into the critic loop phase execution: after each `creator` step produces output, the artifact is written immediately. Reviewers/critics can see the latest artifact even while the phase is still in progress.

## Acceptance Criteria

- [ ] After creator step, artifact is on disk
- [ ] Critics read from latest artifact, not stale snapshot
- [ ] Loop iterations write new artifact versions
