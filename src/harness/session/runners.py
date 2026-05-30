"""Session runners — chat_loop and session_loop for interactive sessions.

Moved from the now-deleted session/loop.py. These are the entry points
for interactive chat and phase-by-phase sessions, using InteractiveSession
from interactive.py and helpers from helpers.py.

Replaced by CommandBus dispatch in future waves.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from harness.agents.consultation import ConsultationResult
from dataclasses import dataclass


@dataclass
class _CycleResultStub:
    """Minimal CycleResult stub — migrated from cycle.py (deleted)."""
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
from harness.session.helpers import (
    PHASES,
    _format_jump_marker,
    _init_phase_jump_counts,
    _load_assessment_findings,
    _print_header,
    build_get_well_phase_list,
    _build_system_prompt,
    read_session_type,
    store_session_type,
)

logger = logging.getLogger(__name__)


# ── Interactive chat loop ──────────────────────────────────────────────────


async def chat_loop(
    root: Path,
    engagement_slug: str,
    phase: str = "design",
    one_shot: str | None = None,
    context_tier: int = 2,
) -> None:
    """Run an interactive chat session using InteractiveSession."""
    from harness.session.interactive import InteractiveSession, execute_chat_effects
    from harness.session.commands import route_chat_command
    from harness.session.client import resolve_provider, SessionClient, ChatTranscript, ChatMessage

    provider = resolve_provider(root)
    api_key = provider.get("api_key", "")
    if not api_key:
        click.echo("Error: No API key configured.", err=True)
        return

    phase_def = next(
        (p for p in PHASES if p["name"] == phase), PHASES[0]
    )

    # Build system prompt for one-shot or interactive use
    system_prompt = _build_system_prompt(
        phase_def, root=root, engagement_slug=engagement_slug,
    )

    session = InteractiveSession(
        root=root,
        engagement_slug=engagement_slug,
        phase=phase,
        phase_def=phase_def,
        context_tier=context_tier,
        command_router=route_chat_command,
        effect_executor=execute_chat_effects,
    )
    session.provider = provider
    session.model = provider.get("model", "deepseek-v4-pro")

    # Create client with system prompt
    session.client = SessionClient(
        root=root,
        engagement_slug=engagement_slug,
        phase_def=phase_def,
        context_tier=context_tier,
        system_prompt=system_prompt,
    )

    # Create transcript
    session.transcript = ChatTranscript(
        engagement_slug=engagement_slug,
        phase=phase,
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    # Display header
    from harness.session.helpers import _print_header as _ph
    _ph(
        f"Chat -- {phase_def['title']} (engagement: {engagement_slug})"
    )
    click.echo(f"Model: {session.model}")
    click.echo("Type  /help for commands, /exit to quit")
    click.echo()

    # One-shot mode: single response, no interactive loop
    if one_shot:
        _ph("One-shot response", "-")
        click.echo(f">>> {one_shot}")
        click.echo("-" * 60)
        session.transcript.messages.append(
            ChatMessage(
                role="user",
                content=one_shot,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )
        async for chunk in session.client.stream(one_shot):
            click.echo(chunk, nl=False)
            sys.stdout.flush()
        click.echo()
        click.echo("-" * 60)
        session.transcript.messages.append(
            ChatMessage(
                role="assistant",
                content=session.client.get_last_response(),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )
        session.transcript.ended_at = datetime.now(timezone.utc).isoformat()
        saved = session.transcript.save(root)
        click.echo(f"\nTranscript saved: {saved}")
        return

    # Interactive loop via InteractiveSession
    await session.run()


# ── Full phase-by-phase session loop ───────────────────────────────────────


async def session_loop(
    root: Path,
    engagement_slug: str,
    start_phase: str = "requirements",
    context_tier: int = 2,
    session_type: str | None = None,
) -> None:
    """Run a full session through all phases using InteractiveSession."""
    from harness.session.interactive import (
        InteractiveSession,
        execute_session_effects,
    )
    from harness.session.commands import route_session_command
    from harness.session.client import resolve_provider, ChatTranscript, ChatMessage
    from harness.engagement.checkpoint import CheckpointManager
    from harness.engagement.feedback import FeedbackManager
    from harness.engagement.phase_state import PhaseState as PS
    from harness.engagement.phase_state import PhaseStateManager

    # ── Select phase list ─────────────────────────────
    if session_type is None:
        try:
            st = read_session_type(root, engagement_slug)
            if st:
                session_type = st.value if hasattr(st, "value") else st
        except Exception:
            pass

    # Determine effective phase list based on session type
    is_get_well = session_type == "get-well"
    if is_get_well:
        effective_phases: list[dict] = build_get_well_phase_list()
        assessment_findings = _load_assessment_findings(root, engagement_slug)
    else:
        effective_phases = PHASES
        assessment_findings = None

    # Find starting index
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

    _print_header(f"Session -- {engagement_slug}")
    click.echo(f"Starting from phase: {effective_phases[start_idx]['title']}")
    if session_type:
        click.echo(f"Session type: {session_type}")
    click.echo()

    # Store session type in engagement metadata if provided
    if session_type:
        try:
            store_session_type(root, engagement_slug, session_type)
        except Exception:
            pass

    # Load phase state for cross-phase navigation
    psm = PhaseStateManager(root, engagement_slug)
    ckm = CheckpointManager(root, engagement_slug)
    fbm = FeedbackManager(root, engagement_slug)

    # Shared conversation across all phases
    phase_artifacts: list[str] = []
    phase_conversations: list[str] = []
    blocking_consults: dict[str, list[ConsultationResult]] = {}
    jump_counts: dict[str, int] = _init_phase_jump_counts()

    # ── Build phase list ──────────────────────────
    _phase_list: list[dict] = []
    for phase_idx in range(start_idx, len(effective_phases)):
        phase_def = effective_phases[phase_idx]

        if phase_def["name"] == "implementation":
            # Note: WaveCycleRunner removed; use LoopRunner for wave execution
            from harness.plan.plan_manager import PlanManager

            plan = PlanManager(root, engagement_slug).load()
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

    # ── Phase execution loop ──────────────────────────
    for phase_idx in range(start_idx, len(effective_phases)):
        phase_def = effective_phases[phase_idx]
        click.echo(str(_format_jump_marker(_CycleResultStub(status="complete"))))

        _print_header(f"  Phase {phase_idx + 1 - start_idx}/{len(effective_phases) - start_idx}"
                       f" -- {phase_def['title']}")
        click.echo()

        # Ensure phase is active (idempotent)
        psm.ensure_phase(phase_def["name"])
        if psm.get_state(phase_def["name"]) != PS.ACTIVE:
            psm.transition(phase_def["name"], PS.ACTIVE)

        # Build system prompt
        gw_context = ""
        if assessment_findings and phase_def["name"] in ("assessment-triage", "remediation-requirements", "architecture-design"):
            gw_context = assessment_findings
        system_prompt = _build_system_prompt(
            phase_def, root=root, engagement_slug=engagement_slug,
            context=gw_context,
        )

        phase_conv: list[str] = []

        # Create InteractiveSession for this phase
        session = InteractiveSession(
            root=root,
            engagement_slug=engagement_slug,
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

        from harness.session.client import SessionClient
        session.client = SessionClient(
            root=root,
            engagement_slug=engagement_slug,
            phase_def=phase_def,
            context_tier=context_tier,
            system_prompt=system_prompt,
        )

        session.transcript = ChatTranscript(
            engagement_slug=engagement_slug,
            phase=phase_def["name"],
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        click.echo(f"Model: {model}")
        click.echo()

        next_name = effective_phases[phase_idx + 1]["title"] \
            if phase_idx + 1 < len(effective_phases) else None
        next_hint = f"Your next step is /next to advance to \"{next_name}\"." \
            if next_name else "This is the last phase -- /next will complete the session."

        click.echo(f"  \U0001f4dd {phase_def['title']}")
        if "agent" in phase_def:
            click.echo(f"     Agent: {phase_def['agent']}")
        click.echo(f"  {next_hint}")
        click.echo("  /help shows all commands. Type your prompt to chat with the agent, or use /exit to quit.")
        click.echo()

        # Run the interactive session for this phase
        await session.run()

        # Phase completed -- capture output
        last_resp = session.client.get_last_response() if session.client else ""
        if last_resp:
            phase_artifacts.append(
                f"## {phase_def['title']}\n\n{last_resp}"
            )

        phase_conversations.append("\n".join(phase_conv))

    # All phases complete
    _print_header("Session Complete!")
    click.echo("All phases have been processed.")
