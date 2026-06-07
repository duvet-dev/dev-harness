# Task 2 — Add `@register(click_only=True)` to all Click-only commands

**Status:** 📋 Pending
**Wave:** 03-repl-rewiring
**Dependencies:** Wave 02
**Effort:** 0.5h

## Description

Add `@register(name="...", click_only=True)` to all Click-only commands that have no TypedCommand/handler. These commands exist only in the Click CLI; calling them from the REPL should show a "CLI only" message (implemented in Task 5).

Commands to annotate:

| REPL Name | Click Function | Current Status |
|-----------|---------------|----------------|
| `engagement list` | `list_engagements` | Pure Click — file listing |
| `engagement diff` | `engagement_diff` | Pure Click — git diff |
| `engagement engagement-status` | `engagement_status_cmd` | Pure Click — status display |
| `engagement set-active` | `set_active_engagement` | Pure Click — writes to yaml |
| `agent show` | `show_agent` | Pure Click — file display |
| `team show` | `show_team` | Pure Click — file display |
| `team consult` | `consult_team` | Pure Click — inline logic |
| `health` | `health` | Pure Click — system check |
| `workflows` | `workflows` | Pure Click — help text display |
| `team add-agent` | `add_agent` | Pure Click — informational yaml edit instruction |
| `team remove-agent` | `remove_agent` | Pure Click — informational yaml edit instruction |

**Note:** `shell` is handled before the CommandBus dispatch block — it's a REPL built-in, not a Click-only command. No `@register` needed.

## Acceptance Criteria

- [ ] All 11 Click-only commands have `@register(name="...", click_only=True)`
- [ ] No `cmd_cls`, `handler`, or `arg_parser` provided — `click_only=True` is sufficient
- [ ] Decorator applied to the correct Click function in `main.py`
- [ ] `workflows` entry is NOT in PURE_CLICK_EXEMPTIONS anymore (now has @register so sync test passes)
- [ ] `team add-agent` and `team remove-agent` also get @register (remove from PURE_CLICK_EXEMPTIONS)
- [ ] `shell` remains in PURE_CLICK_EXEMPTIONS (still has no @register)
- [ ] All 4 sync tests now pass: `test_all_cli_commands_registered` should have zero missing
- [ ] Existing test suite still passes

## Files Affected

- `src/harness/cli/main.py` (add decorators to Click-only commands)
- `tests/unit/command/test_registration.py` (update PURE_CLICK_EXEMPTIONS — remove workflows, team add-agent, team remove-agent)

## Verification

```bash
# Check sync test passes
python -m pytest tests/unit/command/test_registration.py -v
# → 4 passed

# Check all 39 CLI commands have @register (except shell)
python -c "
from harness.command._registration import REGISTRY
from harness.cli import main
from harness.cli import main as cli_main
# Count CLI commands
cli_cmds = set()
for name, cmd in cli_main.main.commands.items():
    if isinstance(cmd, click.Group):
        for sub in cmd.commands:
            cli_cmds.add(f'{name} {sub}')
    elif name != 'shell':  # exempt
        cli_cmds.add(name)

registered = set(REGISTRY.keys())
missing = cli_cmds - registered
if missing:
    print(f'MISSING: {sorted(missing)}')
else:
    print(f'All {len(cli_cmds)} CLI commands have @register. ✓')

click_only = [n for n, r in REGISTRY.items() if r.click_only]
print(f'Click-only: {sorted(click_only)}')
"
```
