"""Session orchestrator — entry points for interactive chat and phase sessions.

Replaces ``harness.session.runners`` (``chat_loop`` / ``session_loop``).

Provides:
- ``run_chat_session()`` — one-off chat via ``SessionClient``
- ``run_phase_session()`` — multi-phase session via ``PhaseOrchestrator``
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
from harness.session.commands import CommandResult
from harness.session.helpers import (
    PHASES,
    _apply_file_blocks,
    _format_consult_result,
    _report_apply_results,
    _write_phase_artifact,
)
from harness.domain.engagement.checkpoint import (
    CHECKPOINT_EXPIRY_HOURS,
    CheckpointManager,
)
from harness.domain.engagement.feedback import FeedbackManager, FeedbackPacket
from harness.domain.engagement.phase_state import PhaseState as PS
from harness.domain.engagement.phase_state import PhaseStateManager

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# InteractiveSession — consolidated from harness.session.interactive
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
            from harness.session.helpers import _print_help
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
            path = _write_phase_artifact(
                self.root, self.engagement_slug, self.phase,
                result.capture_artifact,
            )
            click.echo(f"Artifact written: {path}")

        # Auto-apply file blocks
        if result.auto_apply:
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
        from harness.session.helpers import list_providers, format_providers_table
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
        from harness.session.helpers import _build_system_prompt, _format_conversation_for_context
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
        from harness.session.helpers import switch_provider, list_providers
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

        last_response = self.client.get_last_response()
        self.transcript.messages.append(
            ChatMessage(
                role="assistant",
                content=last_response,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )

        # Auto-process ## File: blocks — write files to disk immediately
        apply_results = _apply_file_blocks(self.root, last_response)
        if apply_results:
            click.echo()
            _report_apply_results(apply_results, self.root)

    # ── Main loop ───────────────────────────────────────────────────────

    async def run(self) -> None:
        """Run the interactive session loop."""
        if not self.client:
            self.create_client()
        if not self.transcript:
            self.create_transcript()

        while not self._done:
            try:
                phase_tag = f"[{self.phase}]" if self.phase else ""
                user_input = click.prompt(
                    f"\n{phase_tag} You", prompt_suffix=" > ", default=""
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
                    "_phase_list": getattr(self, "_phase_list", None),
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


# ═══════════════════════════════════════════════════════════════════════════════
# Session entry points
# ═══════════════════════════════════════════════════════════════════════════════


async def run_chat_session(
    root: Path,
    slug: str,
    phase: str = "design",
    one_shot: str | None = None,
    context_tier: int = 2,
    client: Any | None = None,
) -> None:
    """Run an interactive chat session using SessionClient.

    Delegates to ``InteractiveSession`` from ``harness.session.interactive``.

    Args:
        root: Project root directory.
        slug: Engagement slug.
        phase: Phase name to chat within.
        one_shot: If set, a single response (no interactive loop).
        context_tier: Context tier level (1-3).
        client: Pre-constructed SessionClient, or None to create one.
    """
    from harness.session.client import (
        ChatMessage,
        ChatTranscript,
        SessionClient,
        resolve_provider,
    )
    from harness.session.commands import route_chat_command
    from harness.session.helpers import PHASES, _build_system_prompt

    import click
    import sys
    from datetime import datetime, timezone

    provider = resolve_provider(root)
    api_key = provider.get("api_key", "")
    if not api_key:
        click.echo("Error: No API key configured.", err=True)
        return

    phase_def = next(
        (p for p in PHASES if p["name"] == phase), PHASES[0]
    )

    system_prompt = _build_system_prompt(
        phase_def, root=root, engagement_slug=slug,
    )

    if client is None:
        client = SessionClient(
            root=root,
            engagement_slug=slug,
            phase_def=phase_def,
            context_tier=context_tier,
            system_prompt=system_prompt,
        )

    from harness.session.helpers import _print_header as _ph
    _ph(f"Chat -- {phase_def['title']} (engagement: {slug})")

    model = provider.get("model", "deepseek-v4-pro")
    click.echo(f"Model: {model}")
    click.echo("Type  /help for commands, /exit to quit")
    click.echo()

    if one_shot:
        _ph("One-shot response", "-")
        click.echo(f">>> {one_shot}")
        click.echo("-" * 60)
        transcript = ChatTranscript(
            engagement_slug=slug,
            phase=phase,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        transcript.messages.append(
            ChatMessage(
                role="user",
                content=one_shot,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )
        async for chunk in client.stream(one_shot):
            click.echo(chunk, nl=False)
            sys.stdout.flush()
        click.echo()
        click.echo("-" * 60)
        transcript.messages.append(
            ChatMessage(
                role="assistant",
                content=client.get_last_response(),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )
        transcript.ended_at = datetime.now(timezone.utc).isoformat()
        saved = transcript.save(root)
        click.echo(f"\nTranscript saved: {saved}")
        return

    session = InteractiveSession(
        root=root,
        engagement_slug=slug,
        phase=phase,
        phase_def=phase_def,
        context_tier=context_tier,
        command_router=route_chat_command,
        effect_executor=execute_chat_effects,
    )
    session.provider = provider
    session.model = model
    session.client = client
    session.transcript = ChatTranscript(
        engagement_slug=slug,
        phase=phase,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    await session.run()


async def run_phase_session(
    root: Path,
    slug: str,
    start_phase: str = "requirements",
    context_tier: int = 2,
    session_type: str | None = None,
    orchestrator: Any | None = None,
) -> None:
    """Run a full phase-by-phase session.

    Delegates to ``InteractiveSession`` for per-phase interactive loops.

    Args:
        root: Project root directory.
        slug: Engagement slug.
        start_phase: Phase to start from.
        context_tier: Context tier level (1-3).
        session_type: Session type identifier (e.g. "get-well", "greenfield").
        orchestrator: Pre-constructed PhaseOrchestrator, or None to create one.
    """
    from harness.domain.engagement.checkpoint import CheckpointManager
    from harness.domain.engagement.feedback import FeedbackManager
    from harness.domain.engagement.phase_state import PhaseState as PS
    from harness.domain.engagement.phase_state import PhaseStateManager
    from harness.session.client import (
        ChatTranscript,
        SessionClient,
        resolve_provider,
    )
    from harness.session.commands import route_session_command
    from harness.session.helpers import (
        PHASES,
        _build_system_prompt,
        _format_jump_marker,
        _init_phase_jump_counts,
        _load_assessment_findings,
        _print_header,
        build_get_well_phase_list,
        read_session_type,
        store_session_type,
    )
    # InteractiveSession and execute_session_effects are defined
    # at module level in this file (consolidated from interactive.py)

    import click
    from dataclasses import dataclass
    from datetime import datetime, timezone

    @dataclass
    class _CycleResultStub:
        """Minimal CycleResult stub."""
        status: str = "complete"

        @property
        def is_phase_jump(self) -> bool:
            return False

        @property
        def jump_target(self) -> str | None:
            return None

        @property
        def summary(self) -> str:
            return ""

    from harness.agents.consultation import ConsultationResult

    if session_type is None:
        try:
            st = read_session_type(root, slug)
            if st:
                session_type = st.value if hasattr(st, "value") else st
        except Exception:
            pass

    is_get_well = session_type == "get-well"
    if is_get_well:
        effective_phases: list[dict] = build_get_well_phase_list()
        assessment_findings = _load_assessment_findings(root, slug)
    else:
        effective_phases = PHASES
        assessment_findings = None

    start_idx = 0
    for i, p in enumerate(effective_phases):
        if p["name"] == start_phase:
            start_idx = i
            break
    if start_idx == 0 and start_phase != effective_phases[0]["name"]:
        start_idx = 0

    provider = resolve_provider(root)
    api_key = provider.get("api_key", "")
    if not api_key:
        click.echo("Error: No API key configured.", err=True)
        return

    model = provider.get("model", "deepseek-v4-pro")

    _print_header(f"Session -- {slug}")
    click.echo(f"Starting from phase: {effective_phases[start_idx]['title']}")
    if session_type:
        click.echo(f"Session type: {session_type}")
    click.echo()

    if session_type:
        try:
            store_session_type(root, slug, session_type)
        except Exception:
            pass

    psm = PhaseStateManager(root, slug)
    ckm = CheckpointManager(root, slug)
    fbm = FeedbackManager(root, slug)

    phase_artifacts: list[str] = []
    phase_conversations: list[str] = []
    blocking_consults: dict[str, list[ConsultationResult]] = {}
    jump_counts: dict[str, int] = _init_phase_jump_counts()

    _phase_list: list[dict] = []
    for phase_idx in range(start_idx, len(effective_phases)):
        phase_def = effective_phases[phase_idx]
        if phase_def["name"] == "implementation":
            from harness.plan.plan_manager import PlanManager
            plan = PlanManager(root, slug).load()
            uncommitted = [w for w in plan.waves if not w.is_committed()]
            if uncommitted:
                click.echo(
                    f"\n\U0001f4cb Plan defines {len(uncommitted)} uncommitted wave(s). "
                    "Running per-wave code+test cycles.\n"
                )
                for w in uncommitted:
                    click.echo()
                    click.echo("\u2500" * 50)
                    click.echo(f"  Wave {w.id}: {w.title}  [{w.type}]")
                    click.echo("\u2500" * 50)
        _phase_list.append(phase_def)

    for phase_idx in range(start_idx, len(effective_phases)):
        phase_def = effective_phases[phase_idx]
        click.echo(str(_format_jump_marker(_CycleResultStub(status="complete"))))

        _print_header(f"  Phase {phase_idx + 1 - start_idx}/"
                       f"{len(effective_phases) - start_idx}"
                       f" -- {phase_def['title']}")
        click.echo()

        psm.ensure_phase(phase_def["name"])
        if psm.get_state(phase_def["name"]) != PS.ACTIVE:
            psm.transition(phase_def["name"], PS.ACTIVE)

        gw_context = ""
        if assessment_findings and phase_def["name"] in (
            "assessment-triage", "remediation-requirements", "architecture-design"
        ):
            gw_context = assessment_findings
        system_prompt = _build_system_prompt(
            phase_def, root=root, engagement_slug=slug,
            context=gw_context,
        )

        phase_conv: list[str] = []

        session = InteractiveSession(
            root=root,
            engagement_slug=slug,
            phase=phase_def["name"],
            phase_def=phase_def,
            context_tier=context_tier,
            command_router=route_session_command,
            effect_executor=execute_session_effects,
        )
        session.provider = provider
        session.model = model
        session._blocking_consults = blocking_consults
        session._phase_artifacts = phase_artifacts
        session._phase_conv = phase_conv
        session._phase_done = False
        session._phase_list = _phase_list

        session.client = SessionClient(
            root=root,
            engagement_slug=slug,
            phase_def=phase_def,
            context_tier=context_tier,
            system_prompt=system_prompt,
        )

        session.transcript = ChatTranscript(
            engagement_slug=slug,
            phase=phase_def["name"],
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        click.echo(f"Model: {model}")
        click.echo()

        next_name = effective_phases[phase_idx + 1]["title"] \
            if phase_idx + 1 < len(effective_phases) else None
        next_hint = (
            f"Your next step is /next to advance to \"{next_name}\"."
            if next_name
            else "This is the last phase -- /next will complete the session."
        )

        click.echo(f"  \U0001f4dd {phase_def['title']}")
        if "agent" in phase_def:
            click.echo(f"     Agent: {phase_def['agent']}")
        click.echo(f"  {next_hint}")
        click.echo(
            "  /help shows all commands. Type your prompt to chat with "
            "the agent, or use /exit to quit."
        )
        click.echo()

        await session.run()

        last_resp = session.client.get_last_response() if session.client else ""
        if last_resp:
            phase_artifacts.append(
                f"## {phase_def['title']}\n\n{last_resp}"
            )
        phase_conversations.append("\n".join(phase_conv))

    _print_header("Session Complete!")
    click.echo("All phases have been processed.")
