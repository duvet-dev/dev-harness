# Task 3 — Remove/update stale test references

**Status:** 📋 Pending
**Wave:** 04-dead-code-removal
**Dependencies:** Tasks 1-2
**Effort:** 0.5h

## Description

Update test files that reference the removed command/handler classes. These tests either:
- Test classes that have been deleted (dead code), or
- Import classes that no longer exist

**Tests to update:**

### 1. `tests/unit/command/test_typed_command_dispatch.py`
Contains 3 test classes for the dead commands:
- `TestResumeEngagementCommand` (lines 125-141) — `ResumeEngagementCommand` removed
- `TestCreateWaveCommand` (lines 337-355) — `CreateWaveCommand`/`CreateWaveResult` removed
- `TestExecuteStepCommand` (lines 358-370) — `ExecuteStepCommand` removed

**Action:** Delete these 3 test classes.

### 2. `tests/unit/command/test_handler_integration.py`
Contains 2 test methods for the dead commands:
- `test_create_wave_dispatches` — dispatches `CreateWaveCommand`
- `test_execute_step_dispatches` — dispatches `ExecuteStepCommand`

**Action:** Delete these 2 test methods (only their methods, not the entire test class if it contains other valid tests).

### 3. `tests/unit/cli/test_cli_commands.py`
Line 22 imports `CreateWaveCommand, ExecuteStepCommand` — neither is used in the rest of the file.

**Action:** Remove `CreateWaveCommand, ExecuteStepCommand,` from the import line (keep `RunWaveCommand`).

## Acceptance Criteria

- [ ] `TestResumeEngagementCommand` class deleted from `test_typed_command_dispatch.py`
- [ ] `TestCreateWaveCommand` class deleted from `test_typed_command_dispatch.py`
- [ ] `TestExecuteStepCommand` class deleted from `test_typed_command_dispatch.py`
- [ ] `test_create_wave_dispatches` method deleted from `test_handler_integration.py`
- [ ] `test_execute_step_dispatches` method deleted from `test_handler_integration.py`
- [ ] Unused `CreateWaveCommand, ExecuteStepCommand` removed from import in `test_cli_commands.py`
- [ ] No import errors across test suite
- [ ] Full test suite passes: `python -m pytest -q`

## Files Affected

- `tests/unit/command/test_typed_command_dispatch.py`
- `tests/unit/command/test_handler_integration.py`
- `tests/unit/cli/test_cli_commands.py`

## Verification

```bash
# Check no test references to removed classes
grep -rn "ResumeEngagement\|CreateWave[^F]\|ExecuteStep" tests/
# → Only expected: CreateWaveFromFinding, CreateWavesFromAssessment (valid)

# Full test suite
python -m pytest tests/ -q
# → all passing
```
