# Task 3 — Create `test_registration.py` — 4 Sync Tests

**Status:** ✅ Complete
**Wave:** 01-registration-infrastructure
**Dependencies:** Task 1
**Effort:** 0.5h

## Description

Create `tests/unit/command/test_registration.py` with 4 sync tests that prevent registration drift. These tests will initially fail (no `@register` decorators applied yet), acting as a checklist for subsequent waves.

The `PURE_CLICK_EXEMPTIONS` set lists commands that don't need `@register` — `shell` (REPL built-in), `workflows` (pure help text), `team add-agent`, `team remove-agent` (informational YAML edit instructions).

## Acceptance Criteria

- [ ] File exists at `tests/unit/command/test_registration.py`
- [ ] `PURE_CLICK_EXEMPTIONS` includes `shell`, `workflows`, `team add-agent`, `team remove-agent`
- [ ] **Test 1: `test_all_cli_commands_registered`** — every Click CLI command has `@register` or is in `PURE_CLICK_EXEMPTIONS`
- [ ] **Test 2: `test_no_orphaned_registrations`** — no `@register` entry lacks a corresponding Click function
- [ ] **Test 3: `test_repl_map_instantiable`** — every REPL command's arg parser produces valid kwargs for its `TypedCommand`
  - [ ] Import all command classes needed for this test
  - [ ] Handles `_single_arg`, `_engagement_create_args`, `_session_args`, `_chat_args`, `_phase_args`, `_work_args`, `_init_args`, `_run_wave_args`, `_finish_args`, `_review_args`, and all lambda-based parsers
  - [ ] Uses `try: cls(**parser(sample))` to validate kwargs match
- [ ] **Test 4: `test_no_stale_bus_handlers`** — every bus handler has a matching `@register`
  - [ ] Creates a bus via `create_bus()`
  - [ ] Checks every registered handler type has a matching `@register` entry
- [ ] Helper function `_cli_commands()` walks the Click CLI tree and returns a flat `set[str]` of command names
- [ ] Tests are clearly documented with failure messages that guide remediation
- [ ] File is <100ms runtime, no IO

## Files Affected

- `tests/unit/command/test_registration.py` (new)

## Verification

```bash
# Tests should fail initially (no @register decorators yet) — that's expected
python -m pytest tests/unit/command/test_registration.py -v 2>&1 | head -40

# The test failure messages should list every command that needs @register
# Expected: ~35-39 missing commands depending on PURE_CLICK_EXEMPTIONS

# Once all waves are complete, all 4 tests should pass:
python -m pytest tests/unit/command/test_registration.py -v
# → 4 passed
```
