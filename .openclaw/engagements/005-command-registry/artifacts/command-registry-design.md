# CommandDef Registry — Single Source of Truth for All Commands

**Date:** 2026-06-07
**Status:** Design Proposal
**Author:** Architect (subagent)

---

## 1. Problem Summary

Commands must currently be registered in **three independent places**:
1. **Click CLI** (`src/harness/cli/main.py`) — `@click.command()` / `@group.command()` decorators
2. **REPL command map** (`src/harness/shell/repl.py:224` — `COMMAND_TYPES` dict)
3. **Handler registry** (`src/harness/command/setup.py` — `bus.register_type()`)

**Consequences (from Crichton analysis):**
- 12 CLI commands show up in `/help` but fail at runtime in the REPL
- 10 "pure Click" commands bypass the CommandBus entirely
- 3 handlers are registered but wired to nothing (dead code)
- No test validates that these registries stay in sync
- Adding a command requires touching 3–4 files with no guardrails

---

## 2. Design: `CommandDef` Registry

### 2.1 Core Dataclass

A single dataclass that describes **everything** about a command. Every command in the system appears in exactly one place: the `COMMAND_REGISTRY` list.

```python
# src/harness/command/registry.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional

from harness.command.types import TypedCommand, TypedHandler


@dataclass(frozen=True)
class ClickParams:
    """Describes how a command appears in the Click CLI.

    For argument-heavy or option-heavy commands, params mirror
    @click.argument and @click.option decorators. For simple
    commands, use the short-form string-based declaration.
    """

    # ── Click CLI position ──────────────────────────────────────────
    group: Optional[str] = None        # None = top-level command
    name: Optional[str] = None         # Override command name (default: from registry key)

    # ── Params (replaces @click.argument / @click.option) ──────────
    arguments: list[dict[str, Any]] = field(default_factory=list)
    """Each dict: {"name": str, "type": type, "required": bool, ...}"""

    options: list[dict[str, Any]] = field(default_factory=list)
    """Each dict: {"opts": list[str], "type": type, "default": Any, "help": str, ...}"""

    # ── Escape hatch ───────────────────────────────────────────────
    raw_click_decorators: list[Callable] = field(default_factory=list)
    """Arbitrary @click decorators to apply. For advanced Click features
    not covered by the declarative params above (value_proc, callback,
    etc.). This is a temporary escape hatch — aim for zero usage."""


@dataclass(frozen=True)
class ReplDef:
    """Describes how a command is available in the REPL.

    If omitted entirely, the command is REPL-only (e.g. /exec, /exit).
    If explicity set to ``None``, the command is intentionally
    CLI-only (e.g. informational help commands like ``workflows``).
    """

    # ── REPL dispatch path ─────────────────────────────────────────
    arg_parser: Optional[Callable[[list[str]], dict[str, Any]]] = None
    """Parses raw REPL args into kwargs for the command dataclass.
    If None, the arg parser is auto-generated from ClickParams."""

    auto_parse: bool = True
    """If True, auto-generate arg parser from ClickParams. If False
    and arg_parser is None, the command is CLI-only."""


@dataclass(frozen=True)
class BusDef:
    """Describes how a command connects to the CommandBus.

    If None (the dataclass field is omitted), the command is
    intentionally Click-only / pure-Click.
    """

    handler: TypedHandler
    """The handler instance to register with the CommandBus."""

    multi_result: bool = False
    """If True, the handler may return multiple result types."""


@dataclass(frozen=True)
class CommandDef:
    """Single source of truth for one command.

    From this definition, the system auto-generates:
      - The Click CLI tree (groups + commands + params)
      - The REPL COMMAND_TYPES map (name -> (cmd_cls, arg_parser))
      - The bus.register_type() calls

    A command can be:
      - **Full pipeline**: has cmd_cls, handler, click_def — auto-generated everywhere
      - **Click-only**: has click_def but no cmd_cls/no handler — for informational commands
      - **Bus-only**: has cmd_cls + handler but no click_def — for programmatic dispatch
    """

    # ── Identity ───────────────────────────────────────────────────
    key: str
    """Unique command key, e.g. "engagement create", "team list", "work".
    Used as the canonical identifier everywhere."""

    help_text: str = ""
    """Short help text shown in /help and --help."""

    # ── Command dataclass ──────────────────────────────────────────
    cmd_cls: Optional[type[TypedCommand]] = None
    """The TypedCommand dataclass. If None, this is a Click-only command."""

    # ── Click CLI appearance ───────────────────────────────────────
    click: Optional[ClickParams] = field(default_factory=ClickParams)
    """How the command appears in Click. If None, the command is
    REPL/internal-only."""

    # ── REPL appearance ────────────────────────────────────────────
    repl: Optional[ReplDef] = field(default_factory=ReplDef)
    """How the command is available in the REPL. If None, the command
    is CLI-only."""

    # ── Bus registration ───────────────────────────────────────────
    bus: Optional[BusDef] = None
    """Handler information for CommandBus registration. If None,
    the command does NOT go through the CommandBus."""

    # ── Presenter (optional) ────────────────────────────────────────
    presenter: Optional[Callable] = None
    """Optional presenter for formatting results in the REPL/CLI.
    If None, the default present(result.message) is used."""

    # ── Deprecation ────────────────────────────────────────────────
    deprecated: bool = False
    """If True, emit a deprecation warning on use."""


# ── Alternate: Static registry (the list) ────────────────────────────────
# Commands are declared here and ONLY here. Everything else is derived.

CommandKey = str  # e.g. "engagement create"

CommandRegistry = dict[CommandKey, CommandDef]
```

### 2.2 Field Semantics Reference

| Field | Required | Purpose |
|-------|----------|---------|
| `key` | **Yes** | Canonical identifier. Top-level: `"work"`, sub-command: `"engagement create"` |
| `help_text` | Recommended | Shown in `--help` and `/help` |
| `cmd_cls` | Conditional | **Required** for bus-dispatchable commands. `None` for Click-only informational commands |
| `click` | Optional | How to generate the Click decorator tree. `None` for REPL-only/internal commands |
| `click.group` | Optional | Parent Click group. `None` for top-level commands |
| `click.name` | Optional | Override the Click command name (rare; mostly matches `key` suffix) |
| `click.arguments` | Optional | Positional arguments (mirrors `@click.argument`) |
| `click.options` | Optional | Named options (mirrors `@click.option`) |
| `click.raw_click_decorators` | Escape hatch | Hack for Click features too quirky for the declarative model |
| `repl` | Optional | REPL availability. `None` = CLI-only |
| `repl.arg_parser` | Optional | Custom arg parser function. `None` = auto-generate from `click.*` |
| `repl.auto_parse` | Flag | Auto-generate parser from Click params (default: True) |
| `bus` | Optional | Handler registration. `None` = Click-only |
| `bus.handler` | Conditional | **Required** if `bus` is provided |
| `deprecated` | Flag | Emit deprecation warning on invocation |

### 2.3 Registry Structure

Commands are declared in a single flat `COMMAND_REGISTRY` dict, keyed by their canonical name:

