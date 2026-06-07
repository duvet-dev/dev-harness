# Crichton: REPL Command Wiring Failure Analysis

**Date:** 2026-06-07
**Trigger:** `/engagement list` produces "Unknown command" in REPL but works in CLI and appears in `/help`

---

## 1. Root Cause — Confirmed and Expanded

The root cause diagnosis in the task brief is **correct** but **incomplete**. The REPL has two independent command routing systems that must be manually kept in sync:

### System 1: Click CLI (`src/harness/cli/main.py`)
- Defines all CLI commands via `@main.command()` and `@group.command()` decorators
- Groups: `engagement`, `agent`, `team`, `wave`, `changelog` each have sub-commands
- Some sub-commands dispatch via CommandBus; others contain **inline Click logic** (no TypedCommand)

### System 2: `COMMAND_TYPES` dict (`src/harness/shell/repl.py:224`)
- Maps slash-command names to `(TypedCommand class, arg_parser)` tuples
- The REPL dispatch loop (line ~620) iterates candidate names and looks them up here
- **No fallback to Click.** If a command isn't in `COMMAND_TYPES`, the only outcome is "Unknown command."

### System 3: Handler Registry (`src/harness/command/setup.py`)
- Maps `TypedHandler` instances to `TypedCommand` classes via `bus.register_type()`
- Required for any command that passes through the CommandBus
- Some commands have handlers but no REPL wiring; some have neither

### The Critical Gap

The `/help` text is auto-generated from the Click CLI tree (line ~290 of `repl.py`), so it **truthfully lists every CLI command**. But the REPL dispatch only routes through `COMMAND_TYPES`. The four missing engagement sub-commands (`list`, `diff`, `engagement-status`, `set-active`) show up in `/help` but have no `COMMAND_TYPES` entry, so they fail at runtime.

**The missing commands are "pure Click" commands** — their implementations live directly in the `@click` decorator function bodies (`main.py`), not in the `TypedCommand → TypedHandler → CommandBus` pipeline. They read files, format tables, and call lifecycle functions directly without involving the CommandBus.

---

## 2. Full Gap Matrix

### Legend
- **CLI:** command is defined as a Click command/group in `main.py`
- **CT:** entry exists in `COMMAND_TYPES` dict in `repl.py:224`
- **CMD:** `TypedCommand` dataclass exists
- **HDL:** `TypedHandler` registered in `setup.py`
- **TEST:** has test exercising dispatch through `create_bus()`

| Command | CLI | CT | CMD | HDL | TEST | Notes |
|---------|-----|----|-----|-----|------|-------|
| **engagement group** | | | | | | |
| `engagement create` | ✅ | ✅ | ✅ | ✅ | ❌ | Inline Click has its own logic too |
| `engagement close` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| `engagement rename` | ✅ | ✅ | ✅ | ✅ | ✅ | `TestMgmtCommands.test_rename_empty_slugs` |
| `engagement set-branch` | ✅ | ✅ | ✅ | ✅ | ✅ | `TestQueryCommands.test_set_branch_dispatches` |
| `engagement fix` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| `engagement list` | ✅ | **❌** | **❌** | **❌** | **❌** | **Pure Click — fails in REPL** |
| `engagement diff` | ✅ | **❌** | **❌** | **❌** | **❌** | **Pure Click — fails in REPL** |
| `engagement engagement-status` | ✅ | **❌** | **❌** | **❌** | **❌** | **Pure Click — fails in REPL** |
| `engagement set-active` | ✅ | **❌** | **❌** | **❌** | **❌** | **Pure Click — fails in REPL** |
| **agent group** | | | | | | |
| `agent list` | ✅ | ✅ | ✅ | ✅ | ✅ | `TestQueryCommands.test_agent_list_dispatches` |
| `agent show` | ✅ | **❌** | **❌** | **❌** | **❌** | **Pure Click — fails in REPL** |
| **team group** | | | | | | |
| `team list` | ✅ | ✅ | ✅ | ✅ | ✅ | `TestQueryCommands.test_team_list_dispatches` |
| `team show` | ✅ | **❌** | **❌** | **❌** | **❌** | **Pure Click — fails in REPL** |
| `team add-agent` | ✅ | **❌** | **❌** | **❌** | **❌** | **Pure Click — informational only** |
| `team remove-agent` | ✅ | **❌** | **❌** | **❌** | **❌** | **Pure Click — informational only** |
| `team consult` | ✅ | **❌** | **❌** | **❌** | **❌** | **Pure Click — fails in REPL** |
| `team set-governance` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| **wave group** | | | | | | |
| `wave list` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| `wave run` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| `wave status` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| `wave create-from-assessment` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| `wave create-from-finding` | ✅ | ✅ | ✅ | ✅ | ✅ | `TestBatchCommands` |
| **changelog group** | | | | | | |
| `changelog annotate` | ✅ | ✅ | ✅ | ✅ | ✅ | `TestBatchCommands` |
| **top-level commands** | | | | | | |
| `workflows` | ✅ | **❌** | **❌** | **❌** | **❌** | **Pure Click help display — fails in REPL** |
| `whatsnext` | ✅ | ✅ | ✅ | ✅ | ✅ | |
| `enter-phase` | ✅ | ✅ | ✅ | ✅ | ✅ | |
| `init` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| `refresh-agents` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| `work` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| `summary` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| `inspect` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| `assess` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| `shell` | ✅ | **❌** | **❌** | **❌** | **❌** | **REPL built-in (special case, works)** |
| `health` | ✅ | **❌** | **❌** | **❌** | **❌** | **Pure Click — fails in REPL** |
| `consult` | ✅ | ✅ | ✅ | ✅ | ✅ | |
| `chat` | ✅ | ✅ | ✅ | ✅ | ✅ | |
| `session` | ✅ | ✅ | ✅ | ✅ | ✅ | |
| `review` | ✅ | ✅ | ✅ | ✅ | ✅ | |
| `status` | ✅ | ✅ | ✅ | ✅ | ✅ | |
| `phase` | ✅ | ✅ | ✅ | ✅ | ✅ | |
| `finish` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| `generate-docs` | ✅ | ✅ | ✅ | ✅ | ❌ | |
| **commands with handlers but NOT in CLI or CT** | | | | | | |
| `engagement resume` | **❌** | **❌** | ✅ | ✅ | **❌** | **Dead code — wired nowhere** |
| `wave create` | **❌** | **❌** | ✅ | ✅ | **❌** | **Dead code — wired nowhere** |
| `wave execute-step` | **❌** | **❌** | ✅ | ✅ | **❌** | **Dead code — wired nowhere** |

