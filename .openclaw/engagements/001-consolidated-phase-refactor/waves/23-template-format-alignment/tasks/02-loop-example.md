# Task 2 — Add loop: example to phases.yaml

**Status:** ✅ Complete
**Wave:** 23-template-format-alignment
**Dependencies:** None
**Effort:** 0.5h

## Description

No inline phase step uses `loop:` — the critic loop code path is untested. Add a `loop:` usage example to one phase in `phases.yaml`.

## Acceptance Criteria

- [x] One phase in `phases.yaml` has a `loop:` step with convergence config
- [x] The model supports it but the YAML doesn't exercise it — now it does

## Files Affected

- `.harness/phases.yaml`