```python
# src/harness/command/registry.py (bottom)

from harness.command.commands.engagement import (
    AbortEngagementCommand, CreateEngagementCommand,
)
from harness.command.commands.mgmt import (
    RenameEngagementCommand, SetBranchCommand, FixEngagementCommand,
    RefreshAgentsCommand, SetGovernanceCommand,
    AgentListCommand, TeamListCommand, ConsultCommand,
)
from harness.command.commands.phase import EnterPhaseCommand, ManagePhaseCommand
from harness.command.commands.project import InitProjectCommand
from harness.command.commands.session import ChatCommand, SessionCommand
from harness.command.commands.review import (
    FinishEngagementCommand, ReviewEngagementCommand,
)
from harness.command.commands.wave import RunWaveCommand
from harness.command.commands.batch import (
    AnnotateChangelogCommand, CreateWaveFromFindingCommand,
    CreateWavesFromAssessmentCommand, GenerateDocsCommand,
    ListWavesCommand, WaveStatusCommand,
)
from harness.command.commands.misc import (
    NextCommand, QueryStatusCommand, QueryWhatsNextCommand,
)
from harness.command.commands.analysis import (
    AssessCommand, InspectCommand, SummaryCommand,
)
from harness.command.handlers.engagement_handlers import (
    AbortEngagementTypedHandler, CreateEngagementHandler,
)
from harness.command.handlers.phase_handlers import (
    EnterPhaseTypedHandler, PhaseManagementTypedHandler,
)
from harness.command.handlers.project_handlers import InitProjectTypedHandler
from harness.command.handlers.session_handlers import (
    ChatTypedHandler, SessionTypedHandler,
)
from harness.command.handlers.review_handlers import (
    FinishEngagementTypedHandler, ReviewEngagementTypedHandler,
)
from harness.command.handlers.wave_handlers import (
    RunWaveTypedHandler, WaveStatusTypedHandler,
)
from harness.command.handlers.misc_handlers import (
    NextTypedHandler, QueryStatusTypedHandler, QueryWhatsNextTypedHandler,
)
from harness.command.handlers.analysis_handlers import (
    AssessTypedHandler, InspectTypedHandler, SummaryTypedHandler,
)
from harness.command.handlers.batch_handlers import (
    AnnotateChangelogTypedHandler, CreateWaveFromFindingTypedHandler,
    CreateWavesFromAssessmentTypedHandler, GenerateDocsTypedHandler,
    ListWavesTypedHandler, RunWaveTypedHandler as RunWaveBatchTypedHandler,
)
from harness.command.handlers.mgmt_handlers import (
    AgentListTypedHandler, ConsultTypedHandler,
    FixEngagementTypedHandler, TeamListTypedHandler,
    RefreshAgentsTypedHandler, RenameEngagementTypedHandler,
    SetBranchTypedHandler, SetGovernanceTypedHandler,
)

# Imports for auto-generated arg parsers
from harness.shell.repl import (
    _single_arg, _engagement_create_args, _phase_args, _work_args,
    _init_args, _run_wave_args, _finish_args, _review_args,
    _summary_args, _chat_args, _session_args,
)


COMMAND_REGISTRY: CommandRegistry = {

    # ═══════════════════════════════════════════════════════════════════
    # Top-level commands (full pipeline: bus-dispatchable)
    # ═══════════════════════════════════════════════════════════════════

    "init": CommandDef(
        key="init",
        help_text="Initialise a harness project in the current or specified directory.",
        cmd_cls=InitProjectCommand,
        click=ClickParams(
            arguments=[{"name": "project_dir", "type": str, "required": False}],
            options=[
                {"opts": ["--template"], "type": str, "help": "Project template"},
                {"opts": ["--seed"], "type": str, "help": "Context to seed from"},
                {"opts": ["--no-git"], "is_flag": True, "help": "Skip git init"},
                {"opts": ["--force"], "is_flag": True, "help": "Re-initialise even if already initialised"},
            ],
        ),
        bus=BusDef(handler=InitProjectTypedHandler()),
    ),

    "work": CommandDef(
        key="work",
        help_text="Start a new engagement.",
        cmd_cls=CreateEngagementCommand,
        click=ClickParams(
            arguments=[{"name": "description", "type": str, "required": True}],
            options=[
                {"opts": ["--mode"], "type": str, "default": "auto",
                 "help": "Mode: wild, auto, full"},
                {"opts": ["--backend"], "type": str, "help": "Agent backend"},
                {"opts": ["--max-iterations"], "type": int, "default": 5},
                {"opts": ["--partial-approval/--no-partial-approval"],
                 "type": bool, "default": True},
            ],
        ),
        bus=BusDef(handler=CreateEngagementHandler()),
    ),

    "whatsnext": CommandDef(
        key="whatsnext",
        help_text="Show available next actions for an engagement.",
        cmd_cls=QueryWhatsNextCommand,
        click=ClickParams(
            arguments=[{"name": "slug", "type": str, "required": True}],
        ),
        bus=BusDef(handler=QueryWhatsNextTypedHandler()),
    ),

    "enter-phase": CommandDef(
        key="enter-phase",
        help_text="Enter the specified phase for an engagement.",
        cmd_cls=EnterPhaseCommand,
        click=ClickParams(
            arguments=[
                {"name": "slug", "type": str, "required": True},
                {"name": "phase", "type": str, "required": True},
            ],
        ),
        bus=BusDef(handler=EnterPhaseTypedHandler()),
    ),

    "refresh-agents": CommandDef(
        key="refresh-agents",
        help_text="Refresh agent profiles from the harness's current agent registry.",
        cmd_cls=RefreshAgentsCommand,
        click=ClickParams(
            arguments=[{"name": "project_dir", "type": str, "required": False}],
            options=[
                {"opts": ["--force"], "is_flag": True,
                 "help": "Overwrite existing agent profile files"},
            ],
        ),
        bus=BusDef(handler=RefreshAgentsTypedHandler()),
    ),

    "summary": CommandDef(
        key="summary",
        help_text="Show project status summary.",
        cmd_cls=SummaryCommand,
        click=ClickParams(
            options=[
                {"opts": ["--engagement"], "type": str, "help": "Engagement ID (default: current)"},
                {"opts": ["--deep"], "is_flag": True},
                {"opts": ["--assess"], "is_flag": True,
                 "help": "Run LLM-based independent assessment"},
                {"opts": ["--json"], "is_flag": True, "help": "Output as JSON"},
                {"opts": ["--reconcile"], "is_flag": True, "help": "Refresh state before summary"},
            ],
        ),
        bus=BusDef(handler=SummaryTypedHandler()),
    ),

    "status": CommandDef(
        key="status",
        help_text="Quick view of active engagement.",
        cmd_cls=QueryStatusCommand,
        click=ClickParams(
            arguments=[{"name": "slug", "type": str, "required": False}],
            options=[{"opts": ["--force"], "is_flag": True}],
        ),
        bus=BusDef(handler=QueryStatusTypedHandler()),
    ),

    "inspect": CommandDef(
        key="inspect",
        help_text="Analyse a codebase as an external observer.",
        cmd_cls=InspectCommand,
        click=ClickParams(
            arguments=[{"name": "repo_path", "type": str, "required": False, "default": "."}],
            options=[
                {"opts": ["--report"], "type": str, "help": "Write report to file"},
                {"opts": ["--verbose"], "is_flag": True, "help": "Print full report"},
            ],
        ),
        bus=BusDef(handler=InspectTypedHandler()),
    ),

    "assess": CommandDef(
        key="assess",
        help_text="Run the full assessment on the current project.",
        cmd_cls=AssessCommand,
        click=ClickParams(
            arguments=[{"name": "repo_path", "type": str, "required": False, "default": "."}],
            options=[
                {"opts": ["--report"], "type": str, "help": "Write report to file"},
                {"opts": ["--verbose"], "is_flag": True, "help": "Print full report"},
            ],
        ),
        bus=BusDef(handler=AssessTypedHandler()),
    ),

    "phase": CommandDef(
        key="phase",
        help_text="Manage engagement phases.",
        cmd_cls=ManagePhaseCommand,
        click=ClickParams(
            arguments=[{"name": "engagement_id", "type": str, "required": False}],
            options=[
                {"opts": ["--list"], "is_flag": True, "help": "List phases"},
                {"opts": ["--advance"], "is_flag": True, "help": "Advance to next phase"},
                {"opts": ["--navigate"], "type": str, "help": "Navigate to a phase"},
                {"opts": ["--resume"], "is_flag": True, "help": "Resume from paused checkpoint"},
                {"opts": ["--status"], "is_flag": True, "help": "Show phase state diagram"},
            ],
        ),
        bus=BusDef(handler=PhaseManagementTypedHandler()),
    ),

    "chat": CommandDef(
        key="chat",
        help_text="Interactive LLM chat session within an engagement.",
        cmd_cls=ChatCommand,
        click=ClickParams(
            arguments=[{"name": "prompt_text", "type": str, "required": False}],
            options=[
                {"opts": ["--engagement"], "type": str, "help": "Engagement slug"},
                {"opts": ["--phase"], "type": str, "default": "design"},
                {"opts": ["--context-tier"], "type": int, "default": 2},
            ],
        ),
        bus=BusDef(handler=ChatTypedHandler()),
    ),

    "session": CommandDef(
        key="session",
        help_text="Run a full phase-by-phase session.",
        cmd_cls=SessionCommand,
        click=ClickParams(
            options=[
                {"opts": ["--engagement"], "type": str, "help": "Engagement slug"},
                {"opts": ["--phase"], "type": str, "default": "requirements"},
                {"opts": ["--context-tier"], "type": int, "default": 2},
                {"opts": ["--greenfield"], "is_flag": True, "help": "Greenfield session"},
                {"opts": ["--brownfield"], "is_flag": True, "help": "Brownfield session"},
                {"opts": ["--refactoring"], "is_flag": True, "help": "Refactoring session"},
                {"opts": ["--get-well"], "is_flag": True, "help": "Get-well remediation session"},
            ],
        ),
        bus=BusDef(handler=SessionTypedHandler()),
    ),

    "review": CommandDef(
        key="review",
        help_text="Review an engagement at a gate checkpoint.",
        cmd_cls=ReviewEngagementCommand,
        click=ClickParams(
            arguments=[{"name": "engagement_id", "type": str, "required": True}],
            options=[
                {"opts": ["--approve"], "is_flag": True},
                {"opts": ["--reject"], "is_flag": True},
                {"opts": ["--request-changes"], "is_flag": True},
                {"opts": ["--finding"], "multiple": True, "help": "A specific finding (repeatable)"},
                {"opts": ["--severity"], "type": str, "default": "blocker"},
                {"opts": ["--notes"], "type": str, "default": ""},
            ],
        ),
        bus=BusDef(handler=ReviewEngagementTypedHandler()),
    ),

    "finish": CommandDef(
        key="finish",
        help_text="Complete the current engagement with a commit.",
        cmd_cls=FinishEngagementCommand,
        click=ClickParams(
            options=[
                {"opts": ["--re-assess"], "is_flag": True,
                 "help": "Re-run assessment and compare to baseline"},
            ],
        ),
        bus=BusDef(handler=FinishEngagementTypedHandler()),
    ),

    "consult": CommandDef(
        key="consult",
        help_text="Ask a cross-team consultation question.",
        cmd_cls=ConsultCommand,
        click=ClickParams(
            arguments=[{"name": "question", "nargs": -1, "type": str, "required": True}],
            options=[
                {"opts": ["--team"], "type": str, "help": "Limit to a specific team"},
                {"opts": ["--mode"], "type": str, "default": "advisory"},
                {"opts": ["--engagement"], "type": str, "help": "Engagement context"},
            ],
        ),
        bus=BusDef(handler=ConsultTypedHandler()),
    ),

    "generate-docs": CommandDef(
        key="generate-docs",
        help_text="Generate project documentation from harness analysis data.",
        cmd_cls=GenerateDocsCommand,
        click=ClickParams(
            options=[
                {"opts": ["--output-dir"], "type": str},
                {"opts": ["--overwrite"], "type": str, "default": "ask"},
                {"opts": ["--type"], "type": str, "default": "full"},
                {"opts": ["--source-tier"], "type": int, "default": 3},
            ],
        ),
        bus=BusDef(handler=GenerateDocsTypedHandler()),
    ),

    # ═══════════════════════════════════════════════════════════════════
    # Engagement group commands
    # ═══════════════════════════════════════════════════════════════════

    "engagement create": CommandDef(
        key="engagement create",
        help_text="Create a new engagement.",
        cmd_cls=CreateEngagementCommand,
        click=ClickParams(
            group="engagement",
            arguments=[{"name": "name", "type": str, "required": True}],
            options=[
                {"opts": ["--slug"], "type": str, "help": "Override auto-derived slug"},
                {"opts": ["--refactoring"], "is_flag": True},
                {"opts": ["--focus"], "type": str, "default": "all"},
            ],
        ),
        bus=BusDef(handler=CreateEngagementHandler()),
    ),

    "engagement rename": CommandDef(
        key="engagement rename",
        help_text="Rename an existing engagement.",
        cmd_cls=RenameEngagementCommand,
        click=ClickParams(
            group="engagement",
            arguments=[
                {"name": "old_slug", "type": str, "required": True},
                {"name": "new_slug", "type": str, "required": True},
            ],
            options=[
                {"opts": ["--branch-strategy"], "type": str, "default": "keep"},
                {"opts": ["--dry-run"], "is_flag": True},
            ],
        ),
        bus=BusDef(handler=RenameEngagementTypedHandler()),
    ),

    "engagement close": CommandDef(
        key="engagement close",
        help_text="Close an engagement by setting its status to completed.",
        cmd_cls=AbortEngagementCommand,
        click=ClickParams(
            group="engagement",
            arguments=[{"name": "slug", "type": str, "required": True}],
        ),
        bus=BusDef(handler=AbortEngagementTypedHandler()),
    ),

    "engagement set-branch": CommandDef(
        key="engagement set-branch",
        help_text="Set the branch for an engagement (explicit repoint).",
        cmd_cls=SetBranchCommand,
        click=ClickParams(
            group="engagement",
            arguments=[
                {"name": "slug", "type": str, "required": True},
                {"name": "branch", "type": str, "required": True},
            ],
        ),
        bus=BusDef(handler=SetBranchTypedHandler()),
    ),

    "engagement fix": CommandDef(
        key="engagement fix",
        help_text="Fix missing engagement metadata and state issues.",
        cmd_cls=FixEngagementCommand,
        click=ClickParams(
            group="engagement",
            options=[{"opts": ["--engagement"], "type": str, "help": "Engagement slug (default: active)"}],
        ),
        bus=BusDef(handler=FixEngagementTypedHandler()),
    ),

    "engagement set-active": CommandDef(
        key="engagement set-active",
        help_text="Set an existing engagement as active on the current branch.",
        # Pure Click — this command reads files and writes YAML directly
        # without going through the CommandBus. That's acceptable because
        # it's a filesystem operation that doesn't benefit from bus middleware.
        bus=None,
        click=ClickParams(
            group="engagement",
            arguments=[{"name": "slug", "type": str, "required": True}],
        ),
        # Mark as CLI-only explicitly
        repl=None,
    ),

    "engagement list": CommandDef(
        key="engagement list",
        help_text="List all engagements in the project.",
        # Pure Click — scans directories / reads metadata files.
        # Acceptable until the engagement listing capability is migrated
        # to a TypedCommand.
        bus=None,
        click=ClickParams(group="engagement"),
        repl=None,
    ),

    "engagement diff": CommandDef(
        key="engagement diff",
        help_text="Compare baseline assessment to current state.",
        bus=None,
        click=ClickParams(
            group="engagement",
            options=[{"opts": ["--engagement"], "type": str, "help": "Engagement slug (default: active)"}],
        ),
        repl=None,
    ),

    "engagement engagement-status": CommandDef(
        key="engagement engagement-status",
        # NOTE: click name override to avoid conflict with top-level "status"
        click=ClickParams(
            group="engagement",
            name="status",
            options=[{"opts": ["--engagement"], "type": str, "help": "Engagement slug"}],
        ),
        help_text="Show detailed status of an engagement.",
        bus=None,
        repl=None,
    ),

    # ═══════════════════════════════════════════════════════════════════
    # Agent group commands
    # ═══════════════════════════════════════════════════════════════════

    "agent list": CommandDef(
        key="agent list",
        help_text="List all registered harness agent roles.",
        cmd_cls=AgentListCommand,
        click=ClickParams(group="agent", name="list"),
        bus=BusDef(handler=AgentListTypedHandler()),
    ),

    "agent show": CommandDef(
        key="agent show",
        help_text="Show details for a specific agent role.",
        bus=None,
        click=ClickParams(
            group="agent",
            arguments=[{"name": "agent_role", "type": str, "required": True}],
        ),
        repl=None,
    ),

    # ═══════════════════════════════════════════════════════════════════
    # Team group commands
    # ═══════════════════════════════════════════════════════════════════

    "team list": CommandDef(
        key="team list",
        help_text="List all registered teams with their agents.",
        cmd_cls=TeamListCommand,
        click=ClickParams(
            group="team",
            name="list",
            options=[{"opts": ["--consults"], "is_flag": True,
                      "help": "Show consultation capabilities"}],
        ),
        bus=BusDef(handler=TeamListTypedHandler()),
    ),

    "team show": CommandDef(
        key="team show",
        help_text="Show details for a specific team.",
        bus=None,
        click=ClickParams(
            group="team",
            arguments=[{"name": "team_name", "type": str, "required": True}],
            options=[{"opts": ["--json"], "is_flag": True, "help": "Output as JSON"}],
        ),
        repl=None,
    ),

    "team add-agent": CommandDef(
        key="team add-agent",
        help_text="Add an agent role to a team (informational — use teams.yaml).",
        bus=None,
        click=ClickParams(
            group="team",
            name="add-agent",
            arguments=[
                {"name": "team_name", "type": str, "required": True},
                {"name": "agent_role", "type": str, "required": True},
            ],
        ),
        repl=None,
    ),

    "team remove-agent": CommandDef(
        key="team remove-agent",
        help_text="Remove an agent role from a team (informational — use teams.yaml).",
        bus=None,
        click=ClickParams(
            group="team",
            name="remove-agent",
            arguments=[
                {"name": "team_name", "type": str, "required": True},
                {"name": "agent_role", "type": str, "required": True},
            ],
        ),
        repl=None,
    ),

    "team consult": CommandDef(
        key="team consult",
        help_text="Show consultation capabilities for a team.",
        bus=None,
        click=ClickParams(
            group="team",
            arguments=[{"name": "team_name", "type": str, "required": True}],
            options=[{"opts": ["--no-truncate"], "is_flag": True}],
        ),
        repl=None,
    ),

    "team set-governance": CommandDef(
        key="team set-governance",
        help_text="Set the governance level for the project or an engagement.",
        cmd_cls=SetGovernanceCommand,
        click=ClickParams(
            group="team",
            arguments=[{"name": "level", "type": str, "required": True}],
            options=[{"opts": ["--engagement"], "type": str, "help": "Engagement slug"}],
        ),
        bus=BusDef(handler=SetGovernanceTypedHandler()),
    ),

    # ═══════════════════════════════════════════════════════════════════
    # Wave group commands
    # ═══════════════════════════════════════════════════════════════════

    "wave list": CommandDef(
        key="wave list",
        help_text="List waves from the engagement plan.",
        cmd_cls=ListWavesCommand,
        click=ClickParams(
            group="wave",
            name="list",
            options=[{"opts": ["--engagement"], "type": str, "help": "Engagement slug"}],
        ),
        bus=BusDef(handler=ListWavesTypedHandler()),
    ),

    "wave run": CommandDef(
        key="wave run",
        help_text="Run a wave through the implement-test-verify-commit cycle.",
        cmd_cls=RunWaveCommand,
        click=ClickParams(
            group="wave",
            arguments=[{"name": "wave_id", "type": str, "required": True}],
            options=[
                {"opts": ["--no-test"], "is_flag": True, "help": "Skip test suite execution"},
                {"opts": ["--backend"], "type": str, "help": "Agent backend name"},
                {"opts": ["--engagement"], "type": str, "help": "Engagement slug"},
            ],
        ),
        bus=BusDef(handler=RunWaveTypedHandler()),
    ),

    "wave status": CommandDef(
        key="wave status",
        help_text="Show detailed wave status from the engagement plan.",
        cmd_cls=WaveStatusCommand,
        click=ClickParams(
            group="wave",
            options=[{"opts": ["--engagement"], "type": str, "help": "Engagement slug"}],
        ),
        bus=BusDef(handler=WaveStatusTypedHandler()),
    ),

    "wave create-from-finding": CommandDef(
        key="wave create-from-finding",
        help_text="Create a wave from an assessment finding.",
        cmd_cls=CreateWaveFromFindingCommand,
        click=ClickParams(
            group="wave",
            name="create-from-finding",
            arguments=[{"name": "finding_id", "type": str, "required": True}],
            options=[{"opts": ["--engagement"], "type": str, "help": "Engagement slug"}],
        ),
        bus=BusDef(handler=CreateWaveFromFindingTypedHandler()),
    ),

    "wave create-from-assessment": CommandDef(
        key="wave create-from-assessment",
        help_text="Create waves from all matching assessment findings.",
        cmd_cls=CreateWavesFromAssessmentCommand,
        click=ClickParams(
            group="wave",
            name="create-from-assessment",
            options=[
                {"opts": ["--focus"], "type": str, "default": "high-risk"},
                {"opts": ["--limit"], "type": int, "default": 0},
                {"opts": ["--refactoring"], "is_flag": True},
                {"opts": ["--engagement"], "type": str, "help": "Engagement slug"},
            ],
        ),
        bus=BusDef(handler=CreateWavesFromAssessmentTypedHandler()),
    ),

    # ═══════════════════════════════════════════════════════════════════
    # Changelog group commands
    # ═══════════════════════════════════════════════════════════════════

    "changelog annotate": CommandDef(
        key="changelog annotate",
        help_text="Append a human annotation to the latest changelog entry.",
        cmd_cls=AnnotateChangelogCommand,
        click=ClickParams(
            group="changelog",
            arguments=[
                {"name": "engagement_slug", "type": str, "required": True},
                {"name": "text", "type": str, "required": True},
            ],
        ),
        bus=BusDef(handler=AnnotateChangelogTypedHandler()),
    ),

    # ═══════════════════════════════════════════════════════════════════
    # Click-only commands with explicit bus=None, repl=None
    # ═══════════════════════════════════════════════════════════════════

    "workflows": CommandDef(
        key="workflows",
        help_text="Show workflow guidance and when to use each workflow.",
        bus=None,       # Does not go through the CommandBus
        repl=None,      # Intentionally CLI-only (informational help text)
        click=ClickParams(),
    ),

    "health": CommandDef(
        key="health",
        help_text="Run configuration and state validation checks.",
        bus=None,
        repl=None,      # Currently CLI-only — could be migrated to bus
        click=ClickParams(
            options=[
                {"opts": ["--verbose"], "is_flag": True},
                {"opts": ["--fix"], "is_flag": True, "help": "Attempt to auto-fix issues"},
            ],
        ),
    ),

    "shell": CommandDef(
        key="shell",
        help_text="Launch an interactive REPL with tab completion.",
        bus=None,
        repl=None,      # REPL built-in (runs the REPL itself — infinite recursion)
        click=ClickParams(),
    ),

    # ═══════════════════════════════════════════════════════════════════
    # Dead commands — deprecated, not wired anywhere
    # ═══════════════════════════════════════════════════════════════════

    "engagement resume": CommandDef(
        key="engagement resume",
        help_text="Resume an existing engagement. (Deprecated — not wired)",
        cmd_cls=None,   # No CLI definition
        click=None,     # Not in CLI
        repl=None,      # Not in REPL
        deprecated=True,
    ),

    "wave create": CommandDef(
        key="wave create",
        help_text="Create a new wave. (Deprecated — not wired)",
        cmd_cls=None,
        click=None,
        repl=None,
        deprecated=True,
    ),

    "wave execute-step": CommandDef(
        key="wave execute-step",
        help_text="Execute a single step in a wave. (Deprecated — not wired)",
        cmd_cls=None,
        click=None,
        repl=None,
        deprecated=True,
    ),
}
```

