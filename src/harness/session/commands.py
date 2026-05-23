"""Session command routing — pure command dispatch with structured results.

Extracts the inline command handlers from session/chat loops into
testable functions. Each handler takes typed state and returns a
``CommandResult`` describing what the outer loop should do (display,
advance, switch phase, etc.) — separating logic from terminal IO.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from harness.agents.consultation import ConsultationResult


@dataclass
class CommandResult:
    """Structured result from executing a session command.

    The outer loop reads this and performs the actual IO (click.echo,
    file writes, transcript saves, etc.). All display text is in
    ``display_lines``.
    """

    display_lines: list[str] = field(default_factory=list)
    """Lines to display to the user via click.echo()."""

    exit_loop: bool = False
    """True if the session loop should exit."""

    advance_phase: bool = False
    """True if the loop should advance to the next phase."""

    approved: bool = False
    """True if /approve was issued (vs /next without approval)."""

    switch_to_phase: Optional[str] = None
    """Phase name to navigate to (e.g. from /navigate or /phase)."""

    phase_jump_allowed: bool = False
    """Phase jump passed limit check (caller should execute the jump)."""

    save_transcript: bool = False
    """Outer loop should save the transcript."""

    capture_artifact: Optional[str] = None
    """Content to capture as phase artifact (from last response)."""

    auto_apply: Optional[str] = None
    """Content to apply as file blocks (from last response)."""

    new_provider: Optional[dict[str, Any]] = None
    """Provider dict to switch to (from /model command)."""

    switch_to_phase_with_history: Optional[str] = None
    """Phase to switch to while preserving conversation history."""

    reset_conversation: bool = False
    """True if /new was issued — reset messages to just system prompt."""

    consult_result: Optional[ConsultationResult] = None
    """Result from a /consult dispatch."""

    consult_resolved: bool = False
    """True if a blocking consult was resolved."""

    set_in_session: bool = False
    """True if _print_help should be told it's in session mode."""


# ═══════════════════════════════════════════════════════════════════════════════
# Command dispatch — pure function that routes command string → result
# ═══════════════════════════════════════════════════════════════════════════════


def route_chat_command(cmd: str, state: dict[str, Any]) -> CommandResult:
    """Route a chat-loop meta-command and return the result.

    Args:
        cmd: The command string with leading ``/`` removed and lowercased
            (e.g. ``"help"``, ``"phase design"``, ``"model deepseek"``).
        state: Dict containing:
            - ``root`` — project root Path
            - ``provider`` — current provider dict
            - ``model`` — current model string
            - ``engagement_slug`` — current engagement slug
            - ``last_response`` — client's last response (str or None)
            - ``client_messages`` — list of message dicts
            - ``system_prompt`` — current system prompt string
            - All PHASES constant, PHASES, DOMAIN_LANGUAGE_PREAMBLE

    Returns:
        A ``CommandResult`` describing what the outer loop should do.
    """
    if cmd in ("exit", "quit"):
        return CommandResult(exit_loop=True)

    if cmd == "help":
        return CommandResult(set_in_session=False)

    if cmd == "save":
        return CommandResult(save_transcript=True)

    if cmd == "write":
        content = state.get("last_response")
        if content:
            return CommandResult(capture_artifact=content)
        return CommandResult(display_lines=["No assistant response to save."])

    if cmd == "apply":
        content = state.get("last_response")
        if content:
            return CommandResult(auto_apply=content)
        return CommandResult(display_lines=["No assistant response to apply."])

    if cmd.startswith("phase "):
        return _handle_phase_switch(cmd[6:].strip(), state)

    if cmd == "models":
        return CommandResult(display_lines=["__list_providers__"])

    if cmd.startswith("model "):
        return _handle_model_switch(cmd[6:].strip(), state)

    if cmd == "new":
        return CommandResult(reset_conversation=True)

    if cmd.startswith("consult "):
        return _handle_consult(cmd[8:].strip())

    return CommandResult(display_lines=[
        f"Unknown command: /{cmd}. Type /help for options."
    ])


