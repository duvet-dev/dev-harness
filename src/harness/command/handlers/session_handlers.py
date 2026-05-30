"""Typed handlers for session and chat operations.

Covers: SessionHandler, ChatHandler.
"""

from __future__ import annotations

from pathlib import Path

from harness.command.types import TypedHandler
from harness.command.commands.session import ChatCommand, SessionCommand
from harness.command.results.session import ChatResult, SessionResult


class SessionTypedHandler(TypedHandler[SessionCommand, SessionResult]):
    """Start a phase-walking session."""

    def handle(self, command: SessionCommand) -> SessionResult:
        try:
            from harness.engagement.startup import StartupResumeFlow

            root = Path.cwd()
            phase = command.phase
            session_type = command.session_type
            context_tier = command.context_tier
            get_well = command.get_well

            if get_well and phase == "requirements":
                phase = "assessment-triage"

            flow = StartupResumeFlow(root=root)
            result = flow.create(
                slug=command.slug,
                session_type=session_type or "greenfield",
                mode="auto",
            )

            if result.success:
                return SessionResult(
                    success=True,
                    message=f"Session started for '{command.slug}' (phase: {phase})",
                    slug=command.slug,
                    phase=phase,
                    phase_entered=getattr(result, "phase_entered", ""),
                    session_type=session_type or "greenfield",
                    context_tier=context_tier,
                    get_well=get_well,
                )
            return SessionResult(
                success=False,
                error=result.error,
                message=f"Failed to start session: {result.error}",
            )

        except Exception as exc:
            return SessionResult(
                success=False,
                error=str(exc),
                message=f"Session failed: {exc}",
            )


class ChatTypedHandler(TypedHandler[ChatCommand, ChatResult]):
    """Open a chat session via SessionClient."""

    def handle(self, command: ChatCommand) -> ChatResult:
        try:
            from harness.session.client import resolve_provider, SessionClient
            from harness.paths import get_engagement_dir

            root = Path.cwd()
            prompt = command.prompt
            phase = command.phase
            context_tier = command.context_tier

            eng_dir = get_engagement_dir(root, command.slug)
            if not eng_dir.is_dir():
                return ChatResult(
                    success=False,
                    error=f"Engagement directory not found: {eng_dir}",
                    message=f"Engagement '{command.slug}' not found",
                )

            provider = resolve_provider(root)
            SessionClient(root, provider=provider, verbose=True)

            return ChatResult(
                success=True,
                message=f"Chat session opened for '{command.slug}' (phase: {phase})",
                slug=command.slug,
                phase=phase,
                context_tier=context_tier,
                prompt=prompt,
            )

        except Exception as exc:
            return ChatResult(
                success=False,
                error=str(exc),
                message=f"Chat failed: {exc}",
            )