**Key design decisions in the registry:**

1. **Dead commands** are explicitly deprecated rather than absent — the sync test can flag any command defined in `setup.py` that has no registry entry and assert it's either registered or deprecated.
2. **Click-only commands** use `bus=None, repl=None` — explicit opt-out, not accidental omission.
3. **Bus-only commands** could declare `click=None` and be registered with the bus for programmatic dispatch without CLI/REPL exposure.
4. **Every command gets an entry** — no command exists outside the registry, even temporarily.

---

## 3. Click CLI Generation

Replace the manual `@click.command()` / `@group.command()` decorators in `main.py` with a builder function that reads from `COMMAND_REGISTRY`.

### 3.1 Builder Function

```python
# src/harness/cli/_builder.py

from __future__ import annotations

import click
from harness.command.registry import COMMAND_REGISTRY, CommandDef, ClickParams


def _build_param(param_def: dict) -> click.Parameter:
    """Build a Click parameter from a declarative param dict."""
    if "multiple" in param_def and param_def.get("multiple"):
        # Repeatable option (e.g. --finding)
        return click.option(
            *param_def["opts"],
            multiple=True,
            default=param_def.get("default"),
            help=param_def.get("help", ""),
        )
    if param_def.get("is_flag"):
        flag = param_def["opts"][0]
        is_flag = "/" not in flag  # not a --foo/--no-foo pair
        kwargs = dict(is_flag=is_flag, help=param_def.get("help", ""))
        if "/" in flag:
            kwargs["is_flag"] = True  # default for --foo/--no-foo
        return click.option(flag, **kwargs)
    if "nargs" in param_def:
        return click.argument(
            param_def["name"],
            nargs=param_def["nargs"],
            required=True,
        )
    return click.argument(
        param_def["name"],
        type=param_def.get("type", str),
        required=param_def.get("required", True),
    )


def _make_click_command(defn: CommandDef) -> click.Command:
    """Generate a Click command from a CommandDef.

    If the command has a cmd_cls and handler, the generated Click
    function dispatches through the CommandBus. If it's Click-only
    (no cmd_cls), the function body is left as a stub that must be
    manually defined elsewhere (or we provide a ``click_fn`` callback).
    """
    params = defn.click
    if params is None:
        raise ValueError(f"Command {defn.key} has no Click params")

    # Build decorator list
    decorators = list(params.raw_click_decorators)

    # Build click params
    for arg in params.arguments:
        decorators.append(_build_param(arg))
    for opt in params.options:
        decorators.append(_build_param(opt))

    # Build the function — bus-dispatched or click-only stub
    if defn.cmd_cls and defn.bus:
        func_body = _make_bus_dispatch_fn(defn)
    else:
        # Click-only or stub — we use a placeholder that invokes raw_fn
        func_body = _make_click_only_fn(defn)

    # Apply decorators in reverse order (Click applies bottom-up)
    for decorator in reversed(decorators):
        func_body = decorator(func_body)

    cmd_name = (params.name or defn.key.split()[-1]).replace("-", "_")
    fn = click.command(name=cmd_name)(func_body)
    fn.help = defn.help_text
    return fn


def _make_bus_dispatch_fn(defn: CommandDef) -> Callable:
    """Generate a Click function that dispatches through the CommandBus."""

    def _handler(**kwargs):
        try:
            from harness.command.setup import get_shared_bus
            bus = get_shared_bus()
            cmd = defn.cmd_cls(**kwargs)
            result = bus.dispatch(cmd)
            if not result.success:
                click.echo(f"Error: {result.error or result.message}", err=True)
                raise click.Abort()
            if result.message:
                click.echo(result.message)
            # Print data if available
            data = result.data
            if data and isinstance(data, dict):
                for key, value in data.items():
                    if key not in ("typed_result",) and value:
                        click.echo(f"  {key}: {value}")
        except click.Abort:
            raise
        except Exception as exc:
            click.echo(f"Error: {exc}", err=True)
            raise click.Abort()

    # Switch __name__ based on Click naming convention
    _handler.__name__ = defn.click.name or defn.key.split()[-1].replace("-", "_")
    return _handler


def _make_click_only_fn(defn: CommandDef) -> Callable:
    """Generate a placeholder function for click-only commands.

    These still need function bodies. The generated function raises
    a clear error unless the caller provides a ``raw_fn`` via the
    legacy decorator mechanism.

    In phase 1, we keep the original Click function bodies alongside
    the registry. In phase 2, we migrate them into the registry or
    into handler-files.
    """
    def _stub(**kwargs):
        click.echo(f"Command '{defn.key}' is Click-only and has no registered callback.")
        raise click.Abort()

    _stub.__name__ = (defn.click.name or defn.key.split()[-1]).replace("-", "_")
    return _stub


def build_click_cli() -> click.Group:
    """Build the full Click CLI tree from COMMAND_REGISTRY.

    Returns a ``click.Group`` (``main``) with all sub-groups
    and commands attached, ready for ``cli.main = build_click_cli()``.
    """
    from click import Group, Command

    main = Group(
        name="main",
        help="Dev Harness — agent orchestration for software development.",
    )

    # Phase 1: collect all groups
    groups: dict[str, Group] = {}

    for key, defn in COMMAND_REGISTRY.items():
        if defn.click is None:
            continue  # Not a Click command

        cmd = _make_click_command(defn)

        if defn.click.group:
            parent = defn.click.group
            if parent not in groups:
                # Create the group lazily — we need the help text from main.py
                groups[parent] = Group(name=parent, help=f"Manage {parent}s.")
            groups[parent].add_command(cmd)
        else:
            main.add_command(cmd)

    # Add groups to main
    for name, group in groups.items():
        main.add_command(group)

    return main
```

