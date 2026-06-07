# Task 1 — Delete dead command classes + update import chains

**Status:** 📋 Pending
**Wave:** 04-dead-code-removal
**Dependencies:** Wave 03
**Effort:** 0.5h

## Description

Remove the 3 dead command dataclass definitions and their exports. These commands are wired to no UI (no CLI group/command, no COMMAND_TYPES entry, no @register decorator). They've already been unregistered from the bus (Wave 02).

**Commands to remove:**

1. `ResumeEngagementCommand` — in `src/harness/command/commands/engagement.py`
2. `CreateWaveCommand` — in `src/harness/command/commands/wave.py`
3. `ExecuteStepCommand` — in `src/harness/command/commands/wave.py`

## Acceptance Criteria

- [x] `ResumeEngagementCommand` dataclass removed from `engagement.py`
- [x] `CreateWaveCommand` dataclass removed from `wave.py`
- [x] `ExecuteStepCommand` dataclass removed from `wave.py`
- [x] Their corresponding `TypedResult` dataclasses also removed if they're unique to these commands (check: `ResumeEngagementResult`, `CreateWaveResult`, `ExecuteStepResult`)
- [x] `__init__.py` exports updated (if these classes were exported from `harness.command.commands`)
- [x] No import errors when importing main.py after removal
- [x] `test_cli_commands.py` import lines updated (line 22 currently imports CreateWaveCommand + ExecuteStepCommand)

## Files Affected

- `src/harness/command/commands/engagement.py`
- `src/harness/command/commands/wave.py`
- `src/harness/command/commands/__init__.py` (if exports exist)
- `tests/unit/cli/test_cli_commands.py`

## Verification

```bash
# Import test
python -c "
from harness.cli import main
from harness.command._registration import REGISTRY
print('No import errors after dead command removal')
for name in ['engagement resume', 'wave create', 'wave execute-step']:
    if name in REGISTRY:
        print(f'  WARNING: {name} still registered')
    else:
        print(f'  ✓ {name} not in REGISTRY')
"

# Check no imports point to removed classes
python -c "
import sys
sys.path.insert(0, 'src')
from harness.command.commands.engagement import (ResumeEngagementCommand)
" 2>&1 | grep -q "ImportError" && echo "✓ Import properly fails" || echo "WARNING: ResumeEngagementCommand still importable"
```