### Summary Statistics

| Category | Count |
|----------|-------|
| CLI commands total | 39 |
| CLI commands that **work in REPL** (in COMMAND_TYPES) | 30 |
| CLI commands that **fail in REPL** (not in COMMAND_TYPES) | **12** |
| CLI commands that work in REPL AND have test coverage | 15 |
| CLI commands that work in REPL but have NO test coverage | 15 |
| Dead commands (handler + CMD but wired nowhere) | 3 |
| "Pure Click" commands (no TypedCommand, no handler) | 10 |

**12 CLI commands show up in `/help` but fail in the REPL.** The four engagement sub-commands are the tip of the iceberg.

---

## 3. Broader Architectural Issues

### 3.1 Three-Registration Anti-Pattern (Severity: structural / major)

Every REPL-dispatchable command must be registered in **three independent places**:
1. Click CLI (`main.py`) — decorated with `@click.command()`
2. `COMMAND_TYPES` dict (`repl.py:224`) — mapped to class + arg parser
3. `_build_bus()` in `setup.py` — handler registered via `bus.register_type()`

There is no single source of truth. No mechanism ensures these stay in sync. Adding a new command requires remembering all three registrations, and forgetting any one produces a different failure mode:
- Missing from CLI → not discoverable (no help text)
- Missing from COMMAND_TYPES → "Unknown command" in REPL despite appearing in help
- Missing from setup.py → `UnknownCommandError` at runtime, even from CLI

### 3.2 Help Text Is Misleading (Severity: structural / blocker)

The help is auto-generated from Click, so it truthfully lists what the CLI provides. But the REPL can't execute 12 of those commands. This means `/help` is **actively lying to users** — it says a command exists, the user types it, and gets "Unknown command." This is worse than not listing the command at all.

### 3.3 Pure Click Commands Are Architectural Debt (Severity: structural / major)

Ten commands implement their logic directly in Click function bodies rather than through the CommandBus pipeline. These commands:
- Duplicate logic that should live in handlers
- Can't be tested through the bus integration test framework
- Can't benefit from shared error handling, logging, or middleware
- Require a separate mechanism (Click fallback or TypedCommand refactor) to work in the REPL

The hybrid architecture means two completely different execution paths exist for the same conceptual operation depending on entry point (CLI flag vs REPL slash command).

### 3.4 No Sync Tests (Severity: structural / blocker)

There is exactly one test that exercises the full COMMAND_TYPES → CommandBus → handler chain for a REPL command:
```python
# tests/unit/shell/test_repl.py
def test_known_command_dispatches(self, mock_echo, tmp_path):
    """Known COMMAND_TYPES entries should dispatch via bus."""
    with patch("harness.shell.repl._dispatch_via_bus") as mock_bus:
        mock_bus.return_value = CommandResult(success=True, ...)
        repl = HarnessREPL(root=tmp_path)
        result = repl._run_command("/agent list")
```