def route_session_command(cmd: str, state: dict[str, Any]) -> CommandResult:
    """Route a session-loop meta-command and return the result.

    Same pattern as ``route_chat_command`` but with session-specific
    commands (next, approve, changes, navigate, feedback, resume, etc.).

    Args:
        cmd: Command string (lowercased, no leading ``/``).
        state: Session state dict with keys:
            ``phase_def``, ``blocking_consults``, ``last_response``,
            ``transcript``, ``root``, ``provider``, ``model``,
            ``engagement_slug``, ``jump_counts``, ``client``,
            ``phase_artifacts``, ``phase_name``, ``current_phase_index``,
            ``PHASES``, ``_phase_list``

    Returns:
        ``CommandResult``.
    """
    if cmd == "help":
        return CommandResult(set_in_session=True)

    if cmd in ("next", "approve"):
        return _handle_next_approve(cmd, state)

    if cmd == "save":
        return CommandResult(save_transcript=True)

    if cmd == "models":
        return CommandResult(display_lines=["__list_providers__"])

    if cmd.startswith("model "):
        return _handle_model_switch(cmd[6:].strip(), state)

    if cmd == "write":
        content = state.get("last_response")
        if content:
            return CommandResult(capture_artifact=content)
        return CommandResult(display_lines=["No assistant response to save."])

    if cmd == "apply":
        content = state.get("last_response")
        if content:
            return CommandResult(auto_apply=content)
        return CommandResult(display_lines=["No assistant response to apply."])

    if cmd == "changes" or cmd.startswith("changes "):
        return _handle_changes(cmd, state)

    if cmd.startswith("navigate "):
        return _handle_navigate(cmd[9:].strip(), state)

    if cmd == "feedback" or cmd.startswith("feedback "):
        return _handle_feedback(cmd[9:].strip(), state)

    if cmd in ("resume", "resume-force"):
        return CommandResult(display_lines=["__resume_checkpoint__"])

    if cmd == "phase" or cmd.startswith("phase "):
        return _handle_phase_switch(
            cmd[6:].strip() if cmd.startswith("phase ") else "", state
        )

    if cmd.startswith("consult "):
        return _handle_consult(cmd[8:].strip())

    if cmd == "consult-resolve" or cmd.startswith("consult-resolve "):
        return _handle_consult_resolve(cmd[16:].strip(), state)

    return CommandResult(display_lines=[
        f"Unknown command: /{cmd}. Type /help for options."
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# Individual command handlers
# ═══════════════════════════════════════════════════════════════════════════════


def _handle_phase_switch(target: str, state: dict[str, Any]) -> CommandResult:
    """Handle /phase <name> — switch phase with history preserved."""
    from harness.session.loop import PHASES

    if not target:
        return CommandResult(display_lines=["__show_phase_diagram__"])

    match = next((p for p in PHASES if p["name"] == target), None)
    if match is None:
        names = ", ".join(p["name"] for p in PHASES)
        return CommandResult(display_lines=[
            f"Unknown phase: {target}. Available: {names}"
        ])

    return CommandResult(
        switch_to_phase_with_history=target,
        display_lines=[f"Switched to phase: {match['title']} "
                       "(conversation history preserved)"],
    )


def _handle_model_switch(arg: str, state: dict[str, Any]) -> CommandResult:
    """Handle /model <name> [alias] — switch provider."""
    parts = arg.split(None, 1)
    target_name = parts[0]
    target_alias = parts[1] if len(parts) > 1 else None

    # Pure logic: the outer loop will call switch_provider() which does IO
    return CommandResult(
        display_lines=["__switch_provider__"],
        new_provider={
            "target_name": target_name,
            "target_alias": target_alias,
        },
    )


def _handle_consult(query: str) -> CommandResult:
    """Handle /consult <question> — route to fleet."""
    if not query:
        return CommandResult(display_lines=[
            "Usage: /consult [--fleet <name>] [--mode advisory|blocking]"
            " <question>"
        ])

    from harness.session.loop import _parse_consult_flags
    parsed = _parse_consult_flags(query)
    if not parsed["question"]:
        return CommandResult(display_lines=[
            "Usage: /consult [--fleet <name>] [--mode advisory|blocking]"
            " <question>"
        ])

    # The actual consult dispatch requires FleetRegistry (IO), so
    # the outer loop performs it and passes the result back.
    return CommandResult(
        display_lines=["__do_consult__"],
    )


def _handle_next_approve(cmd: str, state: dict[str, Any]) -> CommandResult:
    """Handle /next or /approve command — pure logic only.

    Checks blocking consults, captures artifacts, determines if
    the phase should advance. The outer loop performs any IO
    (file writes, transcript saves).
    """
    lines: list[str] = []

    # Check for unresolved blocking consults
    pname = state.get("phase_def", {}).get("name", "")
    blocking_consults = state.get("blocking_consults", {})
    if pname in blocking_consults:
        unresolved = [
            c for c in blocking_consults[pname]
            if callable(getattr(c, "is_blocking", None)) and c.is_blocking()
        ]
        if unresolved:
            return CommandResult(display_lines=[
                f"Cannot advance: {len(unresolved)} unresolved "
                "blocking consult(s).",
                "Use /consult-resolve <index> <resolution> to resolve.",
            ])

    # Capture last response as artifact
    last_resp = state.get("last_response")
    if last_resp:
        lines.append(f"  + Phase '{state.get('phase_def', {}).get('title', '')}' completed.")
        if cmd == "approve":
            lines.append("  Approved.")

    return CommandResult(
        display_lines=lines,
        advance_phase=True,
        approved=(cmd == "approve"),
        save_transcript=True,
        capture_artifact=last_resp,
        auto_apply=last_resp,
    )


def _handle_changes(cmd: str, state: dict[str, Any]) -> CommandResult:
    """Handle /changes [reason] — request revisions from agent."""
    feedback_text = cmd[8:].strip() if len(cmd) > 8 else ""
    from harness.session.loop import PHASES
    current_name = state.get("phase_def", {}).get("name", "")
    current_idx = next(
        (i for i, p in enumerate(PHASES) if p["name"] == current_name),
        0,
    )

    lines = ["Changes requested. Sending feedback to agent..."]
    if feedback_text:
        lines.append(f"  Reason: {feedback_text}")
    # For revising: jump back to current phase
    target = PHASES[current_idx]["name"]

    return CommandResult(
        display_lines=lines,
        switch_to_phase=target,
        phase_jump_allowed=True,
    )


def _handle_navigate(target: str, state: dict[str, Any]) -> CommandResult:
    """Handle /navigate <phase> — jump to a phase with checkpoint."""
    from harness.session.loop import PHASES
    match = next((p for p in PHASES if p["name"] == target), None)
    if match is None:
        names = ", ".join(p["name"] for p in PHASES)
        return CommandResult(display_lines=[
            f"Unknown phase: {target}. Available: {names}"
        ])

    current_name = state.get("phase_def", {}).get("name", "")
    source = current_name

    # Check jump limits (pure logic)
    from harness.session.loop import _check_phase_jump_limit
    jump_counts = state.get("jump_counts", {})
    if not _check_phase_jump_limit(jump_counts, source, target):
        return CommandResult(display_lines=[
            f"Phase jump {source}→{target} exceeds max — blocked."
        ])

    return CommandResult(
        display_lines=[
            f"Jumping to phase: {match['title']} (checkpoint: {match['name']})"
        ],
        switch_to_phase=target,
        phase_jump_allowed=True,
    )


def _handle_feedback(arg: str, state: dict[str, Any]) -> CommandResult:
    """Handle /feedback <target> <reason> — send feedback packet."""
    parts = arg.split(None, 1)
    target = parts[0] if parts else ""
    reason = parts[1] if len(parts) > 1 else ""

    if not target:
        return CommandResult(display_lines=[
            "Usage: /feedback <target_phase> <reason>"
        ])

    from harness.session.loop import PHASES
    match = next((p for p in PHASES if p["name"] == target), None)
    if match is None:
        names = ", ".join(p["name"] for p in PHASES)
        return CommandResult(display_lines=[
            f"Unknown target phase: {target}. Available: {names}"
        ])

    return CommandResult(
        display_lines=[
            f"Feedback sent to phase '{target}'.",
        ],
        switch_to_phase=target,
        phase_jump_allowed=True,
    )


def _handle_consult_resolve(arg: str, state: dict[str, Any]) -> CommandResult:
    """Handle /consult-resolve <index> <resolution>."""
    parts = arg.split(None, 1)
    if not parts:
        return CommandResult(display_lines=[
            "Usage: /consult-resolve <index> <resolution_text>"
        ])

    try:
        idx = int(parts[0])
    except ValueError:
        return CommandResult(display_lines=[
            f"Invalid index: {parts[0]}. Use /consult-resolve <index> <resolution>"
        ])

    resolution = parts[1] if len(parts) > 1 else ""

    pname = state.get("phase_def", {}).get("name", "")
    blocking_consults = state.get("blocking_consults", {})
    consults = blocking_consults.get(pname, [])

    if idx < 0 or idx >= len(consults):
        return CommandResult(display_lines=[
            f"Invalid consult index {idx}: "
            f"phase '{pname}' has {len(consults)} consult(s)."
        ])

    return CommandResult(
        consult_resolved=True,
        display_lines=[
            f"Consult #{idx} resolved."
        ],
    )