### 3.2 Migration: `main.py` transformation

**Before** (current):
```python
@main.group()
def agent():
    """List, show, and run harness agents."""
    pass

@agent.command(name="list")
def list_agents():
    """..."""
    from harness.agents.agent_registry import AGENTS, list_agent_roles
    # ... 40 lines of inline logic
```

**After** (phase 1 — registry + keep inline bodies):
```python
# Phase 1: Registry is source of truth for wiring;
# Click function bodies still exist in main.py as "raw fns"
# referenced by the registry.

_RAW_FNS: dict[str, Callable] = {}

def register_raw(key: str):
    """Decorator to register a raw Click function body for a command."""
    def decorator(fn):
        _RAW_FNS[key] = fn
        return fn
    return decorator

# Then in _make_click_only_fn / _make_bus_dispatch_fn:
# - If defn.cmd_cls and defn.bus: use bus dispatch (generated)
# - Else: look up _RAW_FNS[defn.key] and use that as the function body
```

**After** (phase 2 — all bodies migrated):
```python
# main.py becomes entirely generated from the registry.
# Custom Click-only logic moves to handler files or helper modules.

from harness.cli._builder import build_click_cli
main = build_click_cli()
```

---

## 4. REPL Command Map Generation

### 4.1 Auto-generate `COMMAND_TYPES` from the Registry

