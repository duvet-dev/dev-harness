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
from typing import Optional

import click

from harness.command._registration import build_repl_command_map, REGISTRY
from harness.command.setup import get_shared_bus
from harness.command.bus import CommandBus

from harness.command.types import CommandResult, TypedCommand


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





# ── REPL ─────────────────────────────────────────────────────────────────────


class HarnessREPL:
    """Interactive REPL for the Dev Harness CLI.

    Provides tab auto-complete, command history, and wraps all Click CLI
    commands as /command-name [args] entries with help documentation.
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = (root or Path.cwd()).resolve()
        # Ensure REGISTRY is populated by importing CLI modules
        from harness.cli import main as _unused
        self._command_types = build_repl_command_map()
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
        """
        # Import here to avoid circular import at module level
        from harness.cli import main as cli_main

        self.commands: dict[str, click.Command] = {}
        self.groups: dict[str, click.Group] = {}

        for name, cmd in cli_main.commands.items():
            if isinstance(cmd, click.Group):
                self.groups[name] = cmd
                for sub_name in cmd.commands:
                    full = f"{name} {sub_name}"
                    self.commands[full] = cmd.commands[sub_name]
            elif isinstance(cmd, click.Command):
                self.commands[name] = cmd

        self._help_lines = self._build_help_text()

    def _get_short_help(self, name: str) -> str:
        """Fetch the brief description of a Click command by name."""
        cmd = self.commands.get(name)
        if cmd:
            helptext = cmd.help or cmd.short_help or ""
            return helptext.split("\n")[0].strip()
        return ""

    def _build_help_text(self) -> list[str]:
        """Build help text from REGISTRY, excluding click_only commands.

        Returns a list of formatted lines for display with /help.
        """
        lines: list[str] = []
        lines.append("Available commands:")
        lines.append("")

        # Group breakdown for display
        group_children: dict[str, list[str]] = {}
        for name, reg in REGISTRY.items():
            if reg.click_only:
                continue
            parts = name.split(" ", 1)
            if len(parts) == 1:
                group_children.setdefault("_root", []).append(name)
            else:
                group_children.setdefault(parts[0], []).append(name)

        # Top-level (General)
        root_cmds = sorted(group_children.get("_root", []))
        if root_cmds:
            lines.append("── General ──")
            for name in root_cmds:
                brief = self._get_short_help(name)
                lines.append(f"  /{name:<20s} {brief}")
            lines.append("")

        # Grouped sub-commands
        for group_name in sorted(group_children.keys()):
            if group_name == "_root":
                continue
            children = sorted(group_children[group_name])
            if not children:
                continue
            label = GROUP_MAP.get(group_name, group_name.capitalize())
            lines.append(f"── {label} ──")
            for full in children:
                brief = self._get_short_help(full)
                lines.append(f"  /{full:<20s} {brief}")
            lines.append("")

        lines.append("── Special ──")
        lines.append("  /help                Show this help")
        lines.append("  /version             Show version info")
        lines.append("  /findings            Manage Findings Registry (list|show|update-status|confirm-signoff|sync)")
        lines.append("  /assess              Enter assessment phase with assessment-agent")
        lines.append("  /requirements        Enter requirements phase with requirements-agent")
        lines.append("  /design              Enter design phase with design-agent")
        lines.append("  /plan                Enter planning phase with planning-agent")
        lines.append("  /build               Enter build phase with build-agent")
        lines.append("  /get-well            Assessment-driven remediation session")
        lines.append("  /session --get-well  Alternate: /session --get-well [phase]")
        lines.append("  /exit                Exit the REPL")
        lines.append("")
        lines.append("Tab auto-complete: command names, flags, file paths.")
        lines.append("Up/Down arrows: command history.")
        return lines

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

        # ── Findings ────────────────────────────────────────────────────
        if cmd_name == "findings":
            """Manage the Findings Registry for the active engagement."""
            from harness.domain.engagement.resolver import resolve_active_engagement

            slug = resolve_active_engagement(self.root)
            if not slug:
                click.echo("No active engagement.", err=True)
                return True

            sub = cmd_args[0] if cmd_args else "list"

            try:
                from harness.domain.engagement.findings import FindingsStore
                store = FindingsStore(self.root, slug)

                if sub == "list":
                    status_filter = ""
                    sev_filter = ""
                    for a in cmd_args[1:]:
                        if a.startswith("--status="):
                            status_filter = a.split("=", 1)[1]
                        elif a.startswith("--severity="):
                            sev_filter = a.split("=", 1)[1]

                    findings = store.all_findings
                    if status_filter:
                        findings = [f for f in findings if f.status == status_filter]
                    if sev_filter:
                        findings = [f for f in findings if f.severity == sev_filter]

                    if not findings:
                        click.echo("No findings in registry.")
                        return True

                    click.echo(f"\nFindings Registry — {slug} ({len(findings)} total):")
                    click.echo("-" * 72)
                    for f in findings:
                        sev_icon = {
                            "critical": "🔴",
                            "high": "🟠",
                            "medium": "🟡",
                            "low": "🟢",
                            "info": "🔵",
                        }.get(f.severity, "⚪")
                        pending = " ⏳" if f.is_pending_verification else ""
                        click.echo(
                            f"  {sev_icon} {f.id:<6s} {f.status:<13s}{pending} "
                            f"{f.description[:60]}"
                        )
                    click.echo()

                elif sub == "show":
                    fid = cmd_args[1] if len(cmd_args) > 1 else ""
                    if not fid:
                        click.echo("Usage: /findings show F-001", err=True)
                        return True
                    finding = store.get(fid)
                    if not finding:
                        click.echo(f"Finding '{fid}' not found.", err=True)
                        return True
                    click.echo()
                    click.echo(f"  {fid}")
                    click.echo(f"  Status:    {finding.status}")
                    click.echo(f"  Severity:  {finding.severity}")
                    click.echo(f"  Source:    {finding.source}")
                    click.echo(f"  Scope:     {finding.scope}")
                    click.echo(f"  Raised:    {finding.raised_at}")
                    if finding.resolved_at:
                        click.echo(f"  Resolved:  {finding.resolved_at}")
                    if finding.requires_human_signoff:
                        click.echo(f"  Sign-off:  Required{' ⏳' if finding.is_pending_verification else ' ✅'}")
                    if finding.references and finding.references.file:
                        click.echo(f"  File:      {finding.references.file}")
                        if finding.references.line:
                            click.echo(f"  Line:      {finding.references.line}")
                    if finding.resolution and finding.resolution.wave:
                        click.echo(f"  Resolved by: {finding.resolution.wave}")
                    click.echo()
                    click.echo(f"  {finding.description}")
                    click.echo()

                elif sub == "update-status":
                    fid = cmd_args[1] if len(cmd_args) > 1 else ""
                    new_status = cmd_args[2] if len(cmd_args) > 2 else ""
                    if not fid or not new_status:
                        click.echo("Usage: /findings update-status F-001 resolved", err=True)
                        return True
                    from harness.domain.engagement.findings import InvalidTransitionError
                    try:
                        store.update_status(fid, new_status)
                        store.save()
                        click.echo(f"✅ Finding {fid} status updated.")
                    except InvalidTransitionError as e:
                        click.echo(f"❌ {e}", err=True)

                elif sub == "confirm-signoff":
                    fid = cmd_args[1] if len(cmd_args) > 1 else ""
                    if not fid:
                        click.echo("Usage: /findings confirm-signoff F-001", err=True)
                        return True
                    finding = store.confirm_human_signoff(fid)
                    if finding:
                        click.echo(f"✅ Human sign-off confirmed for {fid}.")
                    else:
                        click.echo(f"Finding '{fid}' not found or not pending.", err=True)

                elif sub == "sync":
                    """Run analysis and sync findings into registry."""
                    from harness.analysis.observer import analyse
                    from harness.domain.engagement.findings import (
                        RegistryFinding, FindingReference, _now_iso, _map_severity
                    )
                    deep = "--deep" in cmd_args
                    click.echo("Running analysis...")
                    result = analyse(path=str(self.root), deep=deep)
                    if result["status"] == "error":
                        click.echo(f"Analysis failed: {result.get('message', '')}", err=True)
                        return True

                    # Build findings from scan summary data
                    scanned: list[RegistryFinding] = []
                    for scan_name, scan_data in result.get("scans", {}).items():
                        summary = scan_data.get("summary", "")
                        if summary:
                            rf = RegistryFinding(
                                source=f"scan-{scan_name}",
                                scope="observer",
                                description=summary[:500],
                                severity="info",
                                raised_at=_now_iso(),
                            )
                            scanned.append(rf)

                    # Also sync assessment findings if available
                    assessment = result.get("assessment")
                    if assessment:
                        ad = assessment.get("assessment", {})
                        for item in ad.get("findings", []):
                            sev = _map_severity(item.get("severity", "medium"))
                            file_path = item.get("file", "") or ""
                            rf = RegistryFinding(
                                source=item.get("source", "assessment"),
                                scope="observer",
                                description=item.get("description", ""),
                                severity=sev,
                                references=FindingReference(file=file_path)
                                          if file_path else None,
                                raised_at=_now_iso(),
                            )
                            scanned.append(rf)

                    if not scanned:
                        click.echo("No findings detected.")
                        return True

                    delta = store.compute_delta(scanned)
                    store.save()
                    click.echo("Analysis synced to Findings Registry.")
                    for line in delta.summary_lines():
                        click.echo(f"  {line}")

                else:
                    click.echo("Unknown findings subcommand. Try: list, show, update-status, confirm-signoff, sync", err=True)

            except Exception as exc:
                click.echo(f"Findings error: {exc}", err=True)

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
        # Look up the command in self._command_types. Support both top-level
        # names and group sub-commands ("engagement create").
        candidates = [cmd_name]
        if len(parts) >= 2:
            candidates.insert(0, f"{parts[0]} {parts[1]}")

        dispatched = False
        for candidate in candidates:
            if candidate in self._command_types:
                cmd_cls, arg_parser = self._command_types[candidate]
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

        # ── CLI-only fallback ────────────────────────────────────────────
        if not dispatched:
            for candidate in candidates:
                if candidate in REGISTRY:
                    reg = REGISTRY[candidate]
                    if reg.click_only:
                        click.echo(
                            f"CLI only — use the CLI: harness {candidate}", err=True
                        )
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
