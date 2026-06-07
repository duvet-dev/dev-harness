# Task 3 — Replace `COMMAND_TYPES` with `build_repl_command_map()`

**Status:** 📋 Pending
**Wave:** 03-repl-rewiring
**Dependencies:** Task 1
**Effort:** 0.5h

## Description

Delete the static `COMMAND_TYPES` dict (currently ~30 entries, ~200 lines) from `repl.py`. Replace it with a dynamically-generated command map produced by `build_repl_command_map()` from the REGISTRY.

In `HarnessREPL.__init__`:
```python
from harness.command._registration import build_repl_command_map
self._command_types = build_repl_command_map()
```

Replace all `COMMAND_TYPES` references in `repl.py` with `self._command_types`. Also update any code that imports `COMMAND_TYPES` from `repl.py` (check for `from harness.shell.repl import COMMAND_TYPES` across the codebase).

## Acceptance Criteria

- [x] Static `COMMAND_TYPES` dict deleted from `repl.py`
- [x] `HarnessREPL.__init__` calls `build_repl_command_map()` to populate `self._command_types`
- [x] All `COMMAND_TYPES` references replaced with `self._command_types`
- [x] No `from harness.shell.repl import COMMAND_TYPES` exists anywhere in the codebase
- [x] `build_repl_command_map()` excludes `click_only=True` entries (they're handled by the CLI-only fallback in Task 5)
- [x] The structure `dict[str, tuple[class, Callable]]` is identical — no dispatch logic changes needed
- [x] Existing tests pass (REPL tests need to handle the new instance-attribute pattern)

## Files Affected

- `src/harness/shell/repl.py`

## Verification

```bash
# Check COMMAND_TYPES is gone
grep -n "COMMAND_TYPES" src/harness/shell/repl.py
# → zero hits

# Verify REPL can still dispatch
python -c "
from harness.command._registration import REGISTRY, build_repl_command_map
from harness.cli import main  # populate REGISTRY
cm = build_repl_command_map()
print(f'REPL command map: {len(cm)} entries')
for name in sorted(cm):
    cls, parser = cm[name]
    print(f'  /{name:30s} {cls.__name__}')
"
```
