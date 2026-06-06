# Task 2 — Wire synthesis to persist findings

**Status:** 📋 Pending
**Wave:** 31-findings-registry
**Dependencies:** Task 1
**Effort:** 1h

## Description

Replace the current one-shot analysis report with FindingsStore writes. Synthesis agent writes each finding to the registry with an auto-generated ID. Findings accumulate across analysis runs.

## Acceptance Criteria

- [ ] Synthesis writes findings to registry
- [ ] Each finding gets a stable ID
- [ ] One-shot report still generated but also persisted to registry
