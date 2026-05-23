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
import click.shell_completion

# ── History ──────────────────────────────────────────────────────────────────

HISTORY_FILE = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "harness", "shell_history")
HISTORY_MAXLEN = 1000

# ── Known group prefixes for help display ────────────────────────────────────

GROUP_MAP = {
    "engagement": "Engagement Management",
    "agent":      "Agent Commands",
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
            from harness.engagement.lifecycle import read_active_engagement
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

        # ── Engagement context helpers ───────────────────────────────────
        # If the user types /work /chat /session without being in an
        # engagement, the Click commands will fail gracefully. That's fine.

        # ── Dispatch via Click CLI ───────────────────────────────────────
        try:
            from harness.cli import main as cli_main
            cli_main.main(args=[cmd_name] + cmd_args, standalone_mode=False)
        except SystemExit:
            pass  # Click may call sys.exit even in standalone_mode=False
        except click.Abort:
            pass
        except Exception as exc:
            click.echo(f"Error: {exc}", err=True)

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
