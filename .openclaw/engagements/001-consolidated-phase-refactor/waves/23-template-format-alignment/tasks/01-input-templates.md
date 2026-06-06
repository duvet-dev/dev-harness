# Task 1 — Add input: to all simple templates

**Status:** 📋 Pending
**Wave:** 23-template-format-alignment
**Dependencies:** None
**Effort:** 0.5h

## Description

All 9 simple templates in `step_templates.yaml` lack `input:` declarations. Add them so templates can participate in data-dependency chaining.

## Acceptance Criteria

- [ ] All simple templates have declared `input:` dependencies
- [ ] Templates that produce from scratch have `input: null`

## Files Affected

- `.harness/step_templates.yaml`
