# Task 3 — Update Step.role docstring

**Status:** 📋 Pending
**Wave:** 23-template-format-alignment
**Dependencies:** None
**Effort:** 0.1h

## Description

`Step.role` field has an old docstring "Agent role override for this step." Update to document that it has loop-only semantics (used in critic loop sub-steps only).

## Acceptance Criteria

- [ ] Docstring updated to reflect loop-only usage

## Files Affected

- `src/harness/phase/model.py` (line ~148, ~168)
