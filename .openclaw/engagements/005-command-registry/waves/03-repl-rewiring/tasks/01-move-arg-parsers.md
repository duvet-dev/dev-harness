# Task 1 — Move arg parsers from repl.py to _registration.py

**Status:** 📋 Pending
**Wave:** 03-repl-rewiring
**Dependencies:** Wave 02
**Effort:** 0.25h

## Description

Move all 16 arg parser functions from `repl.py` to `_registration.py`. This breaks the circular import risk: `main.py` needs to import arg parsers (for `@register`'s `arg_parser=` parameter), and `repl.py` needs to import from `_registration.py` — but if arg parsers live in `repl.py`, that would be a circular dependency.

By moving them to `_registration.py`, both `main.py` and `repl.py` can import them from there.

Functions to move:

| Function | Purpose |
|----------|---------|
| `_no_args` | Returns empty dict |
| `_single_arg` | Returns `{"slug": args[0]}` |
| `_engagement_create_args` | Parses `engagement create` arguments |
| `_session_args` | Parses `/session` arguments |
| `_chat_args` | Parses `/chat` arguments |
| `_phase_args` | Parses `/phase` arguments |
| `_work_args` | Parses `/work` arguments |
| `_init_args` | Parses `/init` arguments |
| `_run_wave_args` | Parses `wave run` arguments |
| `_finish_args` | Parses `/finish` arguments |
| `_review_args` | Parses `/review` arguments |
| `_summary_args` | Parses `/summary` arguments |
| `_inspect_args` | Parses `/inspect` arguments |
| `_assess_args` | Parses `/assess` arguments |
| `_create_wave_from_assessment_args` | Parses `wave create-from-assessment` arguments |
| `_create_wave_from_finding_args` | Parses `wave create-from-finding` arguments |

## Acceptance Criteria

- [ ] All 16 parser functions moved to `src/harness/command/_registration.py`
- [ ] Functions maintain exact same signatures and behaviour — no refactoring
- [ ] `repl.py` imports parsers from `_registration.py` instead of defining them
- [ ] All imports in `main.py` are updated to import from `_registration.py`
- [ ] No circular import: `_registration.py` imports `TypedCommand` from `harness.command.types` (already done), parsers don't need any other imports from repl.py

## Files Affected

- `src/harness/command/_registration.py` (add parser functions)
- `src/harness/shell/repl.py` (remove parser functions, add imports)

## Verification

```bash
python -c "
from harness.command._registration import _single_arg, _engagement_create_args, _no_args
print(f'_single_arg([\"test\"]): {_single_arg([\"test\"])}')
print(f'_no_args([]): {_no_args([])}')
"
```
