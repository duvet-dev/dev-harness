# Task 6 — Remove stale arg parsers + unused imports from repl.py

**Status:** 📋 Pending
**Wave:** 03-repl-rewiring
**Dependencies:** Tasks 1-5
**Effort:** 0.25h

## Description

After moving arg parsers to `_registration.py`, some parser functions referenced by `repl.py`'s COMMAND_TYPES dict are no longer needed in repl.py. Clean up:

1. Remove arg parser function definitions (already moved to `_registration.py` in Task 1)
2. Remove unused imports that were only needed by COMMAND_TYPES or old /help generation
3. Remove any TypedCommand imports that are no longer used directly in repl.py
4. Remove dead code around help generation (old Click-tree-based code)
5. Clean up import organization

**Key:** Don't remove imports that are still used by remaining REPL code (dispatch logic, HarnessREPL methods, special commands handling).

## Acceptance Criteria

- [ ] All 16 arg parser function definitions are gone from `repl.py` (moved to `_registration.py`)
- [ ] Unused imports cleaned up — only imports used by remaining code stay
- [ ] No import errors or NameError when REPL starts
- [ ] REPL dispatch still works for all bus-dispatchable commands
- [ ] Commands like `/help`, `/exit`, `/version`, `/exec`, phase command pre-handling all still work
- [ ] Tab completion still works

## Files Affected

- `src/harness/shell/repl.py`

## Verification

```bash
# Verify repl.py imports are minimal
python -c "from harness.shell.repl import HarnessREPL; print('REPL imports OK')"

# Quick smoke test of all major REPL functions
python -c "
from harness.cli import main  # populate REGISTRY
from harness.shell.repl import HarnessREPL
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory() as tmp:
    repl = HarnessREPL(root=Path(tmp))
    # Test help generation
    help_lines = repl._build_help_from_registry()
    print(f'Help generated: {len(help_lines)} lines')
"

# Full test suite
python -m pytest tests/ -q
```