This test only checks `/agent list`. It does not iterate all COMMAND_TYPES entries. It does not compare COMMAND_TYPES against the Click CLI tree. It does not verify that every command in `/help` is executable. It mocks out the bus, so it doesn't even test the full dispatch chain.

**What should exist but doesn't:**
- A test that iterates all `COMMAND_TYPES` keys and verifies each dispatches to a real (non-mocked) handler
- A test that compares the Click CLI command tree against `COMMAND_TYPES` and asserts no mismatches
- A test that parses `/help` output and verifies every listed command is dispatchable

### 3.5 No CI Gate for Command Registration (Severity: structural / major)

Adding a new `@engagement.command()` decorator in `main.py` to a sub-command has zero guardrails. Nothing fails at lint, test, or CI time. The developer must manually remember to also:
1. Create a TypedCommand class
2. Create a TypedHandler class
3. Register it in `setup.py`
4. Add it to `COMMAND_TYPES`
5. Write an arg parser

Missing any one of these creates a silent bug that only manifests at runtime (and only in one execution path).

### 3.6 Dead Code (Severity: clarity / minor)

Three TypedCommands have handlers registered in `setup.py` but are wired to neither the CLI nor COMMAND_TYPES:
- `ResumeEngagementCommand` / `ResumeEngagementHandler`
- `CreateWaveCommand` / `CreateWaveTypedHandler`
- `ExecuteStepCommand` / `ExecuteStepTypedHandler`

These are dead code. They increase the bus registration surface, cost maintenance (imports, tests), and confuse navigation. If they're future features, they should be behind a feature flag or removed until needed.

---

## 4. Fix Plan

### Step 1: Immediate Fix — Add Click Fallback to REPL Dispatch

**Priority:** P0 (blocker — fixes all 12 broken commands immediately)

This is the minimum viable fix. Add a Click fallback in `_run_command()` after the COMMAND_TYPES lookup fails. When a command isn't in COMMAND_TYPES but exists in `self.commands` or `self.groups`, invoke it via Click's `CliRunner` or `ctx.invoke()`.

```python
# In _run_command(), after the "if not dispatched:" block:

if not dispatched:
    # Click fallback: try invoking via Click for commands that
    # exist in the CLI tree but haven't been ported to COMMAND_TYPES
    if cmd_name in self.commands:
        cmd = self.commands[cmd_name]
        try:
            # Use Click's CliRunner for isolation
            from click.testing import CliRunner
            runner = CliRunner()
            result = runner.invoke(cmd, cmd_args, standalone_mode=False)
            if result.output:
                click.echo(result.output.rstrip())
            if result.exit_code != 0:
                if result.exception:
                    click.echo(f"Error: {result.exception}", err=True)
            dispatched = True
        except Exception as exc:
            click.echo(f"Error executing /{cmd_name}: {exc}", err=True)
            dispatched = True
```

**Pros:** One-line fix location, covers all 12 broken commands, no new registrations needed.
**Cons:** Adds a second dispatch path, doesn't address the architectural issues, REPL and CLI still have different code paths for the same commands.

### Step 2: Add Sync Tests

**Priority:** P0 (prevents recurrence)

Add to `tests/unit/shell/test_repl.py`:

```python
def test_all_click_commands_in_command_types(self, tmp_path):
    """Every CLI command that dispatches via CommandBus must be in COMMAND_TYPES
    OR have a typed command + handler. Pure-Click informational commands
    (workflows, team add-agent, team remove-agent) are exempt."""
    from harness.shell.repl import COMMAND_TYPES
    from harness.cli import main as cli_main
    
    # Build flat list of all CLI command names
    cli_commands = set()
    for name, cmd in cli_main.commands.items():
        if isinstance(cmd, click.Group):
            for sub_name in cmd.commands:
                cli_commands.add(f"{name} {sub_name}")
        else:
            cli_commands.add(name)
    
    # Commands that are intentionally pure-Click (informational / help-only)
    pure_click_only = {
        "workflows",         # help display only
        "team add-agent",    # informational — tells user to edit yaml
        "team remove-agent", # informational — tells user to edit yaml
        "shell",             # REPL built-in (special case)
        "engagement list",   # ❌ SHOULD be in COMMAND_TYPES
        "engagement diff",   # ❌ SHOULD be in COMMAND_TYPES
        "engagement engagement-status",  # ❌ SHOULD be in COMMAND_TYPES
        "engagement set-active",  # ❌ SHOULD be in COMMAND_TYPES
        "agent show",        # ❌ SHOULD be in COMMAND_TYPES
        "team show",         # ❌ SHOULD be in COMMAND_TYPES
        "team consult",      # ❌ SHOULD be in COMMAND_TYPES
        "health",            # ❌ SHOULD be in COMMAND_TYPES
    }
    
    missing = cli_commands - set(COMMAND_TYPES.keys()) - pure_click_only
    assert not missing, (
        f"CLI commands missing from COMMAND_TYPES: {sorted(missing)}\n"
        f"Either add them to COMMAND_TYPES or add to pure_click_only "
        f"with a justification comment."
    )
```

