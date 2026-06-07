# Task 5 — Replace setup.py registrations with `register_bus_handlers(bus)`

**Status:** ✅ Complete
**Wave:** 02-bus-dispatchable-commands
**Dependencies:** Tasks 1-4
**Effort:** 0.5h

## Description

Replace all explicit `bus.register_type(...)` calls in `setup.py` (currently ~40 lines across two registration blocks) with a single call to `register_bus_handlers(bus)`.

Remove or comment out the 3 dead handler registrations:
- `bus.register_type(ResumeEngagementHandler(), ResumeEngagementCommand)` — line 79
- `bus.register_type(CreateWaveTypedHandler(), CreateWaveCommand)` — line 85
- `bus.register_type(ExecuteStepTypedHandler(), ExecuteStepCommand)` — line 86

Also clean up imports in setup.py — remove handler/command imports that are only referenced by the dead registrations (ResumeEngagementHandler, CreateWaveTypedHandler, ExecuteStepTypedHandler, ResumeEngagementCommand, CreateWaveCommand, ExecuteStepCommand) if they're not used elsewhere.

## Acceptance Criteria

- [x] `_build_bus()` uses `register_bus_handlers(bus)` instead of individual `bus.register_type()` calls
- [x] All 27 valid handler registrations are still active (30 bus-dispatchable minus `work` which shares `CreateEngagementHandler`/`CreateEngagementCommand` — checked for duplication)
- [x] 3 dead handler registrations are removed/commented out with a clear `# DEAD: no @register — to be removed in Wave 04` comment
- [x] Import lines for dead handlers/commands are removed or commented out
- [x] Existing test suite passes

## Files Affected

- `src/harness/command/setup.py`

## Verification

```bash
# Verify no stale bus registrations remain
python -c "
from harness.command._registration import REGISTRY, register_bus_handlers
from harness.cli import main  # populate REGISTRY
from harness.command.setup import _build_bus

bus = _build_bus()
non_click_only = set(id for id, r in REGISTRY.items() if r.cmd_cls)
registered_types = set(bus._type_handlers.keys())

# Check: every handler type in REGISTRY is on the bus
for r in REGISTRY.values():
    if r.cmd_cls and r.cmd_cls not in bus._type_handlers:
        print(f'MISSING on bus: {r.cmd_cls.__name__} ({r.name})')

# Check: every bus handler has a @register
for cmd_cls in registered_types:
    found = any(r.cmd_cls == cmd_cls for r in REGISTRY.values())
    if not found:
        print(f'STALE on bus: {cmd_cls.__name__}')

print(f'REGISTRY: {len([r for r in REGISTRY.values() if r.cmd_cls])} bus-cmds')
print(f'Bus handlers: {len(registered_types)}')
print('All consistent!' if all(r.cmd_cls in bus._type_handlers for r in REGISTRY.values() if r.cmd_cls) else 'ISSUES FOUND')
"

# Full test suite
python -m pytest tests/ -q
```
