"""CommandRouter — parse user input into typed Command instances — V7 §6.2.

Routes user input based on the routing decision tree:
- ``/``-prefixed commands → strip prefix, map to typed commands
- Free text → return None (NLTranslator or chat agent handles it)

The router maps common ``/command`` strings to their corresponding
typed command classes. It supports:
- Exact matches (``/status`` → ``QueryStatusCommand``)
- Parameterised commands (``/abort hard`` → ``AbortEngagementCommand`` with
  mode in constructor)
- Unknown commands → try as-is or return error

Usage::

    router = CommandRouter()

    # /-prefixed command
    cmd = router.parse("/status")
    # -> QueryStatusCommand(slug="")

    # Free text
    cmd = router.parse("Tell me a joke")
    # -> None

    # Parameterised command
    cmd = router.parse("/abort graceful")
    # -> AbortEngagementCommand(slug="", mode="graceful")
"""

from __future__ import annotations

from harness.command.types import TypedCommand


# ── Lazy-imported typed command classes ─────────────────────────────────

_TYPED_COMMAND_MAP: dict[str, type] = {}


def _get_typed_command_class(command_type: str) -> type | None:
    """Lazy-import and cache the typed command class."""
    if not _TYPED_COMMAND_MAP:
        _TYPED_COMMAND_MAP.update({
            "next": _import_command("harness.command.commands.misc", "NextCommand"),
            "abort_engagement": _import_command("harness.command.commands.engagement", "AbortEngagementCommand"),
            "query_status": _import_command("harness.command.commands.misc", "QueryStatusCommand"),
            "query_whats_next": _import_command("harness.command.commands.misc", "QueryWhatsNextCommand"),
            "enter_phase": _import_command("harness.command.commands.phase", "EnterPhaseCommand"),
            "create_engagement": _import_command("harness.command.commands.engagement", "CreateEngagementCommand"),
            "resume_engagement": _import_command("harness.command.commands.engagement", "ResumeEngagementCommand"),
            "create_wave": _import_command("harness.command.commands.wave", "CreateWaveCommand"),
            "execute_step": _import_command("harness.command.commands.wave", "ExecuteStepCommand"),
        })
    return _TYPED_COMMAND_MAP.get(command_type)


def _import_command(module_path: str, class_name: str) -> type:
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


# ── Routing table: /-command → (command_type string, kwargs builder) ───

def _no_data(cmd_text: str) -> dict:
    """Return empty kwargs dict."""
    return {}


def _mode_data(cmd_text: str) -> dict:
    """Extract mode parameter from /abort <mode> command."""
    parts = cmd_text.split(None, 1)
    mode = parts[1].strip().lower() if len(parts) > 1 else "graceful"
    if mode not in ("hard", "graceful"):
        mode = "graceful"
    return {"mode": mode}


def _phase_data(cmd_text: str) -> dict:
    """Extract phase name from /phase <name> command."""
    parts = cmd_text.split(None, 1)
    phase_name = parts[1].strip() if len(parts) > 1 else ""
    return {"phase": phase_name}


def _wave_data(cmd_text: str) -> dict:
    """Extract wave title from /wave <title> command."""
    parts = cmd_text.split(None, 1)
    title = parts[1].strip() if len(parts) > 1 else "New Wave"
    return {"title": title}


def _step_data(cmd_text: str) -> dict:
    """Extract step data from /step <step_spec> command."""
    parts = cmd_text.split(None, 1)
    step_spec = parts[1].strip() if len(parts) > 1 else "{}"
    return {"step": step_spec}


# Prefixed command map: command name → (type, kwargs_builder)
_PREFIXED_COMMANDS: dict[str, tuple[str, callable]] = {
    # Session commands
    "next": ("next", _no_data),
    "abort": ("abort_engagement", _mode_data),
    "stop": ("abort_engagement", lambda t: {"mode": "hard"}),
    "status": ("query_status", _no_data),
    "health": ("query_status", _no_data),
    "whatsnext": ("query_whats_next", _no_data),
    "phase": ("enter_phase", _phase_data),
    "help": ("", _no_data),  # Special: no command, just help

    # Engagement commands
    "create": ("create_engagement", _no_data),
    "resume": ("resume_engagement", _no_data),

    # Engine/next aliases
    "engine": ("query_whats_next", _no_data),
    "advance": ("next", _no_data),

    # Wave commands
    "wave": ("create_wave", _wave_data),
    "step": ("execute_step", _step_data),
}

# Free-text passthrough: input not starting with / returns None
_FREE_TEXT_RETURN = None


class CommandRouter:
    """Parses user input into typed Command instances for the CommandBus.

    Routing decision tree (V7 §6.2):
    - Starts with ``/`` → strip prefix, map to typed command
    - Free text → return None (NLTranslator / chat agent handles)

    The router is stateless; all state is managed by CommandBus.
    """

    def parse(self, input_text: str, slug: str = "") -> TypedCommand | None:
        """Parse user input text into a typed Command.

        Args:
            input_text: Raw user input (may or may not start with ``/``).
            slug: Optional engagement slug to attach to the command.

        Returns:
            A TypedCommand instance if the input is a ``/``-prefixed command,
            or None for free text input.
        """
        if not input_text or not input_text.strip():
            return None

        stripped = input_text.strip()

        # ── Routing decision tree (V7 §6.2) ──────────────────────────
        # Starts with '/'?
        if not stripped.startswith("/"):
            return _FREE_TEXT_RETURN

        # Strip '/' and parse command
        raw_text = stripped[1:].strip()
        cmd_text = raw_text.lower()

        if not cmd_text:
            # Just "/" by itself — return None (no command)
            return None

        # Split into command name and optional arguments
        parts = cmd_text.split(None, 1)
        raw_parts = raw_text.split(None, 1)
        cmd_name = parts[0]
        raw_args = raw_parts[1] if len(raw_parts) > 1 else ""

        # Look up in routing table
        if cmd_name in _PREFIXED_COMMANDS:
            cmd_type, kwargs_builder = _PREFIXED_COMMANDS[cmd_name]
            if cmd_type == "":
                # Special: /help is a no-op return. We return a basic
                # AbortEngagementCommand as a sentinel — consumers check
                # for empty command_type.
                return None
            # Pass original-case text to data builders
            kwargs = kwargs_builder(raw_text)
            kwargs.setdefault("slug", slug)

            # Build the typed command
            cls = _get_typed_command_class(cmd_type)
            if cls is not None:
                return cls(**kwargs)

        # Unknown command — return None (let consumer handle)
        return None
