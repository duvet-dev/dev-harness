# Task 1 — Add `@register` to engagement lifecycle commands

**Status:** ✅ Complete
**Wave:** 02-bus-dispatchable-commands
**Dependencies:** Wave 01
**Effort:** 0.5h

## Description

Add `@register(...)` decorator to all engagement lifecycle commands in `src/harness/cli/main.py`. These commands dispatch through the CommandBus.

Commands to annotate:

| REPL Name | Click Function | cmd_cls | handler | arg_parser |
|-----------|---------------|---------|---------|------------|
| `engagement create` | `create_engagement` | `CreateEngagementCommand` | `CreateEngagementHandler()` | `_engagement_create_args` |
| `engagement close` | `close_engagement` | `AbortEngagementCommand` | `AbortEngagementTypedHandler()` | `_single_arg` |
| `engagement rename` | `rename_engagement` | `RenameEngagementCommand` | `RenameEngagementTypedHandler()` | lambda |
| `engagement set-branch` | `set_branch` | `SetBranchCommand` | `SetBranchTypedHandler()` | lambda |
| `engagement fix` | `fix_engagement` | `FixEngagementCommand` | `FixEngagementTypedHandler()` | lambda |

## Acceptance Criteria

- [x] All 5 engagement lifecycle commands have `@register(name="...", cmd_cls=..., handler=..., arg_parser=...)`
- [x] Each `handler` argument uses the same handler class/instance pattern as `setup.py` currently does
- [x] Each `arg_parser` matches the existing parser from `COMMAND_TYPES` / `repl.py`
- [x] Decorator placement: right after Click decorators, before the function `def` (Click decorators must be outermost)
- [x] Handlers imported from their module paths (e.g., `CreateEngagementHandler` from `harness.command.handlers.engagement_handlers`)
- [x] All imports added to `main.py`

## Files Affected

- `src/harness/cli/main.py` (add decorators + imports)

## Template

```python
@engagement_group.command()
@click.argument("slug")
@register(
    name="engagement close",
    cmd_cls=AbortEngagementCommand,
    handler=AbortEngagementTypedHandler(),
    arg_parser=_single_arg,
)
def close_engagement(slug: str) -> None:
    ...
```

## Verification

```bash
# Import main and check REGISTRY
python -c "
from harness.command._registration import REGISTRY
from harness.cli import main
print('Engagement commands in REGISTRY:')
for name in sorted(REGISTRY):
    if name.startswith('engagement'):
        r = REGISTRY[name]
        print(f'  /{name:30s} cmd={r.cmd_cls.__name__ if r.cmd_cls else \"-\":30s} click_only={r.click_only}')
"
```
