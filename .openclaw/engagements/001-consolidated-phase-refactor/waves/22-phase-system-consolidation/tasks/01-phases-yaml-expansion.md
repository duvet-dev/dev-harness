# Task 1 — Add missing fields to phases.yaml

**Status:** 📋 Pending
**Wave:** 22-phase-system-consolidation
**Dependencies:** Wave 21
**Effort:** 1-2h

## Description

Current `phases.yaml` has phase names and steps but is missing `lead_agent`, `chat_agent`, `reentry`, and `system_prompt` fields that the session orchestrator needs. Extract these from the old PHASES dict in `helpers.py` and add them to `phases.yaml`.

## Acceptance Criteria

- [ ] All phases in `phases.yaml` have `lead_agent`, `chat_agent`, `reentry` fields
- [ ] Values match what the old PHASES dict had
- [ ] No duplicate data — helpers.py becomes the secondary source

## Files Affected

- `.harness/phases.yaml`

## Verification

```bash
grep "lead_agent\|chat_agent\|reentry" .harness/phases.yaml | wc -l
# → at least 3 matches (one per phase)
```
