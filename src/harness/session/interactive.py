"""Shared interactive session loop — consolidates chat, session, and shell REPLs.

Replaces the duplicated input/command/IO loop in chat_loop(), session_loop(),
and the shell REPL with a single InteractiveSession that delegates to
mode-specific command routers and effect executors.

Usage::
    session = InteractiveSession(
        root=root,
        engagement_slug=slug,
        mode="chat",  # or "session", "shell"
        command_router=route_chat_command,
        effect_executor=execute_chat_effects,
    )
    await session.run()
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import click

from harness.session.client import (
    ChatMessage,
    ChatTranscript,
    SessionClient,
    resolve_provider,
)
from harness.session.loop import (
    PHASES,
    _format_consult_result,
    _write_phase_artifact,
)
from harness.session.commands import CommandResult
from harness.engagement.checkpoint import (
    CHECKPOINT_EXPIRY_HOURS,
    CheckpointManager,
)
from harness.engagement.feedback import FeedbackManager, FeedbackPacket
from harness.engagement.phase_state import PhaseState as PS
from harness.engagement.phase_state import PhaseStateManager

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Shared session state
# ═══════════════════════════════════════════════════════════════════════════════



# ═══════════════════════════════════════════════════════════════════════════════
# Mode-specific effect executors
# ═══════════════════════════════════════════════════════════════════════════════


def execute_session_effects(
    result: CommandResult,
    session: "InteractiveSession",
) -> None:
    """Execute session-mode-specific IO effects.

    Called after common effects for session-specific behaviour:
    phase transitions, checkpoints, consult tracking, etc.
    """
    # advance_phase handler
    if result.advance_phase:
        phase_def_name = session.phase_def.get("name", "")
        phase_def_title = session.phase_def.get("title", "")
        click.echo(f"  + Phase '{phase_def_title}' completed.")
        if result.approved:
            click.echo("  Approved.")
        return  # phase_done flag set externally in the calling code

    # switch_to_phase with checkpoint
    if result.switch_to_phase and result.phase_jump_allowed:
        target = result.switch_to_phase
        match = next(
            (p for p in PHASES if p["name"] == target), None
        )
        if match:
            ckm = CheckpointManager(session.root, session.engagement_slug)
            ckpt = ckm.create(
                phase_name=session.phase_def.get("name", ""),
                context=f"Navigating from {session.phase_def.get('name', '')} to {target}",
            )
            click.echo(f"\n\U0001f4dd Checkpoint saved ({ckpt.checkpoint_id})")
            psm = PhaseStateManager(session.root, session.engagement_slug)
            psm.transition(session.phase_def.get("name", ""), PS.PAUSED)
            psm.ensure_phase(target)
            psm.transition(target, PS.ACTIVE)
            click.echo(f"\U0001f504 Navigating to phase: {target}")
            if session.transcript:
                session.transcript.ended_at = datetime.now(
                    timezone.utc
                ).isoformat()
                session.transcript.save(session.root)
            click.echo(
                f"Session saved. Run 'harness session --phase {target}' to continue."
            )
        return

    # consult_result handling
    if result.consult_result:
        consult_res = result.consult_result
        click.echo()
        click.echo(_format_consult_result(consult_res))
        if (
            consult_res.status == "matched"
            and consult_res.mode == "blocking"
        ):
            pname = session.phase_def.get("name", "")
            blocking_consults = getattr(session, "_blocking_consults", {})
            if pname not in blocking_consults:
                blocking_consults[pname] = []
            blocking_consults[pname].append(consult_res)
            click.echo(
                f"  \u26a0\ufe0f Blocking consult #{len(blocking_consults[pname])}"
                " \u2014 resolve with /consult-resolve"
            )

    # consult_resolved — already handled in command router
    if result.consult_resolved:
        if result.display_lines:
            click.echo(result.display_lines[-1])


def execute_chat_effects(
    result: CommandResult,
    session: "InteractiveSession",
) -> None:
    """Chat-mode specific IO effects.

    Currently minimal — most chat effects are covered by common effects.
    """
    pass


class InteractiveSession:
    """Shared REPL loop for chat, session, and eventually shell modes.

    Attributes:
        mode: Mode name (``"chat"``, ``"session"``, ``"shell"``).
        root: Project root path.
        engagement_slug: Current engagement slug.
        phase: Current phase name.
        phase_def: Phase definition dict.
        provider: Current provider dict.
        model: Current model string.
        client: SessionClient instance.
        transcript: Current chat transcript.
        context_tier: Context bundle tier (1-3).
        _command_router: Callable[[str, dict], CommandResult].
        _effect_executor: Callable[[CommandResult, "InteractiveSession"], None].
        _done: Whether the loop should exit.
    """

    def __init__(
        self,
        root: Path,
        engagement_slug: str,
        phase: str = "design",
        phase_def: dict | None = None,
        context_tier: int = 2,
        command_router: Callable[[str, dict], CommandResult] | None = None,
        effect_executor: Callable[[CommandResult, "InteractiveSession"], None] | None = None,
    ):
        self.root = root
        self.engagement_slug = engagement_slug
        self.phase = phase
        self.phase_def = phase_def or {}
        self.context_tier = context_tier
        self.provider: dict[str, Any] = {}
        self.model: str = ""
        self.client: SessionClient | None = None
        self.transcript: ChatTranscript | None = None
        self._command_router = command_router
        self._effect_executor = effect_executor
        self._done = False

    # ── Setup ────────────────────────────────────────────────────────────

    def resolve_provider(self) -> bool:
        """Resolve the LLM provider. Returns False if no API key."""
        self.provider = resolve_provider(self.root)
        api_key = self.provider.get("api_key", "")
        if not api_key:
            click.echo("Error: No API key configured.", err=True)
            return False
        self.model = self.provider.get("model", "deepseek-v4-pro")
        return True

    def create_client(self) -> None:
        """Create the SessionClient."""
        from harness.session.client import SessionClient
        self.client = SessionClient(
            root=self.root,
            engagement_slug=self.engagement_slug,
            phase_def=self.phase_def,
            context_tier=self.context_tier,
        )

    def create_transcript(self) -> None:
        """Create a new transcript."""
        self.transcript = ChatTranscript(
            engagement_slug=self.engagement_slug,
            phase=self.phase,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

    # ── Command handling ─────────────────────────────────────────────────

    def handle_command(self, cmd: str, cmd_state: dict) -> bool:
        """Route a meta-command and execute its effects.

        Args:
            cmd: Command string (no leading ``/``, lowercased).
            cmd_state: State dict for the command router.

        Returns:
            False if the session should exit, True otherwise.
        """
        if self._command_router is None:
            return True

        result = self._command_router(cmd, cmd_state)

        # Exit
        if result.exit_loop:
            self._done = True
            # Save transcript on exit
            if self.transcript:
                self.transcript.ended_at = datetime.now(
                    timezone.utc
                ).isoformat()
                self.transcript.save(self.root)
            return False

        # Common IO effects
        self._execute_common_effects(result)

        # Mode-specific effects
        if self._effect_executor:
            self._effect_executor(result, self)

        return True

    def _execute_common_effects(self, result: CommandResult) -> None:
        """Execute IO effects shared across all modes."""
        # Display lines
        if result.display_lines:
            for display_line in result.display_lines:
                if display_line == "__list_providers__":
                    self._display_providers()
                else:
                    click.echo(display_line)

        # Help
        if result.set_in_session is not None:
            from harness.session.loop import _print_help
            if hasattr(_print_help, "_in_session"):
                _print_help._in_session = result.set_in_session
            _print_help()

        # Save transcript
        if result.save_transcript and self.transcript:
            self.transcript.ended_at = datetime.now(
                timezone.utc
            ).isoformat()
            saved = self.transcript.save(self.root)
            click.echo(f"Transcript saved: {saved}")

        # Capture artifact
        if result.capture_artifact:
            from harness.session.loop import _write_phase_artifact
            path = _write_phase_artifact(
                self.root, self.engagement_slug, self.phase,
                result.capture_artifact,
            )
            click.echo(f"Artifact written: {path}")

        # Auto-apply file blocks
        if result.auto_apply:
            from harness.session.loop import _apply_file_blocks, _report_apply_results
            apply_results = _apply_file_blocks(self.root, result.auto_apply)
            if apply_results:
                click.echo()
                _report_apply_results(apply_results, self.root)

        # Switch phase with history
        if result.switch_to_phase_with_history and self.client:
            self._switch_phase(result.switch_to_phase_with_history)

        # Switch provider
        if result.new_provider:
            self._switch_provider(result.new_provider)

        # Reset conversation
        if result.reset_conversation and self.client:
            self.client._messages = [
                m for m in self.client._messages
                if m["role"] == "system"
            ]
            if not self.client._messages and self.client.system_prompt:
                self.client._messages.append({
                    "role": "system", "content": self.client.system_prompt,
                })
            click.echo("Conversation reset (phase context retained).")

    def _display_providers(self) -> None:
        """List available providers."""
        from harness.session.loop import list_providers, format_providers_table
        provs = list_providers(self.root)
        if not provs:
            click.echo("No providers found. Check your .harness/providers.yaml.")
        else:
            click.echo()
            click.echo("Available providers:")
            click.echo(format_providers_table(
                provs, current=self.provider.get("name", ""),
            ))
            click.echo(
                f"\nCurrent: {self.provider.get('name', self.model)} / {self.model}"
            )

    def _switch_phase(self, new_phase: str) -> None:
        """Switch to a different phase preserving conversation history."""
        from harness.session.loop import PHASES, _build_system_prompt, _format_conversation_for_context
        match = next(
            (p for p in PHASES if p["name"] == new_phase), None
        )
        if match and self.client:
            self.phase = new_phase
            self.phase_def = match
            hist = _format_conversation_for_context(
                self.client.conversation_history()
            )
            self.client.system_prompt = _build_system_prompt(
                self.phase_def,
                root=self.root,
                engagement_slug=self.engagement_slug,
                conversation=hist,
            )
            for i, m in enumerate(self.client._messages):
                if m["role"] == "system":
                    self.client._messages[i] = {
                        "role": "system",
                        "content": self.client.system_prompt,
                    }
                    break
            else:
                self.client._messages.insert(
                    0,
                    {"role": "system", "content": self.client.system_prompt},
                )

    def _switch_provider(self, target: dict) -> None:
        """Switch to a different provider."""
        from harness.session.loop import switch_provider, list_providers
        new_prov = switch_provider(
            self.root,
            target["target_name"],
            model_alias=target.get("target_alias"),
        )
        if new_prov is None:
            provs = list_providers(self.root)
            names = [p["name"] for p in provs]
            click.echo(
                f"Provider '{target['target_name']}' not found. "
                f"Available: {', '.join(names)}"
            )
            return
        self.provider = new_prov
        self.model = new_prov["model"]
        click.echo(
            f"Switched to provider: {target['target_name']}"
            f" (model: {new_prov['model']})"
        )
        if target.get("target_alias"):
            click.echo(f"  Alias: ~{target['target_alias']}")

    # ── LLM interaction ─────────────────────────────────────────────────

    async def _send_to_llm(self, user_input: str) -> None:
        """Send user input to the LLM and stream the response."""
        if not self.client or not self.transcript:
            return

        self.transcript.messages.append(
            ChatMessage(
                role="user",
                content=user_input,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )

        async for chunk in self.client.stream(user_input):
            click.echo(chunk, nl=False)
            sys.stdout.flush()

        click.echo()

        self.transcript.messages.append(
            ChatMessage(
                role="assistant",
                content=self.client.get_last_response(),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )

    # ── Main loop ───────────────────────────────────────────────────────

    async def run(self) -> None:
        """Run the interactive session loop."""
        if not self.client:
            self.create_client()
        if not self.transcript:
            self.create_transcript()

        while not self._done:
            try:
                user_input = click.prompt(
                    "\nYou", prompt_suffix=" > ", default=""
                )
            except (EOFError, KeyboardInterrupt):
                click.echo()
                break

            if not user_input:
                continue

            # Handle meta-commands
            if user_input.startswith("/"):
                cmd = user_input[1:].strip().lower()

                cmd_state = {
                    "root": self.root,
                    "provider": self.provider,
                    "model": self.model,
                    "engagement_slug": self.engagement_slug,
                    "last_response": (
                        self.client.get_last_response()
                        if self.client else None
                    ),
                    "client_messages": (
                        self.client._messages if self.client else []
                    ),
                    "system_prompt": (
                        self.client.system_prompt if self.client else ""
                    ),
                }

                if not self.handle_command(cmd, cmd_state):
                    return

            else:
                # Send to LLM
                await self._send_to_llm(user_input)

        # Cleanup on exit
        if self.transcript:
            self.transcript.ended_at = datetime.now(
                timezone.utc
            ).isoformat()
            self.transcript.save(self.root)