```python
# src/harness/shell/_repl_registry.py

from harness.command.registry import COMMAND_REGISTRY, CommandDef, ReplDef, ClickParams


def _auto_arg_parser(defn: CommandDef) -> Callable[[list[str]], dict[str, Any]]:
    """Auto-generate an arg parser from ClickParams.

    Generates a simple positional-then-flag parser that:
    1. Consumes positional args in order
    2. Parses --flag value pairs from remaining args
    3. Returns a kwargs dict suitable for the command dataclass
    """
    params = defn.click
    if params is None:
        raise ValueError(f"Cannot auto-parse {defn.key}: no Click params")

    def _parser(args: list[str]) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        remaining = list(args)
        positional_idx = 0

        while remaining:
            arg = remaining.pop(0)
            if arg.startswith("--"):
                # Option parsing
                opt_name = arg.lstrip("-").replace("-", "_")
                # Find the option def
                opt_def = None
                for opt in params.options:
                    if opt_name in [o.lstrip("-").replace("-", "_") for o in opt["opts"]]:
                        opt_def = opt
                        break
                if opt_def is None:
                    continue  # Unknown flag, skip
                if opt_def.get("is_flag") or "/" in " ".join(opt_def.get("opts", [])):
                    kwargs[opt_name] = True
                elif opt_def.get("multiple"):
                    # Collect remaining occurrences
                    values = [remaining.pop(0)] if remaining else []
                    kwargs.setdefault(opt_name, []).extend(values)
                else:
                    kwargs[opt_name] = remaining.pop(0) if remaining else opt_def.get("default")
            else:
                # Positional argument
                if positional_idx < len(params.arguments):
                    arg_def = params.arguments[positional_idx]
                    # Check nargs=-1 (greedy capture)
                    if arg_def.get("nargs", 1) == -1:
                        kwargs[arg_def["name"]] = [arg] + remaining
                        remaining.clear()
                    elif arg_def.get("nargs", 1) > 1:
                        vals = [arg]
                        while remaining and len(vals) < arg_def["nargs"]:
                            vals.append(remaining.pop(0))
                        kwargs[arg_def["name"]] = vals
                    else:
                        kwargs[arg_def["name"]] = arg
                    positional_idx += 1
                else:
                    # Extra positional — likely wrong, but be lenient
                    pass

        return kwargs

    return _parser


def build_repl_command_map() -> dict[str, tuple[type, Callable]]:
    """Build the REPL COMMAND_TYPES dict from COMMAND_REGISTRY.

    Returns a dict matching the current COMMAND_TYPES format so
    the existing REPL dispatch loop works unchanged.
    """
    result: dict[str, tuple[type, Callable]] = {}

    for key, defn in COMMAND_REGISTRY.items():
        if defn.repl is None:
            continue  # CLI-only command

        if defn.cmd_cls is None:
            continue  # Click-only — no command dataclass to dispatch

        if defn.repl.arg_parser:
            arg_parser = defn.repl.arg_parser
        elif defn.repl.auto_parse and defn.click is not None:
            arg_parser = _auto_arg_parser(defn)
        else:
            continue  # No arg parser available

        result[key] = (defn.cmd_cls, arg_parser)

    return result
```

