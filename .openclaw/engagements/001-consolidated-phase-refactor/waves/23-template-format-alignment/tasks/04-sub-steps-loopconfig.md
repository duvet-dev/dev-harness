# Task 4 — Add sub_steps to LoopConfig + remove context hack

**Status:** 📋 Pending
**Wave:** 23-template-format-alignment
**Dependencies:** None
**Effort:** 2-3h

## Description

Critic loop sub-steps are currently smuggled via context injection in `template_registry.py:55` and `step_executor.py:186-195`. Add a proper `sub_steps: list[Step]` field to `LoopConfig`, remove the context-injection hack, and wire the model-driven path.

## Acceptance Criteria

- [ ] `LoopConfig` has `sub_steps: list[Step]` field
- [ ] Context-injection code removed from template_registry and step_executor
- [ ] Critic loop templates in step_templates.yaml still expand correctly
- [ ] All tests pass

## Files Affected

- `src/harness/phase/model.py` (LoopConfig)
- `src/harness/phase/template_registry.py`
- `src/harness/phase/step_executor.py`

## Verification

```bash
grep -r "_template_sub_steps\|context.*smuggle\|context.*inject" src/harness/phase/
# → zero hits
```
