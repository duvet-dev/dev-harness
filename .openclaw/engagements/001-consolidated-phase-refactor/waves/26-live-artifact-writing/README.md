# Wave 26 — Live Artifact Writing

**Milestone:** 4 — Architecture Features
**Effort:** 8-12h
**Status:** 📋 Pending
**Depends on:** Wave 22
**Blocks:** Nothing

## Summary

Phase artifacts are currently written only at phase END (`_write_phase_artifact()` at `session/helpers.py:608`). They must be written immediately so that reviewers can see output in real time and compaction doesn't lose intermediate work.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Build ArtifactWriter class | 📋 Pending | Writes immediately, not deferred |
| 2 | Wire into session orchestrator | 📋 Pending | Artifacts persist mid-session |
| 3 | Wire into phase loop | 📋 Pending | After each creator step in a critic loop |
| 4 | Tests | 📋 Pending | Artifact observable mid-phase, not just end-of-phase |

## Verification

Artifact files exist at `.harness/engagements/<slug>/artifacts/` before a phase completes.