### 4.2 Integration into REPL

The REPL's `COMMAND_TYPES` dict (line 224) is replaced with a call to `build_repl_command_map()`:

```python
# In repl.py, replace the static COMMAND_TYPES dict:

# Before:
COMMAND_TYPES: dict[str, tuple[type, Callable]] = {
    "engagement create": (CreateEngagementCommand, _engagement_create_args),
    # ... 30 manually-maintained entries
}

# After:
from harness.shell._repl_registry import build_repl_command_map
COMMAND_TYPES = build_repl_command_map()
```

This is a backward-compatible change — the dict's shape is identical. The static arg parser functions (`_single_arg`, `_engagement_create_args`, etc.) remain in `repl.py` for now, but are either:
1. Migrated into the `CommandDef.repl.arg_parser` field, or
2. Replaced by auto-generated parsers from `_auto_arg_parser()`

---

## 5. Handler Registration

### 5.1 Auto-generate `bus.register_type()` from the Registry

```python
# src/harness/command/_bus_builder.py

from harness.command.registry import COMMAND_REGISTRY
from harness.command.bus import CommandBus


def register_handlers(bus: CommandBus) -> None:
    """Register all typed handlers from COMMAND_REGISTRY onto a bus.

    This replaces all manual ``bus.register_type()`` calls in setup.py.
    """
    for key, defn in COMMAND_REGISTRY.items():
        if defn.bus is None or defn.cmd_cls is None:
            continue
        bus.register_type(defn.bus.handler, defn.cmd_cls)
```

### 5.2 Simplified `setup.py`

```python
# src/harness/command/setup.py — simplified

from harness.command.bus import CommandBus
from harness.command._bus_builder import register_handlers

_SHARED_BUS: CommandBus | None = None


def _build_bus() -> CommandBus:
    bus = CommandBus()
    register_handlers(bus)
    return bus


def create_bus() -> CommandBus:
    return _build_bus()


def get_shared_bus() -> CommandBus:
    global _SHARED_BUS
    if _SHARED_BUS is None:
        _SHARED_BUS = _build_bus()
    return _SHARED_BUS


def reset_shared_bus() -> None:
    global _SHARED_BUS
    _SHARED_BUS = None
```

This removes **33 manual `bus.register_type()` calls** and their associated imports.

---

## 6. Arg Parser Unification

### 6.1 The Two Current Approaches

| Aspect | Click Decorators | REPL Arg Parsers |
|--------|-----------------|-----------------|
| Positional args | `@click.argument("name")` | Manual list indexing: `args[0]` |
| Flags | `@click.option("--foo")` | Manual flag iteration |
| Flag values | Injected by Click | Manual `while i < len(args)` |
| Multiple flags | `@click.option("--finding", multiple=True)` | Manual accumulation |
| Flag defaults | Set in decorator | Set in parser function |
| Type coercion | Automatic (str, int, choice) | Manual (`int(args[i+1])`) |

### 6.2 Auto-Generated Arg Parser

The `_auto_arg_parser()` function in §4.1 is the unification mechanism. It reads the same `ClickParams` that generate the Click decorators and produces a REPL-compatible parser. This means:

- **One declaration** in `ClickParams.arguments` / `ClickParams.options`
- **Two derivations**: Click decorator + REPL arg parser
- **No drift**: both always parse the same way

### 6.3 Migration Path for Custom Parsers

Custom parsers (like `_work_args` which does slug derivation) are not eliminated — they're moved into the `CommandDef.repl.arg_parser` field:

```python
"work": CommandDef(
    key="work",
    cmd_cls=CreateEngagementCommand,
    click=ClickParams(
        arguments=[{"name": "description", ...}],
        options=[...],
    ),
    repl=ReplDef(
        # Custom parser needed because /work derives slug from description
        auto_parse=False,
        arg_parser=_work_args,
    ),
    bus=BusDef(handler=CreateEngagementHandler()),
),
```

Only commands with genuinely different REPL vs CLI argument semantics need custom parsers. Initially, **all** commands keep their old parsers (moved into `repl.arg_parser`). Over time, each custom parser is either:
1. Replaced by `auto_parse=True` (if REPL and CLI args are identical), or
2. Kept as a custom parser in `repl.arg_parser` (if genuinely different)

### 6.4 What Makes REPL and CLI Args Different

The only commands where REPL args differ from CLI args:

