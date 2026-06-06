# Task 5 — Rename P1-P11 constant prefixes

**Status:** ✅ Complete
**Wave:** 24-wire-refactoring-analyser
**Dependencies:** None
**Effort:** 1-2h

## Description

Rename all opaque constant prefixes in `analysis/agents.py` and all imports across the codebase:
- `P1_PROJECT_PROFILER` → `PROJECT_PROFILER`
- `P2_RESPONSIBILITY_DECODER` → `RESPONSIBILITY_DECODER`
- `P3_ARCHITECTURE_CRITIC` → `ARCHITECTURE_CRITIC`
- `P4_CODE_CRITIC` → `CODE_CRITIC`
- `P5_TEST_AUDITOR` → `TEST_AUDITOR`
- `P6_SECURITY_AUDITOR` → `SECURITY_AUDITOR`
- `P7_DEPENDENCY_ANALYSER` → `DEPENDENCY_ANALYSER`
- `P8_DOCUMENTATION_REVIEWER` → `DOCUMENTATION_REVIEWER`
- `P10_CRITICAL_REVIEWER` → `CRITICAL_REVIEWER`
- `P11_REFACTORING_ANALYSER` → `REFACTORING_ANALYSER`

## Acceptance Criteria

- [ ] Zero P1/P2/P3/P4/P5/P6/P7/P8/P10/P11 prefixed constants in analysis/agents.py
- [ ] All imports updated across the codebase
- [ ] Tests pass

## Verification

```bash
grep -rn "P1_\|P2_\|P3_\|P4_\|P5_\|P6_\|P7_\|P8_\|P10_\|P11_" src/ tests/ --include="*.py"
# → zero hits
```
