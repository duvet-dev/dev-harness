# Task 5 — Wire wave-plan to declare resolved findings

**Status:** 📋 Pending
**Wave:** 31-findings-registry
**Dependencies:** Task 1
**Effort:** 0.5h

## Description

Allow wave definitions to declare which findings they resolve: `resolves: ["F-001", "F-003"]`. When a wave completes, those findings are automatically marked as resolved in the registry.

## Acceptance Criteria

- [ ] Wave metadata supports `resolves:` field
- [ ] On wave completion, listed findings automatically resolved
- [ ] Requires human sign-off still respected if set
