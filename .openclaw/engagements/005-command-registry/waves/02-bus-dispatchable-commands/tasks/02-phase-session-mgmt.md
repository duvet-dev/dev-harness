# Task 2 — Add `@register` to phase/session/management commands

**Status:** 📋 Pending
**Wave:** 02-bus-dispatchable-commands
**Dependencies:** Wave 01
**Effort:** 0.5h

## Description

Add `@register(...)` decorator to all phase, session, chat, init, and generic management commands.

Commands to annotate:

| REPL Name | Click Function | cmd_cls | handler | arg_parser |
|-----------|---------------|---------|---------|------------|
| `enter-phase` | `enter_phase` | `EnterPhaseCommand` | `EnterPhaseTypedHandler()` | lambda |
| `phase` | `manage_phase` | `ManagePhaseCommand` | `PhaseManagementTypedHandler()` | `_phase_args` |
| `session` | `session` | `SessionCommand` | `SessionTypedHandler()` | `_session_args` |
| `chat` | `chat` | `ChatCommand` | `ChatTypedHandler()` | `_chat_args` |
| `work` | `work` | `CreateEngagementCommand` | `CreateEngagementHandler()` | `_work_args` |
| `init` | `init` | `InitProjectCommand` | `InitProjectTypedHandler()` | lambda |
| `finish` | `finish` | `FinishEngagementCommand` | `FinishEngagementTypedHandler()` | `_finish_args` |
| `review` | `review` | `ReviewEngagementCommand` | `ReviewEngagementTypedHandler()` | `_review_args` |

## Acceptance Criteria

- [x] All 8 commands have `@register(name="...", cmd_cls=..., handler=..., arg_parser=...)`
- [x] `work` uses `CreateEngagementCommand` / `CreateEngagementHandler()` — maps to same handler as `engagement create` (confirmed: `register_bus_handlers` skips duplicates)
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
for name in ['enter-phase', 'phase', 'session', 'chat', 'work', 'init', 'finish', 'review']:
    r = REGISTRY.get(name)
    status = f'cmd={r.cmd_cls.__name__:30s} handler={\"yes\" if r.handler else \"no\":3s}' if r else 'MISSING'
    print(f'  /{name:20s} {status}')
"
```
