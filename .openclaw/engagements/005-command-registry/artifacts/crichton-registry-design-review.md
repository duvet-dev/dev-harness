# Crichton: CommandDef Registry Design Review

**Date:** 2026-06-07
**Subject:** `command-registry-design.md` (design proposal)
**Reference:** `crichton-command-wiring-analysis.md` (gap analysis)

---

## 1. Strengths

What the design gets right — and there is real substance here:

### 1.1 Identifies the right problem
The design correctly diagnoses the three-registration anti-pattern and aims for a single source of truth. The `CommandDef` dataclass captures the concept well: identity, CLI appearance, REPL appearance, bus wiring, all in one place.

### 1.2 Explicit opt-out over implicit omission
Using `bus=None, repl=None` for Click-only commands and `click=None` for REPL-only commands is the right pattern. It prevents the ambiguity present in the current code where "not in COMMAND_TYPES" could mean either "intentionally excluded" or "forgotten." The `deprecated=True` pattern for dead commands is similarly correct.

### 1.3 Separate sub-dataclasses
Breaking `ClickParams`, `ReplDef`, and `BusDef` into separate optional dataclasses is structurally sound. It avoids the massive flat dataclass with 20 optional fields where every consumer has to know which fields apply to which mode. The field semantics table in §2.2 is clear.

### 1.4 Sync tests in Phase 0
Putting the sync tests before the registry is operationally correct — prevents further drift while the registry is populated. The test suite in §7 is thorough, covering the critical cross-referencing checks: every Click command has a registry entry, every handler has a registry entry, every registry entry dispatches.

### 1.5 Migrate-in-parallel strategy
Running the registry alongside the old wiring (Phase 1) rather than doing a big-bang switch is prudent. The design acknowledges that the most disruptive part (Click CLI generation) comes last, which is correct sequencing.

### 1.6 Decision log and risk table
The explicit alternatives-rejected entries (§9) and the risk matrix (§10) show real architectural thinking. The circular import risk is correctly identified as high-impact.

---

## 2. Concerns

### 2.1 Severity: Major — Phase 1 adds a fourth registration, doesn't remove any

**Read the design's Phase 1 description carefully:**

> 1. Create registry with `CommandDef` + `COMMAND_REGISTRY`
> 2. Populate with all 39+ commands
> 3. Create `_repl_registry.py`, `_bus_builder.py`
> 4. **Do NOT delete old wiring — the registry runs alongside it**
> 5. Add sync tests that compare registry vs old wiring
> 6. Fix any discovered gaps

During Phase 1, a developer adding a new command must now touch:
1. Click CLI (`main.py`) — old, still required
2. `COMMAND_TYPES` (`repl.py:224`) — old, still required
3. `setup.py` (`bus.register_type()`) — old, still required
4. `COMMAND_REGISTRY` entry — **new, fourth place**

The design says the sync test "prevents further drift." But the mechanism is: write 4 registrations, get a passing test. Forgot one of the 3 old ones? Test catches it — good. **But the developer still writes all 4.** That's not a single source of truth. That's a single source of truth plus three redundant copies that must stay in sync. The operational burden **increases** during Phase 1, not decreases.

**The burden doesn't drop to one until Phase 3 (weeks-months), the full-generation phase.** Given that the current state is "12 broken commands live in production for weeks/months," is a multi-phase migration over weeks/months actually going to happen? What stops the project from stalling at Phase 1 indefinitely, leaving the codebase with the worst of both worlds (4 registrations, maintained in parallel)?

### 2.2 Severity: Major — The registry key naming conflicts with REPL dispatch

This is the single biggest design flaw I found. The registry keys use a full-path naming convention:

```python
"engagement engagement-status"   # registry key
# But the command's Click name is just "status" under group="engagement"
# Users type: /engagement status
```

The REPL dispatch loop (as described in my gap analysis) iterates candidate name prefixes and looks them up in `COMMAND_TYPES`. If the registry-generated `COMMAND_TYPES` uses `"engagement engagement-status"` as the key, then `/engagement status` won't match. The user would need to type `/engagement engagement-status`, which they won't.

