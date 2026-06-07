"""Phase-specific session entry points.

Provides the entry point functions for ``/assess``, ``/requirements``,
``/design``, ``/plan``, and ``/build`` commands in both the REPL and CLI.

Each function:
1. Resolves the active engagement
2. Loads the correct phase-specific agent and system prompt
3. Creates an InteractiveSession wired to the agent
4. Runs the session loop showing which agent the user is talking to

Architecture:
- Phase-specific sessions use the same InteractiveSession infrastructure
  as regular sessions but with a dedicated phase agent as the chat agent.
- The system prompt is built from the phase definition AND the agent's
  SOP, giving the agent a clear identity.
- Context from previous phases is loaded and injected.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

import click

from harness.agents.agent_registry import get_phase_agent
from harness.agents.auto_mode import DEFAULT_MAX_ITERATIONS
from harness.domain.engagement.resolver import resolve_active_engagement

logger = logging.getLogger(__name__)


# ── Phase-to-name mapping ────────────────────────────────────────────────

PHASE_MAP: dict[str, str] = {
    "assess": "assess",
    "requirements": "discover",
    "design": "design",
    "plan": "planning",
    "planning": "planning",
    "build": "build",
}

PHASE_AGENT_MAP: dict[str, str] = {
    "assess": "assessment-agent",
    "requirements": "requirements-agent",
    "design": "design-agent",
    "plan": "planning-agent",
    "planning": "planning-agent",
    "build": "build-agent",
}


def _resolve_phase_for_entry(entry_name: str) -> str | None:
    """Map an entry command name to the canonical phase name.

    Entry commands are one of: assess, requirements, design, plan, build.
    """
    return PHASE_MAP.get(entry_name)


def _get_phase_agent_name(entry_name: str) -> str | None:
    """Get the dedicated agent role for an entry command."""
    return PHASE_AGENT_MAP.get(entry_name)


def _build_phase_system_prompt(
    phase_name: str,
    agent_role: str,
) -> str:
    """Build a phase-specific system prompt that includes the agent identity."""
    agent = get_phase_agent(phase_name)
    agent_title = agent.name if agent else agent_role.replace("-", " ").title()

    base_prompt = f"""You are a **{agent_title}**. You are in the {phase_name.upper()} phase of a development engagement.

YOUR ROLE:
{agent.description if agent else f'Drive the {phase_name} phase of the engagement.'}

YOUR SOP:
{chr(10).join(f'- {s}' for s in (agent.sop_summary if agent else []))}

YOUR BOUNDARIES:
- Stay focused on your phase. Do not implement or design outside your scope.
- Use the RepoTool to read and write files.
- Present your work clearly. Use Markdown headings and structured output.
- If you detect issues outside your phase, flag them but don't act on them.

