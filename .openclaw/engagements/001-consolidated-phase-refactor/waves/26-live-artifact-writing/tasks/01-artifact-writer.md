# Task 1 — Build ArtifactWriter class

**Status:** 📋 Pending
**Wave:** 26-live-artifact-writing
**Dependencies:** Wave 22
**Effort:** 3-5h

## Description

Build `ArtifactWriter` class that writes phase artifacts immediately to `.harness/engagements/<slug>/artifacts/`. Not deferred. Supports: structured content (YAML), freeform text (Markdown), with metadata (phase, agent, timestamp).

## Acceptance Criteria

- [ ] ArtifactWriter class exists with write() method
- [ ] Artifacts written immediately, not buffered
- [ ] Metadata includes phase, agent role, timestamp
- [ ] Atomic writes (temp file → rename)
