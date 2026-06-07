"""Interactive REPL — drop-in command shell for the Dev Harness CLI.

Usage:
    harness shell

All CLI commands are available via /command-name [args] with tab auto-complete
and command history. Type /help to list commands, /exit to quit.
"""

import atexit
import os
import readline
import shlex
from pathlib import Path
from typing import Any, Callable, Optional

import click
import click.shell_completion

from harness.command.setup import get_shared_bus
from harness.command.bus import CommandBus

from harness.command.types import CommandResult, TypedCommand
from harness.command.commands.analysis import AssessCommand, InspectCommand, SummaryCommand
from harness.command.commands.batch import (
    AnnotateChangelogCommand,
    CreateWaveFromFindingCommand,
    CreateWavesFromAssessmentCommand,
    GenerateDocsCommand,
    ListWavesCommand,
    WaveStatusCommand,
)
from harness.command.commands.engagement import (
    AbortEngagementCommand,
    CreateEngagementCommand,
)
from harness.command.commands.mgmt import (
    AgentListCommand,
    ConsultCommand,
    FixEngagementCommand,
    RefreshAgentsCommand,
    RenameEngagementCommand,
    SetBranchCommand,
    SetGovernanceCommand,
    TeamListCommand,
)
from harness.command.commands.phase import EnterPhaseCommand, ManagePhaseCommand
from harness.command.commands.project import InitProjectCommand
from harness.command.commands.review import FinishEngagementCommand, ReviewEngagementCommand
from harness.command.commands.misc import QueryStatusCommand, QueryWhatsNextCommand
from harness.command.commands.session import ChatCommand, SessionCommand
from harness.command.commands.wave import RunWaveCommand


# ── History ──────────────────────────────────────────────────────────────────

HISTORY_FILE = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "harness", "shell_history")
HISTORY_MAXLEN = 1000

# ── Known group prefixes for help display ────────────────────────────────────

GROUP_MAP = {
    "engagement": "Engagement Management",
    "agent":      "Agent Commands",
}


# ── CommandBus dispatch helpers ────────────────────────────────────────────


def _build_command_bus() -> CommandBus:
    """Create a fresh CommandBus with all handlers registered."""
    return get_shared_bus()


def _dispatch_via_bus(command: TypedCommand) -> CommandResult:
    """Dispatch a command through the shared CommandBus and return the result."""
    return get_shared_bus().dispatch(command)


# ── Command name → factory map ────────────────────────────────────────────
# Maps REPL command names to (factory_function, arg_parser) tuples.
# arg_parser(args: list[str]) -> dict of kwargs for the factory.


def _no_args(_args: list[str]) -> dict[str, Any]:
    return {}


def _single_arg(args: list[str]) -> dict[str, str]:
    return {"slug": args[0]} if args else {}


def _engagement_create_args(args: list[str]) -> dict[str, Any]:
    """Parse args for /engagement create <name> [--slug ...] [...]."""
    return {"slug": args[0], "workflow_name": "standard", "session_type": "greenfield", "mode": "auto"} if args else {}


def _session_args(args: list[str]) -> dict[str, Any]:
    """Parse args for /session [--get-well] [phase]."""
    cleaned = [a for a in args if a != "--get-well"]
    phase = cleaned[0] if cleaned else "requirements"
    get_well = "--get-well" in args
    if get_well and phase == "requirements":
        phase = "assessment-triage"
    return {"slug": "", "phase": phase, "get_well": get_well}


def _chat_args(args: list[str]) -> dict[str, Any]:
    return {"slug": "", "prompt": args[0] if args else None}


def _phase_args(args: list[str]) -> dict[str, Any]:
    """Parse /phase [engagement_id] [--list|--navigate|...]."""
    # Extract engagement_id (first positional) and action from flags
    engagement_id = ""
    remaining = list(args)
    if remaining and not remaining[0].startswith("--"):
        engagement_id = remaining.pop(0)
    return {"slug": engagement_id, "action": "list", "root": str(Path.cwd())}


