# Task 4 — Add `@register` to agent/team/consult/remaining commands

**Status:** 📋 Pending
**Wave:** 02-bus-dispatchable-commands
**Dependencies:** Wave 01
**Effort:** 0.5h

## Description

Add `@register(...)` decorator to remaining bus-dispatchable commands: agent/team listing, consult, analysis commands, and other top-level commands.

Commands to annotate:

| REPL Name | Click Function | cmd_cls | handler | arg_parser |
|-----------|---------------|---------|---------|------------|
| `agent list` | `list_agents` | `AgentListCommand` | `AgentListTypedHandler()` | lambda |
| `team list` | `list_teams` | `TeamListCommand` | `TeamListTypedHandler()` | lambda |
| `team set-governance` | (done in Task 3) | — | — | — |
| `consult` | `consult` | `ConsultCommand` | `ConsultTypedHandler()` | lambda |
| `summary` | `summary` | `SummaryCommand` | `SummaryTypedHandler()` | lambda |
| `inspect` | `inspect` | `InspectCommand` | `InspectTypedHandler()` | lambda |
| `assess` | `assess` | `AssessCommand` | `AssessTypedHandler()` | lambda |
| `status` | `status` | `QueryStatusCommand` | `QueryStatusTypedHandler()` | `_single_arg` |
| `whatsnext` | `whatsnext` | `QueryWhatsNextCommand` | `QueryWhatsNextTypedHandler()` | `_single_arg` |
| `generate-docs` | `generate_docs` | `GenerateDocsCommand` | `GenerateDocsTypedHandler()` | lambda |
| `refresh-agents` | `refresh_agents` | `RefreshAgentsCommand` | `RefreshAgentsTypedHandler()` | lambda |

## Acceptance Criteria

- [x] All 11 commands have `@register(name="...", cmd_cls=..., handler=..., arg_parser=...)`
- [x] Each `handler` argument matches current setup.py instantiation pattern
- [x] Each `arg_parser` matches the existing parser from `COMMAND_TYPES` (note: some commands like `summary`, `inspect`, `assess` have both lambdas and named functions — use the named functions for clarity)
- [x] All imports added to `main.py`

## Files Affected

- `src/harness/cli/main.py` (add decorators + imports)

## Verification

```bash
python -c "
from harness.command._registration import REGISTRY
from harness.cli import main
non_click_only = [n for n, r in REGISTRY.items() if not r.click_only]
print(f'Bus-dispatchable commands: {len(non_click_only)}')
print(f'All bus-dispatchable: {len(non_click_only) >= 30}')
"
```
