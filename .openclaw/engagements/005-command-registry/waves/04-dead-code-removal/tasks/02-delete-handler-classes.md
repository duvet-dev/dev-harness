# Task 2 — Delete dead handler classes + update import chains

**Status:** 📋 Pending
**Wave:** 04-dead-code-removal
**Dependencies:** Task 1
**Effort:** 0.5h

## Description

Remove the 3 dead handler classes and their result models. These handlers were registered on the bus but wired to no UI. They've already been unregistered (Wave 02 removed the `bus.register_type()` calls), now remove the actual class definitions.

**Handlers to remove:**

1. `ResumeEngagementHandler` — in `src/harness/command/handlers/engagement_handlers.py`
   - Remove the class definition and its `ResumeEngagementResult` dataclass
   - Update the module docstring

2. `CreateWaveTypedHandler` — in `src/harness/command/handlers/wave_handlers.py`
   - Remove the class definition and its `CreateWaveResult` dataclass

3. `ExecuteStepTypedHandler` — in `src/harness/command/handlers/wave_handlers.py`
   - Remove the class definition and its `ExecuteStepResult` dataclass

## Acceptance Criteria

- [x] `ResumeEngagementHandler` class removed from `engagement_handlers.py`
- [x] `ResumeEngagementResult` dataclass removed from `engagement_handlers.py`
- [x] `CreateWaveTypedHandler` and `CreateWaveResult` removed from `wave_handlers.py`
- [x] `ExecuteStepTypedHandler` and `ExecuteStepResult` removed from `wave_handlers.py`
- [x] Module exports updated (if these were exported from `__init__.py`)
- [x] All dead-code-related imports removed from `setup.py` (already commented out in Wave 02, now fully delete)
- [x] No import errors after removal

## Files Affected

- `src/harness/command/handlers/engagement_handlers.py`
- `src/harness/command/handlers/wave_handlers.py`
- `src/harness/command/setup.py`
- `src/harness/command/handlers/__init__.py` (if exports exist)

## Verification

```bash
# Import test
python -c "
from harness.cli import main
print('No import errors after dead handler removal')
"

# Verify handlers can't be imported
for handler in ['ResumeEngagementHandler', 'CreateWaveTypedHandler', 'ExecuteStepTypedHandler']:
    python -c "
from harness.command.handlers.engagement_handlers import $handler
" 2>&1 | grep -q "ImportError" && echo "✓ $handler removed" || echo "WARNING: $handler still importable"
}
```