The classic naming for this pattern is: `engagement create`, `engagement close` — the key equals the user-facing name. Fine. But for `engagement engagement-status` (note: "engagement" appears twice, because the group is "engagement" and the sub-command name is "engagement-status"), the key diverges from what a user naturally types.

**The design never addresses how registry keys map to user-facing REPL command names.** The `build_repl_command_map()` function uses `key` directly as the dict key. The REPL dispatch loop prefix-matching (line ~620 of `repl.py`) is not modified. This is a latent bug.

### 2.3 Severity: Major — `/help` generation is unaddressed

The current `/help` text is auto-generated from the Click CLI tree. If Click is now generated from the registry, `/help` still works — the Click tree is a valid reflection. **But:**

1. **REPL-only commands** (commands with `click=None`) won't appear in `/help` at all, even though they're available in the REPL. Users won't discover them.

2. **CLI-only commands with `repl=None`** WILL appear in `/help` (because they're in the Click tree), but typing them in the REPL produces "Unknown command." This is the exact same bug the design is supposed to fix — `/help` lying to users. The design marks `engagement list`, `agent show`, `team show`, etc. as `repl=None`, which means they'll show up in `/help` but fail in the REPL.

3. **No REPL-aware help generation** — The design doesn't propose any mechanism for `/help` to distinguish between "this command exists in the CLI but not in the REPL" vs "this command works from any interface." The help text remains misleading.

The fix is straightforward: `/help` should read from `COMMAND_REGISTRY` and only list commands where `repl is not None`. But this is never mentioned in the design.

### 2.4 Severity: Major — `_auto_arg_parser` is underspecified and likely broken for several commands

The auto-parser in §4.1 treats `--anything` as an option flag and everything else as positional. Several failure modes:

1. **`nargs=-1` handling is wrong.** When the parser encounters `nargs=-1`, it captures `[arg] + remaining` — but `remaining` could contain valid `--option value` pairs that belong to later arguments. Example: `consult` has `nargs=-1` for the question argument. If a user types `/consult Why is X slow? --team architects`, the parser would capture `['Why', 'is', 'X', 'slow?', '--team', 'architects']` as the question, losing the `--team` flag.

2. **No `=` syntax.** `--foo=bar` is not handled. The `startswith("--")` check would match, but the option name extraction via `lstrip("-").replace("-", "_")` would produce `"foo=bar"` which won't match any option definition.

3. **No short options.** `-v`, `-f`, `-h` are not handled at all. While the current REPL doesn't heavily use them, the Click CLI does (`-h` for help).

4. **Flag pairs handled incorrectly.** The detection `"/" not in flag` is too fragile. `--partial-approval/--no-partial-approval` is a single Click option, not two. The generated Click param would be a boolean flag, but the auto-parser would try to treat it as a value option.

5. **Missing defaults for optional arguments.** If an argument has `required=False`, the auto-parser doesn't know what default to use if the user doesn't supply it. Example: `init` has `project_dir` with `required=False`. If the user types `/init`, no positional args, the parser produces `{}`, and `InitProjectCommand(**{})` fails because a required field (from the TypedCommand, not from Click) is missing.

6. **`multiple=True` for flags.** The design's option handling says `if opt_def.get("multiple")` then collect remaining tokens as values. But for `--finding` (multiple=True), the Click definition is `@click.option("--finding", multiple=True)`. In the REPL, this would be `/review id --finding F1 --finding F2`. The auto-parser would consume the first `--finding` value but never see the second because it's already moved past `--finding`.

### 2.5 Severity: Major — Param name mismatch between Click kwargs and TypedCommand fields

The generated `_make_bus_dispatch_fn` does:

```python
cmd = defn.cmd_cls(**kwargs)
```

This assumes that every Click parameter name maps directly to a TypedCommand field name. Two problems:

1. **Different naming conventions.** Click options use `--output-dir` → kwarg `output_dir`. But the TypedCommand might have `output_directory`. The design never reconciles these.

2. **Extra kwargs.** Click will inject kwargs for ALL declared params, but the TypedCommand might not have fields for all of them. Some Click params are routing hints, not data fields. `TypeError: __init__() got an unexpected keyword argument` at runtime.

The design says nothing about field name mapping or transformation. This is a silent runtime bug waiting to happen.

### 2.6 Severity: Minor — REPL built-in commands are not in the registry

The REPL has built-in commands: `/help`, `/exit`, `/exec`, `/clear` (plus any others defined inline). These are not in `COMMAND_REGISTRY` and never will be. The design's `build_repl_command_map()` would produce a `COMMAND_TYPES` dict that doesn't include them. The REPL needs to merge them. Minor, but unaddressed.

### 2.7 Severity: Minor — Circular import risk is acknowledged but not mitigated

The registry imports every command class AND every handler class AND arg parsers from `repl.py`. The import chain is: `registry.py` → `handlers/*.py` → (possibly) `setup.py` → (possibly) `registry.py`. The design acknowledges this risk in §10 but offers no structural mitigation beyond "keep COMMAND_REGISTRY in a dedicated module" and "lazy imports in generation functions" — neither of which is concrete.

This is a real issue because several existing handlers import things that could transitively reach back. Adding a new registry entry could break imports for entirely unrelated modules.

### 2.8 Severity: Minor — `_RAW_FNS` mechanism for Click-only bodies is a deferred problem

The design says Click-only command bodies live in `main.py` in a `_RAW_FNS` dict, "referenced by the registry." This means:

1. The bodies still live in `main.py` (no relocation)
2. There's a second mapping (`_RAW_FNS`) that must stay in sync with the registry keys
3. This is the same two-registration problem, just with a different second registry

The design's Phase 2 acknowledges this: "Gradually migrate Click-only bodies into handler files." But there's no plan for what "handler files" means for commands that don't use the CommandBus. The migration path for these 10 commands is vague.

### 2.9 Severity: Clarification — The design is ~1,732 lines. Is this scope proportional?

The three-registration problem produces 12 broken commands (30% failure rate in REPL) and a misleading `/help`. The Crichton analysis proposed these fix options:

| Option | Effort | Fixes 12 broken commands? | Fixes architecture? |
|--------|--------|--------------------------|---------------------|
| Click fallback in REPL | 15 lines | ✅ Immediately | ❌ |
| Sync test only | ~30 lines | ❌ (identifies, doesn't fix) | Prevents drift |
| Decorator-based registration | ~200 lines | ✅ | ✅ (single registration) |
| Full registry design | ~1,700+ lines + weeks migration | Eventually | ✅ |

The question is whether the full-registry approach delivers proportionate benefit relative to simpler alternatives. The next section examines this.

---

## 3. Edge Cases / Gaps

### 3.1 Commands that access `click.Context`

Several Click commands use `@click.pass_context` or access `click.get_current_context()` to get configuration or shared state. The generated `_make_bus_dispatch_fn` does NOT provide a Click context. A command that currently does:

```python
@main.command()
@click.pass_context
def some_command(ctx, slug):
    project = ctx.obj["project"]
```

Would break with the auto-generated function because `ctx` is never passed.

**What to check:** Audit existing Click-only commands for `click.pass_context`, `click.pass_obj`, or `click.get_current_context()` usage before assuming they can be auto-generated.

### 3.2 Commands that `echo` directly vs return through the bus

Currently, bus-dispatchable commands print results through the REPL's result handling (which calls `echo` on `result.message`). But some Click-only commands use `click.echo(click.style(...))` with formatting, or `click.echo_via_pager()`, or `tabulate`. The auto-generated bus dispatch function in `_make_bus_dispatch_fn` only does:

```python
if result.message:
    click.echo(result.message)
```

If the handler returns data that requires formatted output (tables, colors, pagination), the auto-generated function loses that formatting. The `presenter` field exists on `CommandDef` but is never wired into the Click generation functions. It's defined but unused in the generation code.

### 3.3 Commands with mutually exclusive options or option groups

Click supports `cls=mutually_exclusive_group` and `@click.option(cls=...)` for complex option validation. The `ClickParams.options` list of flat dicts cannot express mutual exclusion. The `raw_click_decorators` escape hatch exists, but if it's used for mutual exclusion, the auto-generated arg parser won't enforce the constraint in the REPL — leading to different behaviour between CLI and REPL for the same command.

### 3.4 `click.Choice` and type coercion

The design's `_build_param` doesn't handle `click.Choice`, `click.IntRange`, `click.Path`, `click.File`, or any Click parameter types beyond `type=int` / `type=str`. If a command uses `@click.option("--mode", type=click.Choice(["auto", "wild", "full"]))`, the auto-generated arg parser won't validate the value — it'll just pass the raw string through. Again, different behaviour between CLI and REPL.

### 3.5 The `presenter` field is orphaned

`CommandDef.presenter` is defined in the dataclass but:
- It's never referenced in `_make_bus_dispatch_fn` (Click generation)
- It's never referenced in `build_repl_command_map()` (REPL generation)
- No usage example exists in the registry entries

It's a dead field in the design. Either wire it or remove it.

### 3.6 Multi-word group names

The design's `build_click_cli()` creates groups lazily from `defn.click.group`. If two commands belong to the same group, the second one overwrites the first group's `Group` instance? No — `add_command` is called on the same group object. But the group `help` text is hardcoded: `help=f"Manage {parent}s."`. This produces "Manage engagements." (correct) but also "Manage changelogs." (wrong — should be "Manage changelogs." wait, that's actually fine). But it's still hardcoded with no per-group help text customization.

Also: what about commands with compound group names like `"engagement status"` where the word after the group is the sub-command? That's handled by `click.name` override. But there's no validation that `click.name` doesn't collide with another command in the same group.

### 3.7 Dead commands are in the registry but `setup.py` still has their handlers

The design adds dead commands to the registry with `deprecated=True`. But the handler registration code (`_bus_builder.py`) iterates the registry and registers handlers **unconditionally** — it checks `defn.bus is None or defn.cmd_cls is None` but does NOT check `defn.deprecated`. So deprecated dead commands still get their handlers registered on the bus, which means the bus has registrations for commands with no UI path. This is harmless but wasteful, and the sync test should flag that a deprecated command's handler is still in setup.py.

Wait — looking again at the dead command entries:

```python
"engagement resume": CommandDef(
    key="engagement resume",
    cmd_cls=None,   # No CLI definition
    click=None,
    repl=None,
    deprecated=True,
),
```

If `cmd_cls=None` and `bus=None` (default `None`), then `register_handlers()` skips it. But the handler class `ResumeEngagementHandler` is still registered in `setup.py`'s old `_build_bus()` — it's just not in the registry's bus definitions. The sync test `test_no_dead_code_not_in_registry` would fail because `ResumeEngagementCommand` is in `bus._type_handlers` but has no matching registry entry with `defn.cmd_cls is cmd_type`. The design acknowledges this in the test but never resolves the conflict: do we keep the handler in `setup.py` (fails sync test) or remove it (breaks if anyone calls it)?

---

## 4. Recommendations

### 4.1 Before implementing: justify why a simpler approach won't work

The Crichton gap analysis proposed these options. The design should explicitly address why each was rejected:

| Option | Why it might be sufficient | Why the design rejects it |
|--------|---------------------------|--------------------------|
| **Click fallback** | Fixes 12 broken commands in 15 lines. Zero new infrastructure. Solves the immediate user-facing problem. | Doesn't fix the three-registration anti-pattern for future commands. |
| **Sync test only** | Prevents drift. ~30 lines. No architectural changes. | Doesn't reduce registration burden. Still 3 places to edit. |
| **Decorator-based registration** | Single decorator that records command onto a registry. ~200 lines. Both Click and REPL auto-generate from it. | ? (design doesn't discuss this) |
| **Type-scanning COMMAND_TYPES** | Auto-build COMMAND_TYPES by scanning TypedCommand subclasses or a `_repl_parser` attribute. ~50 lines. | Doesn't address Click wiring. |

The design should explicitly argue why 1,700+ lines of registry infrastructure is the right scope.

### 4.2 Fix the registry key naming for REPL dispatch

**Before Phase 1 code starts:** Define the canonical key naming convention and how it maps to user-facing REPL names.

Option A: Use slash-command names as keys: `"engagement status"`, `"engagement list"`, etc. The `click.name` field handles the case where Click name differs: `engagement engagement-status` → `click=ClickParams(group="engagement", name="engagement-status")`, key = `"engagement status"` (user-facing).

Option B: Use canonical keys but add a `repl_name` field to `CommandDef` that specifies the user-facing REPL name.

Option C: Modify the REPL dispatch loop to be registry-aware, looking up by prefix against both the key and the `(click.group, click.name)` pair.

**Recommendation: Option A.** It's the simplest and most discoverable — the key IS the user-facing name.

### 4.3 Add `/help` generation from the registry

Add a section to the design addressing:
1. `/help` generation reads from `COMMAND_REGISTRY`
2. Only commands with `repl is not None` are listed
3. Commands with `repl is None` but `click is not None` are listed with a "(CLI only)" annotation
4. Built-in REPL commands (`/help`, `/exit`, `/exec`) are hardcoded and listed separately

This is ~20 lines in the REPL's `_cmd_help` method.

### 4.4 Fix or scope the auto-arg-parser before it ships

The `_auto_arg_parser` has too many failure modes (see §2.4). Options:

**Option A:** Don't ship it in Phase 1. Keep all existing custom parsers in `repl.arg_parser`. The auto-parser is a Phase 2 aspiration. This avoids the risk of subtly-broken parsing.

**Option B:** Scope it to commands that are provably compatible. Add a `test_arg_parser_roundtrip` that, for each `auto_parse=True` command, generates random valid args, parses them with the auto-parser, parses them with the Click equivalent, and asserts identical results. Commands that fail get `auto_parse=False`.

**Option C:** Lean on Click itself. Rather than writing a custom parser, use Click's parser: `click.BaseCommand.parse_args()` or invoke with `standalone_mode=False` and extract the params. This eliminates the parsing gap entirely.

**Recommendation: Option C** (use Click's parser) or **Option A** (defer auto-parser). Writing a second parser is a maintenance burden with correctness risk.

### 4.5 Wire the `presenter` field or remove it

Either:
- Document how `presenter` is used in the generated Click and REPL dispatch paths, OR
- Remove it from the v1 dataclass and add it when it's actually implemented

Leaving a defined-but-unused field in the core dataclass is confusing and suggests the design isn't complete.

### 4.6 Add field-name mapping between Click params and TypedCommand fields

Add either:
- A `param_map: dict[str, str]` to `ClickParams` (mapping Click kwarg names → TypedCommand field names), OR
- A `transform_fn: Callable[[dict], dict]` to `BusDef` that transforms Click kwargs into TypedCommand kwargs

Without this, the `cmd_cls(**kwargs)` call is fragile.

### 4.7 Make dead command handling explicit

For the three dead commands (`engagement resume`, `wave create`, `wave execute-step`):

**Decision required:** Remove their handlers from `setup.py`, OR add them to the registry with `deprecated=True` and an explicit `bus` definition with their handler.

The current design puts them in the registry as `deprecated=True` without bus definitions, but doesn't remove them from `setup.py`. That's an inconsistent state the sync test will catch — but it doesn't specify which side should change.

**Recommendation:** Remove the dead handlers from `setup.py` as part of Phase 1. If they're needed later, they can be re-added through the registry. Dead code is dead code.

### 4.8 Add Click context support to generated dispatch functions

For bus-dispatchable commands that currently use `@click.pass_context`: audit the codebase first. If none of them do, document that `ctx` is not available in registry-generated Click functions and it's an explicit limitation. If some do, define a mechanism:

```python
# In BusDef
pass_context: bool = False
```

And in `_make_bus_dispatch_fn`, pass `ctx` as a kwarg if `pass_context=True`.

### 4.9 Shorten the Phase 1 window

The biggest risk is stalling at Phase 1 (4 registrations, indefinite). To mitigate:

**Recommendation:** Set a concrete trigger for moving to Phase 2. For example: "Phase 2 begins when the sync test passes for 7 consecutive days and no new commands have been added in the old style for 14 days." Without a trigger, Phase 1 becomes the permanent state.

### 4.10 Consider a smaller-scope alternative: decorator-based registration

Before committing to this design, prototype the decorator approach. It achieves the single-source-of-truth goal with ~80% less code:

```python
# In a new module: src/harness/command/_registration.py
_registry: dict[str, CommandDef] = {}

def register(
    key: str,
    *,
    cmd_cls: Optional[type[TypedCommand]] = None,
    handler: Optional[TypedHandler] = None,
    click_group: Optional[str] = None,
    click_name: Optional[str] = None,
    repl_parser: Optional[Callable] = None,
    click_fn: Optional[Callable] = None,  # Keep existing Click body
):
    """One decorator to rule them all."""
    def decorator(click_fn):
        _registry[key] = CommandDef(...)
        return click_fn  # Return unchanged — Click still works
    return decorator
```

Usage:
```python
@register("engagement create", cmd_cls=CreateEngagementCommand, 
          handler=CreateEngagementHandler(), click_group="engagement")
@click.argument("name")
def create_engagement(name):
    ...
```

This preserves the existing Click decorators (no Parameter reimplementation), requires one decorator per command, and auto-generates both COMMAND_TYPES and bus registrations. The migration is: add `@register(...)` to every existing Click command. One line per command. No new parser, no new code generation, no 1,700-line registry module.

The design should at minimum address why this approach was rejected.

---

## 5. Summary by Severity

| # | Issue | Severity | Section |
|---|-------|----------|---------|
| 1 | Phase 1 adds a 4th registration; single-source-of-truth deferred to Phase 3 (weeks-months) | **Major** | 2.1 |
| 2 | Registry key naming doesn't match REPL dispatch prefix-matching | **Major** | 2.2 |
| 3 | `/help` generation unaddressed; design leaves help lying to users | **Major** | 2.3 |
| 4 | `_auto_arg_parser` is underspecified and likely broken for several commands | **Major** | 2.4 |
| 5 | Click-param-name → TypedCommand-field-name mismatch is unaddressed | **Major** | 2.5 |
| 6 | REPL built-in commands not in registry | Minor | 2.6 |
| 7 | Circular import risk acknowledged but not mitigated | Minor | 2.7 |
| 8 | `_RAW_FNS` for Click-only bodies defers the problem | Minor | 2.8 |
| 9 | Proportionality: is 1,732-line design right scope vs 15-line fallback? | Clarification | 2.9 |
| 10 | Commands using `click.Context` will break | Gap | 3.1 |
| 11 | Formatted output lost in generated bus dispatch | Gap | 3.2 |
| 12 | Mutual exclusion / option groups not expressible | Gap | 3.3 |
| 13 | `click.Choice` / type coercion unaddressed | Gap | 3.4 |
| 14 | `presenter` field is orphaned (defined, never used) | Gap | 3.5 |
| 15 | Dead command handlers still in setup.py vs registry conflict | Gap | 3.7 |

---

## 6. Verdict

The design is thoughtful and thorough. The `CommandDef` dataclass, the separate sub-definitions, the explicit opt-out patterns, the sync test suite, and the phased migration are all solid architectural choices.

**But the design is over-scoped for the problem it solves.** A 1,732-line registry infrastructure with a custom arg parser, a custom Click parameter builder, and a multi-phase migration spanning weeks-to-months is a heavy solution for "12 commands don't work in the REPL because they're registered in 3 places instead of 1."

The simpler alternatives — a Click fallback in the REPL (15 lines, fixes everything now), a sync test (30 lines, prevents recurrence), or a decorator-based registration system (~200 lines, true single source of truth) — should be evaluated and either adopted or explicitly rejected with reasons before committing to this design.

**If the full registry design proceeds, fix the five major issues above before Phase 1 code starts.** In particular:
1. Define the canonical key naming convention and how it maps to REPL names
2. Address `/help` generation from the registry
3. Fix or defer the auto-arg-parser (consider using Click's own parser)
4. Add field-name mapping between Click params and TypedCommand fields
5. Shorten the Phase 1 window with a concrete transition trigger

Without these fixes, the design risks replacing "12 commands are silently broken" with "the registry says they're fine but the REPL and CLI disagree on what's available."

---

*This review should be appended to the project file and added to the CNS change queue.*
