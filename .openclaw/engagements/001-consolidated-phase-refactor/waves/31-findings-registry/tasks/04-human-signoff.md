# Task 4 — Add human sign-off flag

**Status:** 📋 Pending
**Wave:** 31-findings-registry
**Dependencies:** Task 1
**Effort:** 0.5h

## Description

Add `requires_human_signoff` boolean to finding schema. When set, a finding stays in `resolved/pending_verification` status until a human confirms closure via CLI or explicit acknowledgment.

## Acceptance Criteria

- [ ] `requires_human_signoff` field in schema
- [ ] Findings with this flag show as `pending_verification` when auto-resolved
- [ ] Human can confirm via CLI command
- [ ] Only then does status become `resolved`