You have restricted write access to your phase's artifact directories.
"""

    return base_prompt


# ── Phase session entry point ────────────────────────────────────────────


async def run_phase_entry_session(
    root: Path,
    entry_name: str,
) -> None:
    """Run a phase-specific session.

    This is the entry point for ``/assess``, ``/requirements``, ``/design``,
    ``/plan``, and ``/build`` commands.

    Args:
        root: Project root directory.
        entry_name: The entry command name (assess, requirements, design,
            plan, build).
    """
    from harness.session.client import (
        ChatTranscript,
        SessionClient,
        resolve_provider,
    )
    from harness.session.helpers import _build_system_prompt, _print_header
    from harness.session.phase_source import find_phase, get_phases
    from harness.session.session_orchestrator import (
        InteractiveSession,
        execute_session_effects,
    )
    from harness.session.commands import route_session_command

    slug = resolve_active_engagement(root)
    if not slug:
        click.echo("No active engagement. Create one with:")
        click.echo("  /work \"your task\"")
        return

    phase_name = _resolve_phase_for_entry(entry_name)
    if not phase_name:
        click.echo(f"Unknown phase entry: {entry_name}")
        return

    agent_role = _get_phase_agent_name(entry_name)
    agent = get_phase_agent(agent_role) if agent_role else None
    agent_display = agent.name if agent else phase_name.title()

    # Load phase definition
    phase_def = find_phase(phase_name, root)
    if not phase_def:
        phases = get_phases(root)
        phase_def = next((p for p in phases if p["name"] == phase_name), None)
    if not phase_def:
        click.echo(f"Phase definition not found: {phase_name}")
        return

    provider = resolve_provider(root)
    api_key = provider.get("api_key", "")
    if not api_key:
        click.echo("Error: No API key configured.", err=True)
        return

    model = provider.get("model", "deepseek-v4-pro")

    # Build system prompt with agent identity
    agent_system_prompt = _build_phase_system_prompt(phase_name, agent_role or "unknown")
    system_prompt = _build_system_prompt(
        phase_def,
        root=root,
        engagement_slug=slug,
    )

    # Inject agent identity into the prompt
    full_prompt = f"{agent_system_prompt}\n\n---\n\n{system_prompt}"

    _print_header(f"{agent_display} — {phase_def['title']} (engagement: {slug})")
    click.echo(f"Agent: {agent_display}")
    click.echo(f"Model: {model}")
    click.echo()

    # Build context from previous phases
    context = _load_previous_phase_context(root, slug, phase_name)

    # ── Auto mode prompt ──────────────────────────────────────────────
    from harness.agents.auto_mode import PhaseAutoRunner, ManualOverride, prompt_auto_mode, load_auto_mode_state

    # Check for existing auto mode state (for resume)
    existing_state = load_auto_mode_state(root, slug, phase_name)
    if existing_state and existing_state.status == "interrupted":
        click.echo("\n  Found an interrupted auto mode session.")
        resume_choice = click.prompt(
            "Resume auto mode?",
            type=click.Choice(["resume", "interactive", "start-over"], case_sensitive=False),
            default="resume",
        )
        if resume_choice == "resume":
            click.echo("\n  Resuming auto mode...")
            override = ManualOverride()
            runner = PhaseAutoRunner(
                root=root,
                engagement_slug=slug,
                phase_name=phase_name,
                agent_role=agent_role or "unknown",
                max_iterations=DEFAULT_MAX_ITERATIONS,
                override=override,
            )
            runner.state = existing_state
            runner.state.status = "running"
            final_state = await runner.run()
            click.echo(f"\n  Auto mode complete: {final_state.status.value}")
        elif resume_choice == "start-over":
            from harness.agents.auto_mode import clear_auto_mode_state
            clear_auto_mode_state(root, slug, phase_name)
            click.echo("  Cleared previous state. Starting fresh.")
            use_auto = True
        else:
            use_auto = False
    else:
        use_auto = prompt_auto_mode()

    if use_auto:
        click.echo(f"\n  Running {agent_display} in auto mode...")
        click.echo(f"  Max iterations: {DEFAULT_MAX_ITERATIONS}")
        click.echo("  Press Ctrl+C or type /stop to interrupt.\n")

        # Set up manual override handler
        override = ManualOverride()

        # Run auto mode
        runner = PhaseAutoRunner(
            root=root,
            engagement_slug=slug,
            phase_name=phase_name,
            agent_role=agent_role or "unknown",
            max_iterations=DEFAULT_MAX_ITERATIONS,
            override=override,
        )
        final_state = await runner.run()

        if final_state.status == "interrupted":
            click.echo(
                "\n  Auto mode interrupted. You can review the work done so far "
                "and interact with the agent."
            )
            click.echo("  Use /resume to restart auto mode when ready.\n")
        elif final_state.status in ("converged", "completed"):
            click.echo(f"\n  \u2713 Auto mode {final_state.status.value}.")
            click.echo(
                "  You can now interact with the agent or move to the next phase.\n"
            )
        elif final_state.status == "max-iterations":
            click.echo(
                "\n  \u26a0 Auto mode reached max iterations. Review the artifacts "
                "and decide next steps.\n"
            )
        else:
            click.echo(f"\n  Auto mode finished: {final_state.status.value}\n")

    # ── Interactive session ────────────────────────────────────────────
    click.echo(
        "Entering interactive session. "
        "Type your prompt to chat with the agent, or /help for commands."
    )
    click.echo()

    session = InteractiveSession(
        root=root,
        engagement_slug=slug,
        phase=phase_name,
        phase_def=phase_def,
        command_router=route_session_command,
        effect_executor=execute_session_effects,
    )
    session.provider = provider
    session.model = model
    session._phase_artifacts = context.get("artifacts", [])
    session._phase_conv = context.get("conversations", [])

    session.client = SessionClient(
        root=root,
        engagement_slug=slug,
        phase_def=phase_def,
        system_prompt=full_prompt,
    )

    session.transcript = ChatTranscript(
        engagement_slug=slug,
        phase=phase_name,
        started_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    )

    await session.run()


def _load_previous_phase_context(
    root: Path,
    slug: str,
    current_phase: str,
) -> dict[str, Any]:
    """Load artifacts and conversation history from previous phases.

    Args:
        root: Project root directory.
        slug: Engagement slug.
        current_phase: The current phase name. Phases before this in
            the phase order are considered "previous".

    Returns:
        Dict with ``artifacts`` (list of str) and ``conversations``
        (list of str) from previous phases.
    """
    from harness.session.phase_source import get_phase_order

    phase_order = get_phase_order(root)
    try:
        current_idx = phase_order.index(current_phase)
        previous_phases = phase_order[:current_idx]
    except ValueError:
        return {"artifacts": [], "conversations": []}

    artifacts: list[str] = []
    conversations: list[str] = []

    from harness.paths import get_engagement_dir
    eng_dir = get_engagement_dir(root, slug)

    for prev_phase in previous_phases:
        # Try to load artifact files from engagement directory
        phase_artifacts = eng_dir / prev_phase / "artifacts"
        if phase_artifacts.is_dir():
            for f in sorted(phase_artifacts.iterdir()):
                if f.is_file() and f.suffix in (".md", ".yaml", ".txt"):
                    try:
                        content = f.read_text()
                        artifacts.append(
                            f"## Artifact from {prev_phase}: {f.name}\n\n{content}"
                        )
                    except Exception:
                        pass

        # Try to load chat transcripts
        phase_chat = eng_dir / prev_phase / "chat"
        if phase_chat.is_dir():
            for f in sorted(phase_chat.iterdir()):
                if f.is_file() and f.suffix == ".md":
                    try:
                        conversations.append(
                            f"## Conversation from {prev_phase}\n\n{f.read_text()}"
                        )
                    except Exception:
                        pass

    return {"artifacts": artifacts, "conversations": conversations}


# ── CLI entry points ─────────────────────────────────────────────────────


def run_assess(root: Path) -> None:
    """Entry point for ``/assess``."""
    asyncio.run(run_phase_entry_session(root, "assess"))


def run_requirements(root: Path) -> None:
    """Entry point for ``/requirements``."""
    asyncio.run(run_phase_entry_session(root, "requirements"))


def run_design(root: Path) -> None:
    """Entry point for ``/design``."""
    asyncio.run(run_phase_entry_session(root, "design"))


def run_plan(root: Path) -> None:
    """Entry point for ``/plan``."""
    asyncio.run(run_phase_entry_session(root, "plan"))


def run_build(root: Path) -> None:
    """Entry point for ``/build``."""
    asyncio.run(run_phase_entry_session(root, "build"))


# ── Command handler mapping for REPL integration ───────────────────────


PHASE_ENTRY_HANDLERS: dict[str, Any] = {
    "assess": run_assess,
    "requirements": run_requirements,
    "design": run_design,
    "plan": run_plan,
    "build": run_build,
}
