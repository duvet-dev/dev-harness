# Task 2 — Add empty-REGISTRY warning to builder functions

**Status:** 📋 Pending
**Wave:** 01-registration-infrastructure
**Dependencies:** Task 1
**Effort:** 0.25h

## Description

Per Crichton implementation note #4: document the import ordering constraint and add a warning in builder functions when REGISTRY is empty. If `main.py` hasn't been imported first, `REGISTRY` will be empty, and the builder functions would silently produce no-op results.

Add a `import warnings` check in both `build_repl_command_map()` and `register_bus_handlers()` that warns when REGISTRY is empty (or was not yet populated by decorator execution). This provides a clear signal if the import order is violated in tests or scripts.

## Acceptance Criteria

- [x] `build_repl_command_map()` emits a warning when REGISTRY is empty
- [x] `register_bus_handlers()` emits a warning when REGISTRY is empty
- [x] Warning message is informative: mentions the import ordering constraint (`main.py` must be imported first)
- [x] Warning uses `warnings.warn()` (not print), so it's controllable via pytest `-W` flag
- [x] Functions still return/execute normally (warning, not raise) — retains backward compatibility during migration

## Files Affected

- `src/harness/command/_registration.py`

## Verification

```bash
python -c "
import warnings
warnings.simplefilter('always')
from harness.command._registration import build_repl_command_map, register_bus_handlers

# Warning should be emitted when REGISTRY is empty
map = build_repl_command_map()
print(f'Empty warning works: map={map}')
"
```
