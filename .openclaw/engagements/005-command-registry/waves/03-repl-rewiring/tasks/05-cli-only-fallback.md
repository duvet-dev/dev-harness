# Task 5 — Add "CLI only" fallback to REPL dispatch

**Status:** ✅ Complete
**Wave:** 03-repl-rewiring
**Dependencies:** Task 3
**Effort:** 0.25h

## Description

Per Crichton note #1: Add a fallback in the REPL dispatch loop that checks for `click_only=True` commands and shows a helpful "CLI only" message instead of "Unknown command."

Currently, when a command isn't found in `COMMAND_TYPES` (now `build_repl_command_map()`), the REPL falls through to "Unknown command." Since Click-only commands have `@register(click_only=True)`, they exist in `REGISTRY` but not in the REPL map. Add a second lookup against raw `REGISTRY` entries:

```python
# In HarnessREPL._run_command(), after the main dispatch block:

if not dispatched:
    # Check if it's a Click-only command
    from harness.command._registration import REGISTRY
    if candidate in REGISTRY and REGISTRY[candidate].click_only:
        click.echo(f"CLI only — use the CLI: `harness {candidate}`")
        return Result(success=True, output="")
    else:
        click.echo(f"Unknown command: /{cmd_name}")
```

## Acceptance Criteria

- [x] Typing a `click_only=True` command in the REPL shows: `"CLI only — use the CLI: \`harness <command>\`"`
- [x] Typing a truly unknown command still shows: `"Unknown command: /<cmd_name>"`
- [x] Typing a bus-dispatchable command still dispatches normally
- [x] The fallback is after the main dispatch loop (so bus-dispatchable commands take priority)
- [x] ~5 lines of code

## Files Affected

- `src/harness/shell/repl.py`

## Verification

```bash
# Test Click-only command
echo "/engagement list" | harness shell 2>&1 | grep -i "CLI only"
# → should show "CLI only — use the CLI: `harness engagement list`"

# Test unknown command
echo "/nonexistent" | harness shell 2>&1 | grep -i "Unknown command"
# → should show "Unknown command: /nonexistent"

# Test bus-dispatchable command still works
echo "/status" | harness shell 2>&1 | grep -i -v "CLI only"
# → should dispatch normally

# Full test suite
python -m pytest tests/ -q
```
