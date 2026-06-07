# Task 3 — Add `@register` to wave/changelog/governance commands

**Status:** ✅ Complete
**Wave:** 02-bus-dispatchable-commands
**Dependencies:** Wave 01
**Effort:** 0.5h

## Description

Add `@register(...)` decorator to all wave management, changelog, and governance commands.

Commands to annotate:

| REPL Name | Click Function | cmd_cls | handler | arg_parser |
|-----------|---------------|---------|---------|------------|
| `wave list` | `list_waves` | `ListWavesCommand` | `ListWavesTypedHandler()` | lambda |
| `wave run` | `run_wave` | `RunWaveCommand` | `RunWaveTypedHandler()` | `_run_wave_args` |
| `wave status` | `wave_status` | `WaveStatusCommand` | `WaveStatusTypedHandler()` | lambda |
| `wave create-from-assessment` | `create_waves_from_assessment` | `CreateWavesFromAssessmentCommand` | `CreateWavesFromAssessmentTypedHandler()` | `_create_wave_from_assessment_args` |
| `wave create-from-finding` | `create_wave_from_finding` | `CreateWaveFromFindingCommand` | `CreateWaveFromFindingTypedHandler()` | `_create_wave_from_finding_args` |
| `changelog annotate` | `annotate_changelog` | `AnnotateChangelogCommand` | `AnnotateChangelogTypedHandler()` | lambda |
| `team set-governance` | `set_governance` | `SetGovernanceCommand` | `SetGovernanceTypedHandler()` | lambda |

## Acceptance Criteria

- [x] All 7 commands have `@register(name="...", cmd_cls=..., handler=..., arg_parser=...)`
- [x] Each `handler` argument matches current setup.py instantiation pattern
- [x] Each `arg_parser` matches the existing parser from `COMMAND_TYPES`
- [x] All imports added to `main.py`

## Files Affected

- `src/harness/cli/main.py` (add decorators + imports)

## Verification

```bash
python -c "
from harness.command._registration import REGISTRY
from harness.cli import main
for prefix in ['wave', 'changelog', 'team set']:
    for name in sorted(REGISTRY):
        if name.startswith(prefix):
            r = REGISTRY[name]
            print(f'  /{name:30s} cmd={r.cmd_cls.__name__ if r.cmd_cls else \"-\":30s} handler={\"yes\" if r.handler else \"no\":3s}')
"
```