| Command | CLI | REPL | Difference |
|---------|-----|------|------------|
| `work` | `harness work "description" --mode auto` | `/work description --mode auto` | CLI has quotes; REPL joins all non-flag tokens |
| `init` | `harness init [dir] [--template]` | `/init [dir] [--template]` | Nearly identical |
| `finish` | `harness finish --re-assess` | `/finish --re-assess` | Identical |
| `review` | `harness review id --approve` | `/review id --approve` | Identical |
| `phase` | `harness phase --list` | `/phase [eng_id] --list` | Slightly different arg order |
| `summary` | `harness summary --engagement X --deep` | `/summary X --deep` | Minor positional difference |
| `engagement create` | `harness engagement create "name"` | `/engagement create name` | Identical (both use positional first arg) |

The auto-parser handles the common case (positional args + flag/value pairs). For edge cases like `work` slug derivation, custom parsers remain.

---

## 7. Test Strategy

### 7.1 Core Sync Test

The single most important test — runs in CI, fails loudly if any command appears in only one dispatch path:

```python
# tests/unit/command/test_registry_sync.py

from harness.command.registry import COMMAND_REGISTRY
from harness.command._bus_builder import register_handlers
from harness.command.bus import CommandBus
from harness.shell._repl_registry import build_repl_command_map


class TestCommandRegistrySync:
    """Verifies that the CommandDef registry is the single source of truth.

    Every command must be present in the registry. No command should
    exist in only one of: CLI, REPL, Bus — unless explicitly exempted.
    """

    def test_all_commands_have_registry_entry(self):
        """Every known command key is in the registry.

        The known set is built from:
        - All Click commands in main.py
        - All REPL COMMAND_TYPES entries
        - All bus.register_type() registrations
        - All known dead commands (deprecated but still registered in setup.py)
        """
        from harness.cli.main import main as cli_main

        # Build flat command names from Click tree
        click_commands: set[str] = set()
        for name, cmd in cli_main.commands.items():
            if isinstance(cmd, click.Group):
                for sub_name in cmd.commands:
                    click_commands.add(f"{name} {sub_name}")
            else:
                click_commands.add(name)

        # Build from REPL COMMAND_TYPES (old-style, for migration period)
        from harness.shell.repl import COMMAND_TYPES as legacy_ct
        repl_keys = set(legacy_ct.keys())

        # Build from bus registrations (old-style)
        from harness.command.setup import _build_bus
        bus = _build_bus()
        bus_registered = set(bus._type_handlers.keys())
        handler_cmd_names: set[str] = set()
        for cmd_type in bus_registered:
            # Map command class to its registry key by scanning registry
            for key, defn in COMMAND_REGISTRY.items():
                if defn.cmd_cls is cmd_type and not defn.deprecated:
                    handler_cmd_names.add(key)

        # All known commands
        all_known = click_commands | repl_keys | handler_cmd_names

        # Plus deprecated commands that exist in setup.py but not elsewhere
        # (these have cmd_cls set but no click/no repl — they'll fail the
        # full-coverage test below unless deprecated)
        from harness.command.commands.engagement import ResumeEngagementCommand
        from harness.command.commands.wave import CreateWaveCommand, ExecuteStepCommand
        deprecated_in_bus = {
            ResumeEngagementCommand,
            CreateWaveCommand,
            ExecuteStepCommand,
        }
        for cmd_type in deprecated_in_bus:
            # Find or add their registry entry
            found = any(
                defn.cmd_cls is cmd_type for defn in COMMAND_REGISTRY.values()
            )
            if not found:
                # These exist in setup.py but NOT in the registry — test fails
                pytest.fail(
                    f"Command {cmd_type.__name__} is registered in bus "
                    f"but missing from COMMAND_REGISTRY. Add it or remove "
                    f"the handler registration."
                )

        # Assert all known commands are in the registry
        for key in all_known:
            assert key in COMMAND_REGISTRY, (
                f"Command '{key}' found in Click/REPL/bus but missing "
                f"from COMMAND_REGISTRY"
            )

    def test_registry_covers_all_click_commands(self):
        """Every Click command has a registry entry (even if bus=None)."""
        from harness.cli.main import main as cli_main

        click_commands: set[str] = set()
        for name, cmd in cli_main.commands.items():
            if isinstance(cmd, click.Group):
                for sub_name in cmd.commands:
                    click_commands.add(f"{name} {sub_name}")
            else:
                click_commands.add(name)

        registered = set(COMMAND_REGISTRY.keys())
        missing = click_commands - registered
        assert not missing, (
            f"Click commands missing from COMMAND_REGISTRY: "
            f"{sorted(missing)}"
        )

    def test_no_dead_code_not_in_registry(self):
        """Every bus-registered command is in the registry (possibly deprecated)."""
        from harness.command.setup import _build_bus
        bus = _build_bus()

        registered_cmd_types = set()
        for key, defn in COMMAND_REGISTRY.items():
            if defn.cmd_cls is not None:
                registered_cmd_types.add(defn.cmd_cls)

        for cmd_type in bus._type_handlers:
            if cmd_type not in registered_cmd_types:
                pytest.fail(
                    f"Handler for {cmd_type.__name__} is registered in setup.py "
                    f"but NOT in COMMAND_REGISTRY. Add an entry (even if "
                    f"deprecated=True)."
                )

    def test_repl_map_matches_registry(self):
        """REPL command map reflects the registry's repl-enabled commands."""
        from harness.shell.repl import COMMAND_TYPES as legacy_ct

        registry_map = build_repl_command_map()

        # During migration: registry_map should be a superset of legacy_ct
        # (modulo commands with repl=None that are intentionally CLI-only)
        for key in legacy_ct:
            assert key in registry_map or key not in COMMAND_REGISTRY, (
                f"REPL command '{key}' exists in legacy COMMAND_TYPES "
                f"but not in registry's build_repl_command_map() output. "
                f"If it's in the registry, check repl= is set correctly."
            )

    def test_every_registry_entry_dispatches(self):
        """Every registry entry with cmd_cls+bus dispatches without error.

        This validates that the bus wiring is complete — no missing
        handlers, no import errors, no unknown command types.
        """
        from harness.command.setup import _build_bus
        bus = _build_bus()

        for key, defn in COMMAND_REGISTRY.items():
            if defn.cmd_cls is None or defn.bus is None:
                continue  # Click-only or CLI-only — skip

            # Instantiate the command with default kwargs
            try:
                cmd = defn.cmd_cls()
            except TypeError:
                # Has required fields — skip full instantiation test
                continue

            try:
                result = bus.dispatch(cmd)
                # We don't check success/failure (depends on filesystem state),
                # only that dispatch doesn't raise UnknownCommandError
            except Exception as exc:
                if "No handler registered" in str(exc):
                    pytest.fail(
                        f"Command '{key}' ({defn.cmd_cls.__name__}) has no "
                        f"handler registered on the bus. Check that "
                        f"register_handlers() covers it."
                    )
    def test_arg_parsers_produce_valid_kwargs(self):
        """REPL arg parsers produce valid kwargs for their command dataclass."""
        for key, defn in COMMAND_REGISTRY.items():
            if defn.cmd_cls is None:
                continue
            if defn.repl is None:
                continue

            parser = defn.repl.arg_parser
            if parser is None and defn.repl.auto_parse and defn.click:
                from harness.shell._repl_registry import _auto_arg_parser
                parser = _auto_arg_parser(defn)

            if parser is None:
                continue

            # Test with empty args (positionals get defaults)
            kwargs = parser([])
            try:
                defn.cmd_cls(**kwargs)
            except TypeError as exc:
                pytest.fail(
                    f"Arg parser for '{key}' produced kwargs {kwargs} "
                    f"that raised: {exc}"
                )

    def test_click_generation_is_valid(self):
        """Generated Click commands have valid structure.

        This catches malformed ClickParams that would cause runtime errors.
        """
        from harness.cli._builder import _make_click_command

        for key, defn in COMMAND_REGISTRY.items():
            if defn.click is None:
                continue  # Not a Click command
            try:
                cmd = _make_click_command(defn)
                assert isinstance(cmd, click.Command), (
                    f"Generated command for '{key}' is not a click.Command"
                )
            except Exception as exc:
                pytest.fail(
                    f"Failed to generate Click command for '{key}': {exc}"
                )

    def test_no_unregistered_registry_entries(self):
        """Every non-deprecated registry entry is wired somewhere.

        A command should not be in the registry with cmd_cls + bus
        but no click and no repl — that means it's registered but
        has no UI. This is OK for deprecated commands and pure
        programmatic commands, but must be explicit.
        """
        for key, defn in COMMAND_REGISTRY.items():
            if defn.deprecated:
                continue
            if defn.cmd_cls is not None and defn.bus is not None:
                has_click = defn.click is not None
                has_repl = defn.repl is not None
                if not has_click and not has_repl:
                    pytest.fail(
                        f"Command '{key}' has cmd_cls + handler but no "
                        f"click or repl definition. Either add UI exposure "
                        f"or mark as deprecated=True."
                    )
```

