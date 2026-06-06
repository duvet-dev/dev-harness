# Task 2 — Migrate session orchestrator to phases.yaml

**Status:** 📋 Pending
**Wave:** 22-phase-system-consolidation
**Dependencies:** Task 1
**Effort:** 2-3h

## Description

Session orchestrator currently loads phase definitions from the old PHASES dict in `helpers.py`. Migrate it to load from `phases.yaml` via `PhaseBuilder`. The old PHASES dict becomes unused.

## Acceptance Criteria

- [ ] Session orchestrator loads phase definitions from `phases.yaml`
- [ ] Phase metadata (lead_agent, chat_agent, system_prompt) reads from YAML
- [ ] Step definitions read from YAML
- [ ] All session lifecycle commands work identically

## Files Affected

- `src/harness/session/session_orchestrator.py`
- `src/harness/session/helpers.py`

## Verification

`grep -c "phase.get\|PHASES" src/harness/session/orchestrator.py` → zero hits