def _work_args(args: list[str]) -> dict[str, Any]:
    """Parse /work <description> [--mode ...]."""
    import re
    description = " ".join(a for a in args if not a.startswith("--"))
    slug = re.sub(r"[^a-z0-9-]", "-", description.lower().strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return {"slug": slug, "workflow_name": "standard", "session_type": "greenfield", "mode": "auto"}


def _init_args(args: list[str]) -> dict[str, Any]:
    """Parse /init [project_dir] [--template ...] [--no-git] [--force]."""
    remaining = [a for a in args if not a.startswith("--")]
    project_dir = remaining[0] if remaining else None
    return {"project_dir": project_dir, "root": Path.cwd()}


def _run_wave_args(args: list[str]) -> dict[str, Any]:
    """Parse /wave run <wave_id> [--no-test] [--backend ...] [--engagement ...]."""
    wave_id = ""
    no_test = False
    backend = None
    i = 0
    while i < len(args):
        if args[i] == "--no-test":
            no_test = True
        elif args[i] == "--backend" and i + 1 < len(args):
            backend = args[i + 1]
            i += 1
        elif args[i] == "--engagement" and i + 1 < len(args):
            pass  # slug handled by caller
            i += 1
        elif not args[i].startswith("--"):
            wave_id = args[i]
        i += 1
    return {"slug": "", "wave_id": wave_id, "no_test": no_test, "backend": backend}


def _finish_args(args: list[str]) -> dict[str, Any]:
    return {"slug": "", "root": str(Path.cwd()), "re_assess": "--re-assess" in args}


def _review_args(args: list[str]) -> dict[str, Any]:
    slug = ""
    decision = "approved"
    i = 0
    while i < len(args):
        if args[i] == "--approve":
            decision = "approved"
        elif args[i] == "--reject":
            decision = "rejected"
        elif args[i] == "--request-changes":
            decision = "request_changes"
        elif not args[i].startswith("--"):
            slug = args[i]
        i += 1
    return {"slug": slug, "decision": decision, "root": str(Path.cwd())}


def _summary_args(args: list[str]) -> dict[str, Any]:
    return {
        "deep": "--deep" in args,
        "assess_flag": "--assess" in args,
        "json_flag": "--json" in args,
        "reconcile": "--reconcile" in args,
        "engagement": None,
    }


def _inspect_args(args: list[str]) -> dict[str, Any]:
    return {"root": args[0] if args else "."}


def _assess_args(args: list[str]) -> dict[str, Any]:
    return {"root": args[0] if args else ".", "deep_flag": True}


def _create_wave_from_assessment_args(args: list[str]) -> dict[str, Any]:
    focus = "high-risk"
    limit = 0
    i = 0
    while i < len(args):
        if args[i] == "--focus" and i + 1 < len(args):
            focus = args[i + 1]
            i += 1
        elif args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 1
        elif args[i] == "--refactoring":
            pass
        i += 1
    return {"focus": focus, "limit": limit, "slug": "", "refactoring": "--refactoring" in args}


def _create_wave_from_finding_args(args: list[str]) -> dict[str, Any]:
    finding_id = args[0] if args else ""
    return {"finding_id": finding_id, "slug": ""}


# Command name -> (command_class, arg_parser)
# All commands are constructed directly from parsed kwargs and dispatched
# via the shared CommandBus. No factory functions, no Click fallback.
COMMAND_TYPES: dict[str, tuple[type, Callable[[list[str]], dict[str, Any]]]] = {
    # Engagement lifecycle
    "engagement create":             (CreateEngagementCommand, _engagement_create_args),
    "engagement close":              (AbortEngagementCommand, _single_arg),
    "engagement rename":             (RenameEngagementCommand, lambda a: {"slug": a[0], "new_slug": a[1]} if len(a) >= 2 else {}),
    "engagement set-branch":         (SetBranchCommand, lambda a: {"slug": a[0], "branch": a[1]} if len(a) >= 2 else {"slug": a[0] if a else ""}),
    "engagement fix":                (FixEngagementCommand, lambda a: {"slug": a[0] if a else ""}),
    # Phase management
    "enter-phase":                    (EnterPhaseCommand, lambda a: {"slug": a[0], "phase": a[1]} if len(a) >= 2 else {}),
    "phase":                         (ManagePhaseCommand, _phase_args),
    # Session / chat
    "session":                       (SessionCommand, _session_args),
    "chat":                          (ChatCommand, _chat_args),
    "work":                          (CreateEngagementCommand, _work_args),
    "init":                          (InitProjectCommand, lambda a: {k: v for k, v in _init_args(a).items() if k != "root"}),
    "finish":                        (FinishEngagementCommand, _finish_args),
    "review":                        (ReviewEngagementCommand, _review_args),
    "summary":                       (SummaryCommand, lambda a: {"slug": a[0] if a else "", "deep": "--deep" in a, "assess_flag": "--assess" in a, "json_flag": "--json" in a, "reconcile": "--reconcile" in a}),
    "inspect":                       (InspectCommand, lambda a: {"slug": "", "root": a[0] if a else "."}),
    "assess":                        (AssessCommand, lambda a: {"slug": "", "root": a[0] if a else ".", "deep_flag": True}),
    "status":                        (QueryStatusCommand, _single_arg),
    "whatsnext":                     (QueryWhatsNextCommand, _single_arg),
    "generate-docs":                 (GenerateDocsCommand, lambda a: {"slug": "", "root": a[0] if a else "."}),
    # Wave management
    "wave list":                     (ListWavesCommand, lambda a: {"slug": a[0] if a else ""}),
    "wave run":                      (RunWaveCommand, _run_wave_args),
    "wave status":                   (WaveStatusCommand, lambda a: {"slug": a[0] if a else ""}),
    "wave create-from-assessment":   (CreateWavesFromAssessmentCommand, _create_wave_from_assessment_args),
    "wave create-from-finding":      (CreateWaveFromFindingCommand, _create_wave_from_finding_args),
    # Changelog
    "changelog annotate":            (AnnotateChangelogCommand, lambda a: {"slug": a[0], "wave": "", "text": " ".join(a[1:])} if a else {}),
    # Governance
    "team set-governance":           (SetGovernanceCommand, lambda a: {"slug": "", "level": a[0]} if a else {"slug": "", "level": "standard"}),
    # Agent / Team listing
    "agent list":                    (AgentListCommand, lambda a: {"slug": ""}),
    "team list":                     (TeamListCommand, lambda a: {"slug": ""}),
    "consult":                        (ConsultCommand, lambda a: {"slug": "", "question": " ".join(a)} if a else {"slug": "", "question": ""}),
    # Refresh agents
    "refresh-agents":                (RefreshAgentsCommand, lambda a: {"slug": "", "project_dir": None, "force": "--force" in a}),
}


# ── REPL ─────────────────────────────────────────────────────────────────────


class HarnessREPL:
    """Interactive REPL for the Dev Harness CLI.

    Provides tab auto-complete, command history, and wraps all Click CLI
    commands as /command-name [args] entries with help documentation.
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = (root or Path.cwd()).resolve()
        self._build_command_index()
        self._setup_readline()

    # ------------------------------------------------------------------
    # Command discovery
    # ------------------------------------------------------------------

    def _build_command_index(self) -> None:
        """Walk the Click CLI tree and build a flat command index.

        Populates:
            self.commands    -- flat dict: "name" -> click.Command
            self.groups      -- dict: group name -> click.Group
            self.help_tree   -- structured tree for help display
        """
        # Import here to avoid circular import at module level
        from harness.cli import main as cli_main

        self.commands: dict[str, click.Command] = {}
        self.groups: dict[str, click.Group] = {}
        # Track group->subcommands for help display
        self.group_children: dict[str, list[str]] = {}

        for name, cmd in cli_main.commands.items():
            if isinstance(cmd, click.Group):
                self.groups[name] = cmd
                self.group_children.setdefault("_root", []).append(name)
                for sub_name, sub_cmd in cmd.commands.items():
                    full = f"{name} {sub_name}"
                    self.commands[full] = sub_cmd
                    self.group_children.setdefault(name, []).append(full)
            elif isinstance(cmd, click.Command):
                self.commands[name] = cmd
                self.group_children.setdefault("_root", []).append(name)

        # Build help tree: sorted group -> sorted commands
        self._help_lines: list[str] = []
        self._help_lines.append("Available commands:")
        self._help_lines.append("")

        # Top-level items: commands only (groups handled separately below)
        root_cmds = sorted(
            n for n in self.group_children.get("_root", [])
            if n in self.commands
        )
        if root_cmds:
            self._help_lines.append("── General ──")
            for name in root_cmds:
                cmd = self.commands.get(name)
                if cmd and hasattr(cmd, 'help'):
                    brief = (cmd.help or cmd.short_help or "").split("\n")[0].strip()
                else:
                    brief = ""
                self._help_lines.append(f"  /{name:<20s} {brief}")
            self._help_lines.append("")

        # Grouped sub-commands
        for group_name in sorted(self.groups.keys()):
            children = sorted(self.group_children.get(group_name, []))
            if not children:
                continue
            label = GROUP_MAP.get(group_name, group_name.capitalize())
            self._help_lines.append(f"── {label} ──")
            for full in children:
                cmd = self.commands.get(full)
                if cmd and hasattr(cmd, 'help'):
                    brief = (cmd.help or cmd.short_help or "").split("\n")[0].strip()
                else:
                    brief = ""
                self._help_lines.append(f"  /{full:<20s} {brief}")
            self._help_lines.append("")

        self._help_lines.append("── Special ──")
        self._help_lines.append("  /help                Show this help")
        self._help_lines.append("  /version             Show version info")
        self._help_lines.append("  /assess              Enter assessment phase with assessment-agent")
        self._help_lines.append("  /requirements        Enter requirements phase with requirements-agent")
        self._help_lines.append("  /design              Enter design phase with design-agent")
        self._help_lines.append("  /plan                Enter planning phase with planning-agent")
        self._help_lines.append("  /build               Enter build phase with build-agent")
        self._help_lines.append("  /get-well            Assessment-driven remediation session")
        self._help_lines.append("  /session --get-well  Alternate: /session --get-well [phase]")
        self._help_lines.append("  /exit                Exit the REPL")
        self._help_lines.append("")
        self._help_lines.append("Tab auto-complete: command names, flags, file paths.")
        self._help_lines.append("Up/Down arrows: command history.")

    # ------------------------------------------------------------------
    # Readline setup
    # ------------------------------------------------------------------

    def _setup_readline(self) -> None:
        """Configure readline with history, tab completion, and line editing."""
        # History
        try:
            hist_dir = os.path.dirname(HISTORY_FILE)
            if hist_dir:
                os.makedirs(hist_dir, exist_ok=True)
            readline.read_history_file(HISTORY_FILE)
        except (FileNotFoundError, PermissionError, OSError):
            pass
        try:
            readline.set_history_length(HISTORY_MAXLEN)
        except Exception:
            pass
        atexit.register(self._flush_history)

        # Line editing keys
        try:
            readline.parse_and_bind('"\\eb": backward-word')
            readline.parse_and_bind('"\\ef": forward-word')
            readline.parse_and_bind('"\\e[H": beginning-of-line')
            readline.parse_and_bind('"\\e[F": end-of-line')
            readline.parse_and_bind('"\\e[7~": beginning-of-line')  # xterm home
            readline.parse_and_bind('"\\e[8~": end-of-line')        # xterm end
        except Exception:
            pass  # Non-UNIX platforms

        # Tab completion
        self._completer = _REPLCompleter(self)
        try:
            readline.set_completer(self._completer.complete)
            readline.set_completer_delims(' \t\n')
            readline.parse_and_bind('tab: complete')
        except Exception:
            pass

    @staticmethod
    def _flush_history() -> None:
        """Safely flush readline history to disk."""
        try:
            readline.write_history_file(HISTORY_FILE)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------

    def _prompt(self) -> str:
        """Build the prompt string with optional engagement context."""
        engagement = self._get_active_engagement()
        if engagement:
            return f"harness [\x1b[36m{engagement}\x1b[0m]> "
        return "harness> "

    def _get_active_engagement(self) -> Optional[str]:
        """Return the active engagement slug, if any."""
        try:
            from harness.domain.engagement.lifecycle import read_active_engagement
            return read_active_engagement(self.root)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    def _run_command(self, line: str) -> bool:
        """Parse and execute one line of input.

        Returns True to continue, False to exit.
        """
        raw = line.strip()

        # Strip leading /
        if not raw.startswith("/"):
            click.echo(
                "Commands start with /. Type /help for available commands.",
                err=True,
            )
            return True

        cmd_text = raw[1:].strip()
        if not cmd_text:
            return True

        parts = shlex.split(cmd_text)
        cmd_name = parts[0]
        cmd_args = parts[1:]

        # ── Built-in commands ────────────────────────────────────────────
        if cmd_name in ("exit", "quit", "q"):
            return False

        if cmd_name == "help":
            for line_ in self._help_lines:
                click.echo(line_)
            return True

        if cmd_name == "shell":
            click.echo("Already in the REPL.")
            return True

        if cmd_name == "exec":
            shell_cmd = " ".join(cmd_args) if cmd_args else ""
            if not shell_cmd:
                click.echo("Usage: /exec <shell command>")
                return True
            import subprocess
            try:
                result = subprocess.run(
                    shell_cmd, shell=True, capture_output=True, text=True, timeout=60,
                )
                if result.stdout:
                    click.echo(result.stdout.rstrip())
                if result.stderr:
                    if result.stdout:
                        click.echo()
                    click.echo(result.stderr.rstrip(), err=True)
                if result.returncode != 0:
                    click.echo()
                    click.echo(f"\u2716 exit code {result.returncode}")
                elif not result.stdout and not result.stderr:
                    click.echo(f"(exit code {result.returncode}, no output)")
            except subprocess.TimeoutExpired:
                click.echo(f"Command timed out after 60s: {shell_cmd}", err=True)
            except Exception as exc:
                click.echo(f"Error: {exc}", err=True)
            return True

        if cmd_name == "version":
            from harness._version import __version__, __build__, __build_date__, __commit__
            date_str = __build_date__ if __build_date__ else "development"
            commit_str = __commit__ if __commit__ else "unknown"
            click.echo(f"dev-harness v{__version__}.{__build__:03d}")
            click.echo(f"build:   {__build__:03d}")
            click.echo(f"commit:  {commit_str}")
            click.echo(f"date:    {date_str}")
            return True

        # ── Get-well ────────────────────────────────────────────────────
        if cmd_name == "get-well":
            """Run a get-well remediation session via CommandBus."""
            import asyncio
            from harness.session.session_orchestrator import run_phase_session
            from harness.domain.engagement.resolver import resolve_active_engagement

            slug = resolve_active_engagement(self.root)
            if not slug:
                click.echo("No active engagement. Create one with:")
                click.echo("  engagement create \"your task\"", err=True)
                return True

            phase = cmd_args[0] if cmd_args else "assessment-triage"

            # Dispatch session command through CommandBus first
            from harness.command.commands.session import SessionCommand
            bus = _build_command_bus()
            cmd = SessionCommand(slug=slug, phase=phase, get_well=True)
            result = bus.dispatch(cmd)
            if not result.success:
                click.echo(f"Session setup failed: {result.error}", err=True)
                return True

            click.echo(f"Starting get-well session on: {slug}")
            click.echo(f"Starting from phase: {phase}")
            click.echo()

            try:
                asyncio.run(run_phase_session(
                    self.root, slug,
                    start_phase=phase,
                    session_type="get-well",
                ))
            except click.Abort:
                pass
            except Exception as exc:
                click.echo(f"Get-well session error: {exc}", err=True)

            return True

        # ── Phase entry ──────────────────────────────────────────────────
        if cmd_name in ("assess", "requirements", "design", "plan", "build"):
            """Enter a phase-specific session with the dedicated phase agent."""
            import asyncio
            from harness.session.phase_sessions import PHASE_ENTRY_HANDLERS
            from harness.domain.engagement.resolver import resolve_active_engagement

            slug = resolve_active_engagement(self.root)
            if not slug:
                click.echo("No active engagement. Create one with:")
                click.echo("  /work \"your task\"")
                return True

            handler = PHASE_ENTRY_HANDLERS.get(cmd_name)
            if not handler:
                click.echo(f"Unknown phase: {cmd_name}", err=True)
                return True

            try:
                handler(self.root)
            except Exception as exc:
                click.echo(f"Phase session error: {exc}", err=True)

            return True

        # ── Session ──────────────────────────────────────────────────────
        if cmd_name == "session":
            """Run a full multi-phase session via CommandBus."""
            import asyncio
            from harness.session.session_orchestrator import run_phase_session
            from harness.domain.engagement.resolver import resolve_active_engagement

            slug = resolve_active_engagement(self.root)
            if not slug:
                click.echo("No active engagement. Create one with:")
                click.echo("  engagement create \"your task\"", err=True)
                return True

            is_get_well = "--get-well" in cmd_args
            cleaned = [a for a in cmd_args if a != "--get-well"]
            phase = cleaned[0] if cleaned else ("assessment-triage" if is_get_well else "requirements")

            # Dispatch session command through CommandBus
            from harness.command.commands.session import SessionCommand
            bus = _build_command_bus()
            cmd = SessionCommand(slug=slug, phase=phase, get_well=is_get_well)
            result = bus.dispatch(cmd)
            if not result.success:
                click.echo(f"Session setup failed: {result.error}", err=True)
                return True

            session_type = "get-well" if is_get_well else None
            click.echo(f"Starting session on: {slug}")
            click.echo(f"Starting from phase: {phase}")
            click.echo()

            try:
                asyncio.run(run_phase_session(
                    self.root, slug,
                    start_phase=phase,
                    session_type=session_type,
                ))
            except click.Abort:
                pass
            except Exception as exc:
                click.echo(f"Session error: {exc}", err=True)

            return True

        # ── CommandBus dispatch ──────────────────────────────────────────
        # Look up the command in COMMAND_TYPES. Support both top-level names
        # and group sub-commands ("engagement create").
        candidates = [cmd_name]
        if len(parts) >= 2:
            candidates.insert(0, f"{parts[0]} {parts[1]}")

        dispatched = False
        for candidate in candidates:
            if candidate in COMMAND_TYPES:
                cmd_cls, arg_parser = COMMAND_TYPES[candidate]
                try:
                    kwargs = arg_parser(list(cmd_args))
                    command = cmd_cls(**kwargs)
                    result = _dispatch_via_bus(command)
                    if result.success:
                        if result.message:
                            click.echo(result.message)
                    else:
                        click.echo(f"Error: {result.error or result.message}", err=True)
                    dispatched = True
                    break
                except Exception as exc:
                    click.echo(f"Error executing /{candidate}: {exc}", err=True)
                    dispatched = True
                    break

        if not dispatched:
            click.echo(f"Unknown command: /{cmd_name}. Type /help for available commands.", err=True)

        return True

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Enter the main REPL loop."""
        click.echo(
            "Dev Harness REPL — type \x1b[1m/help\x1b[0m for "
            "commands, \x1b[1m/exit\x1b[0m to quit"
        )
        click.echo("")

        # Run health checks (non-blocking, warnings only)
        if self.root:
            try:
                from harness.health import run_health_checks
                report = run_health_checks(self.root)
                if report.status != "pass":
                    warnings = [
                        c for c in report.checks
                        if c.status != "pass"
                        and c.severity in ("CRITICAL", "BRANCH", "WARN")
                    ]
                    if warnings:
                        for c in warnings[:5]:
                            icon = "✗" if c.status == "fail" else "⚠"
                            click.echo(f"  {icon} {c.message}")
                            if c.fix:
                                click.echo(f"     → Fix: {c.fix}")
                        click.echo(
                            "  ──────────────────────────────"
                        )
                        click.echo(
                            "  Run 'harness health' for full details."
                        )
                        click.echo("")
            except Exception:
                pass  # Non-critical — don't block shell start

        while True:
            try:
                line = input(self._prompt())
            except (EOFError, KeyboardInterrupt):
                click.echo()
                break

            if not self._run_command(line):
                break

        click.echo("Goodbye.")


# ── Tab completer ────────────────────────────────────────────────────────────


class _REPLCompleter:
    """Readline completer for the Dev Harness REPL."""

    def __init__(self, repl: HarnessREPL):
        self.repl = repl
        # Build flat command-name list for first-word completion
        self._command_names = sorted(repl.commands.keys())
        self._group_names = sorted(repl.groups.keys())
        # All possible first tokens
        self._first_tokens = set()
        for name in self._command_names:
            self._first_tokens.add(name.split()[0])
        for name in self._group_names:
            self._first_tokens.add(name)
        # REPL-only commands (not in Click CLI)
        self._first_tokens.update({"assess", "requirements", "design", "plan", "build", "get-well", "session"})
        self._matches: list[str] = []

    def complete(self, text: str, state: int) -> Optional[str]:
        """Readline completer callback."""

        if state == 0:
            # Get current line buffer and cursor position
            line = readline.get_line_buffer()
            cursor = readline.get_endidx()

            # Determine what we're completing (word before cursor)
            buf_before = line[:cursor]
            parts = buf_before.lstrip().split()

            if not parts:
                # No text yet — suggest all commands
                self._matches = sorted(
                    f"/{n}" for n in self._first_tokens
                )
            elif len(parts) == 1:
                # First word: command name
                prefix = parts[0]
                if prefix.startswith("/"):
                    prefix = prefix[1:]
                self._matches = sorted(
                    f"/{n}" for n in self._first_tokens
                    if n.startswith(prefix)
                )
                if not self._matches:
                    # Maybe the user typed the beginning of a flag or value
                    self._matches = []
            else:
                # Subsequent words: complete flags or file paths
                cmd_name = parts[0].lstrip("/")
                last_part = parts[-1]

                # Find the click.Command for context
                cmd = self.repl.commands.get(cmd_name)
                if cmd and isinstance(cmd, click.Command):
                    self._matches = self._complete_for_command(
                        cmd, parts[1:], last_part
                    )
                else:
                    # Fallback: file path completion
                    self._matches = self._complete_path(last_part)
        try:
            return self._matches[state]
        except IndexError:
            return None

    def _complete_for_command(
        self,
        cmd: click.Command,
        args_so_far: list[str],
        last_part: str,
    ) -> list[str]:
        """Suggest completions for a known Click command."""
        matches: list[str] = []

        # Suggest flags (--option=)
        if last_part.startswith("-") or last_part == "":
            for param in cmd.params:
                if isinstance(param, click.Option):
                    for opt in param.opts:
                        if opt.startswith(last_part):
                            matches.append(opt)
                elif isinstance(param, click.Argument):
                    # Arguments don't have flags, skip
                    pass
        else:
            # Could be a file path
            matches = self._complete_path(last_part)

        return matches

    def _complete_path(self, prefix: str) -> list[str]:
        """Simple file-path completion."""
        if not prefix:
            prefix = "."
        p = Path(prefix)
        parent = p.parent if p.parent else Path(".")
        try:
            children = list(parent.iterdir())
        except (PermissionError, FileNotFoundError):
            return []

        matches = []
        prefix_name = p.name
        for child in children:
            name = child.name
            if name.startswith(prefix_name):
                if child.is_dir():
                    matches.append(str(child) + "/")
                else:
                    matches.append(str(child))
        return matches


# ── CLI entry point ──────────────────────────────────────────────────────────


def shell(root: Optional[Path] = None) -> None:
    """Entry point for ``harness shell``.

    Pass an explicit *root* path, or default to the current working directory.
    """
    repl = HarnessREPL(root=root)
    repl.run()