### 7.2 Pipeline Integration

```
┌─────────────────────────────────────────────────────────────┐
│                    CI Pipeline Gate                          │
├─────────────────────────────────────────────────────────────┤
│ 1. test_registry_sync.py::test_registry_covers_all_click_   │
│    commands  →  fails if a Click command has no registry    │
│                 entry (even bus=None)                        │
├─────────────────────────────────────────────────────────────┤
│ 2. test_registry_sync.py::test_no_dead_code_not_in_registry │
│    →  fails if setup.py registers a handler for a command   │
│       not in the registry                                    │
├─────────────────────────────────────────────────────────────┤
│ 3. test_registry_sync.py::test_repl_map_matches_registry    │
│    →  fails if the legacy COMMAND_TYPES has entries not     │
│       derivable from the registry                            │
├─────────────────────────────────────────────────────────────┤
│ 4. test_registry_sync.py::test_every_registry_entry_        │
│    dispatches  →  fails if a registered command can't be    │
│    dispatched (missing handler, import error)                │
├─────────────────────────────────────────────────────────────┤
│ 5. test_registry_sync.py::test_arg_parsers_produce_valid_   │
│    kwargs  →  fails if parser returns kwargs that don't     │
│    construct the command dataclass                           │
├─────────────────────────────────────────────────────────────┤
│ 6. test_registry_sync.py::test_click_generation_is_valid    │
│    →  fails if ClickParams is malformed                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Migration Path

### Phase 0: Immediate Fix (Hours)
- Add the **sync tests** to CI even before registry exists — they'll fail loudly
- This documents the problem and prevents further drift
- See Step 2 in Crichton's analysis for the test

### Phase 1: Registry as Parallel Source of Truth (Days)
1. Create `src/harness/command/registry.py` with `CommandDef` dataclass and `COMMAND_REGISTRY`
2. Populate with all 39+ commands, keeping `bus=None` and `repl=None` for Click-only commands
3. Create `_repl_registry.py` with `build_repl_command_map()`
4. Create `_bus_builder.py` with `register_handlers()`
5. **Do NOT delete old wiring** — the registry runs alongside it
6. Add sync tests that compare registry vs old wiring
7. Fix any discovered gaps (REPL fixes for engagement sub-commands, etc.)

**At this point:**
- The registry is not yet the source of truth — it mirrors reality
- Sync tests pass only when real wiring matches registry
- Adding a new command requires: `CommandDef` entry (one place) + sync test passes

### Phase 2: Gradual Adoption (Weeks)
Per command, migrate from old wiring to registry-auto-generated:

1. **REPL map first**: 
   - Replace `COMMAND_TYPES` static dict → `build_repl_command_map()` call
   - Move custom arg parsers into `CommandDef.repl.arg_parser`
   - Validate all commands still work in REPL

2. **Bus registration second**:
   - Replace `setup.py` → `register_handlers()` call
   - Remove all manual `bus.register_type()` calls and their imports
   - Validate all bus-dispatchable commands still work

3. **Click CLI third** (most disruptive):
   - Replace `@main.command()` bodies in `main.py` with registry-generated functions
   - For bus-dispatchable commands: auto-generate the Click function (wraps `bus.dispatch()`)
   - For Click-only commands: inline bodies remain in a `_RAW_FNS` dict, referenced by the registry
   - Gradually migrate Click-only bodies into handler files

### Phase 3: Full Generation (Weeks-Months)
- `main.py` is fully generated: `main = build_click_cli()`
- All Click-only command logic lives in handler modules or helper modules
- `setup.py` is fully generated: `_build_bus()` calls `register_handlers()`
- `COMMAND_TYPES` is fully generated: `build_repl_command_map()`
- The three-generation functions are the only wiring in the system

### Migration Order (by Command)

**Wave 1 (2-3 commands, prove the pattern):**
- `engagement create` — full pipeline, has custom arg parser
- `workflows` — Click-only, `bus=None, repl=None`
- `agent list` — simple bus-dispatchable

**Wave 2 (remaining bus-dispatchable commands):**
- All commands that currently have `cmd_cls + handler + COMMAND_TYPES` entries
- ~27 commands, bulk migrate via registry import generator

**Wave 3 (Click-only commands):**
- `engagement list`, `diff`, `engagement-status`, `set-active`
- `agent show`, `team show`, `team add-agent`, `team remove-agent`, `team consult`
- `health`, `shell`, `workflows`
- Each either gets a handler or stays Click-only with `bus=None, repl=None`

**Wave 4 (dead code):**
- `engagement resume`, `wave create`, `wave execute-step`
- Add to registry as `deprecated=True`
- Sync test asserts they're either removed from `setup.py` or added to registry

---

## 9. Decision Log

| Decision | Rationale | Alternatives Rejected |
|----------|-----------|----------------------|
| Flat dict keyed by canonical name | Simple, fast lookup, easy to grep | Nested hierarchy (harder to iterate) |
| Separate `ClickParams` / `ReplDef` / `BusDef` objects | Each is independently optional; avoids a single huge flat dataclass with 20 optional fields | One big flat dataclass with all fields |
| `bus=None` for Click-only | Explicit opt-out, not implicit omission | Separate `is_click_only=True` flag |
| `deprecated=True` for dead commands | Prevents them from being silently forgotten | Deleting them immediately (risky — someone may depend on them) |
| Auto-generated arg parser from `ClickParams` | One declaration, two derivations — no drift | Two independent parsers (current approach — broken by design) |
| Phase migration (registry parallel first) | Zero risk — old wiring still works | Big-bang rewrite (too risky, too much down-time) |
| Sync tests run in Phase 0 | Prevents further drift while migration happens | Add tests only after migration (allows more drift in the meantime) |
| Keep Click-only bodies in `_RAW_FNS` during migration | No need to refactor 10+ inline functions upfront | Fork-lift all inline logic into handlers (disproportionate effort) |

---

## 10. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Auto-generated arg parser misses edge cases | Medium | Low | Custom `arg_parser` escape hatch; sync test validates runtime |
| Click generation produces different CLI than current | Medium | Medium | `test_click_generation_is_valid` plus manual smoke test |
| Circular imports from registry importing too many modules | Medium | High | Keep `COMMAND_REGISTRY` in a dedicated module; lazy imports in generation functions |
| Developer bypasses registry and adds raw Click decorator | Low | High | Sync test in CI catches it immediately with clear failure message |
| Migration takes longer than expected | High | Low | Phase 1 is sufficient to enforce discipline; full generation is polish |
| Deprecated dead commands stay dead forever | Medium | Low | Sync test requires either `deprecated=True` or full wiring; no silent dead code |
