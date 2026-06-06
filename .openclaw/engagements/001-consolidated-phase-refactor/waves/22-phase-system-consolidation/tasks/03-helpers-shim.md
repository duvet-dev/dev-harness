# Task 3 — Remove or shim old PHASES dict

**Status:** 📋 Pending
**Wave:** 22-phase-system-consolidation
**Dependencies:** Task 2
**Effort:** 1-2h

## Description

The old PHASES dict in `helpers.py` is now unused. Delete it entirely if the change is clean. If there are other references, leave a minimal compatibility shim with a deprecation warning to be removed in a subsequent wave.

## Acceptance Criteria

- [ ] Old PHASES dict either deleted or replaced with a deprecation shim
- [ ] If shim used, it has a `DeprecationWarning` noting removal target
- [ ] Zero references to old PHASES dict from orchestrator or workflow code

## Files Affected

- `src/harness/session/helpers.py`

## Verification

```bash
grep "PHASES\|phase.get" src/harness/session/helpers.py
# → zero hits (or only deprecation shim)
```