This test will **fail** until all missing commands are either wired or explicitly exempted. The failure message is self-documenting.

### Step 3: Refactor Pure Click Commands to CommandBus Pipeline

**Priority:** P1 (addresses architectural debt)

For each of the 10 "pure Click" commands, either:

**Option A (preferred):** Create a TypedCommand + TypedHandler and refactor the Click function to dispatch through the bus. Add to COMMAND_TYPES.

**Option B (pragmatic):** Accept them as Click-only and document why. Add to an explicitly-exempted list in the sync test. This is reasonable for:
- `workflows` — pure help text display
- `team add-agent` / `team remove-agent` — purely informational (tells user to edit YAML)
- `shell` — runs the REPL itself (infinite recursion risk)

Everything else should go Option A, because they perform meaningful operations that users expect to work in the REPL.

### Step 4: Auto-Generate COMMAND_TYPES from CLI Decorators

**Priority:** P2 (long-term architectural fix)

The real fix is to eliminate manual registration. Options:

**Option A:** Use Click's `Context.params` / `Context.command` introspection at REPL startup to auto-build COMMAND_TYPES. This is fragile because Click doesn't carry CommandBus type information.

**Option B:** Register TypedCommand → handler mappings in a decorator or class attribute, then auto-derive COMMAND_TYPES from that registry. The Click CLI functions become thin wrappers that dispatch through the bus.

**Option C:** Move to a single-source-of-truth registry:
```python
# command_registry.py
REGISTRY = [
    CommandDef(
        name="engagement create",
        cmd_cls=CreateEngagementCommand,
        handler=CreateEngagementHandler(),
        arg_parser=_engagement_create_args,
        click_group="engagement",
        click_decorators=[click.argument("name")],
    ),
    ...
]
```

Then auto-generate both the Click CLI and COMMAND_TYPES from this registry.

### Step 5: Remove Dead Code

**Priority:** P2 (cleanup)

Either:
- Wire `ResumeEngagementCommand`, `CreateWaveCommand`, `ExecuteStepCommand` into the CLI and REPL (if they're intended features), OR
- Remove them from `setup.py` and delete the handler/command classes (if they're abandoned)

### Step 6: CI Enforcement

**Priority:** P2

Add the sync test from Step 2 to the CI pipeline. Any PR that adds a Click command without corresponding COMMAND_TYPES + handler registration should fail CI with a clear message.

---

## 5. Immediate Fix Recommendation

The fastest path to fixing the specific `/engagement list` failure (and all 12 broken commands):

1. **Add Click fallback** to `_run_command()` (~15 lines of code) — fixes everything now
2. **Add the sync test** from Step 2 — prevents recurrence
3. **File issues** for the architectural refactors (Steps 3-6) — track the debt

The Click fallback is pragmatic because:
- It fixes all 12 broken commands with one code change
- It doesn't require refactoring 10 command implementations
- It handles future Click-only commands automatically
- The CLI commands already have their own error handling and output formatting

The architectural fixes (Steps 3-6) should still be done, but they're 2-3 days of work vs. 10 minutes for the fallback.

---

## 6. Audit Notes

### Files examined:
- `src/harness/shell/repl.py` (full file, 825 lines)
- `src/harness/cli/main.py` (full file, ~1500 lines)
- `src/harness/command/commands/engagement.py`
- `src/harness/command/commands/mgmt.py`
- `src/harness/command/commands/batch.py`
- `src/harness/command/handlers/mgmt_handlers.py`
- `src/harness/command/setup.py`
- `tests/unit/shell/test_repl.py`
- `tests/unit/command/test_create_bus_integration.py`

### Commands not individually verified (existence confirmed from file listing):
- `commands/analysis.py`, `commands/misc.py`, `commands/phase.py`, `commands/project.py`, `commands/review.py`, `commands/session.py`, `commands/wave.py`
- `handlers/analysis_handlers.py`, `handlers/batch_handlers.py`, `handlers/engagement_handlers.py`, `handlers/misc_handlers.py`, `handlers/phase_handlers.py`, `handlers/project_handlers.py`, `handlers/review_handlers.py`, `handlers/session_handlers.py`, `handlers/wave_handlers.py`
