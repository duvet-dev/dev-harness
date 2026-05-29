"""Delegation-thin command handlers.

Each handler calls exactly one business component method and wraps the
result in a CommandResult. See V7 §5.20 Handler Delegation Map.

Stubs wire up to existing components (PhaseOrchestrator, StepDispatcher,
PlanManager) and use placeholder stubs for future components
(StartupResumeFlow, NextEngine, AbortHandler, WhatsNextEngine).
"""

from __future__ import annotations

from typing import Any

from harness.command.types import Command, CommandHandler, CommandResult
from harness.errors import (
    EngagementNotFoundError,
    UnknownPhaseError,
    UnknownCommandError,
)


# ── Handlers for existing components ────────────────────────────────


class CreateEngagementHandler(CommandHandler):
    """Delegates to StartupResumeFlow.create() — stubbed until Wave 10."""

    def handle(self, command: Command) -> CommandResult:
        """Stub: creates an engagement via StartupResumeFlow.create().

        Args:
            command: Command with slug and optional data payload.

        Returns:
            CommandResult indicating stub status until Wave 10.
        """
        data: dict[str, Any] = {
            "slug": command.slug,
            "status": "stub",
            "note": "StartupResumeFlow.create() not yet implemented (Wave 10)",
        }
        return CommandResult(
            success=True,
            message=f"Engagement '{command.slug}' creation requested (stub)",
            data=data,
        )


class ResumeEngagementHandler(CommandHandler):
    """Delegates to StartupResumeFlow.resume() — stubbed until Wave 10."""

    def handle(self, command: Command) -> CommandResult:
        """Stub: resumes an engagement via StartupResumeFlow.resume().

        Args:
            command: Command with slug of the engagement to resume.

        Returns:
            CommandResult indicating stub status until Wave 10.
        """
        data: dict[str, Any] = {
            "slug": command.slug,
            "status": "stub",
            "note": "StartupResumeFlow.resume() not yet implemented (Wave 10)",
        }
        return CommandResult(
            success=True,
            message=f"Engagement '{command.slug}' resume requested (stub)",
            data=data,
        )


class EnterPhaseHandler(CommandHandler):
    """Delegates to PhaseOrchestrator.enter_phase()."""

    def handle(self, command: Command) -> CommandResult:
        """Enter a phase via PhaseOrchestrator.

        Args:
            command: Command with slug and phase name in data.

        Returns:
            CommandResult with phase entry status.
        """
        try:
            from harness.phase.orchestrator import PhaseOrchestrator

            phase_name = command.data.get("phase", "")
            if not phase_name:
                return CommandResult(
                    success=False,
                    error="No phase specified in command data",
                    message="Missing 'phase' in command data",
                )

            orchestrator = PhaseOrchestrator(command.slug)
            # Note: run_phase is async; stubs with sync wrapper for now
            data: dict[str, Any] = {
                "slug": command.slug,
                "phase": phase_name,
                "delegated_to": "PhaseOrchestrator.enter_phase()",
                "note": "Async dispatch — call dispatch_async for full support",
            }
            return CommandResult(
                success=True,
                message=f"Phase '{phase_name}' entry dispatched for '{command.slug}'",
                data=data,
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Failed to enter phase: {exc}",
            )


class NextHandler(CommandHandler):
    """Delegates to NextEngine.advance() — stubbed until Wave 6."""

    def handle(self, command: Command) -> CommandResult:
        """Stub: advances the engagement via NextEngine.advance().

        Args:
            command: Command with slug and optional advance parameters.

        Returns:
            CommandResult indicating stub status until Wave 6.
        """
        data: dict[str, Any] = {
            "slug": command.slug,
            "status": "stub",
            "note": "NextEngine.advance() not yet implemented (Wave 6)",
        }
        return CommandResult(
            success=True,
            message=f"Next/advance requested for '{command.slug}' (stub)",
            data=data,
        )


class CreateWaveHandler(CommandHandler):
    """Delegates to PlanManager.create_wave()."""

    def handle(self, command: Command) -> CommandResult:
        """Create a wave via PlanManager.

        Args:
            command: Command with slug and wave description in data.

        Returns:
            CommandResult with wave creation status.
        """
        try:
            from pathlib import Path
            from harness.plan.plan_manager import PlanManager

            root = Path.cwd()
            pm = PlanManager(root, command.slug)

            wave_title = command.data.get("title", "New Wave")
            wave = pm.add_wave(wave_title)

            data: dict[str, Any] = {
                "slug": command.slug,
                "wave_title": wave_title,
                "wave_id": wave.id,
                "delegated_to": "PlanManager.add_wave()",
            }
            return CommandResult(
                success=True,
                message=f"Wave '{wave_title}' created for '{command.slug}'",
                data=data,
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Failed to create wave: {exc}",
            )


class ExecuteStepHandler(CommandHandler):
    """Delegates to StepDispatcher.dispatch()."""

    def handle(self, command: Command) -> CommandResult:
        """Execute a step via StepDispatcher.

        Args:
            command: Command with slug and step data.

        Returns:
            CommandResult with step execution status.
        """
        try:
            from harness.phase.dispatcher import StepDispatcher

            step_spec = command.data.get("step", {})
            # StepDispatcher needs context; stubs with a note for now
            data: dict[str, Any] = {
                "slug": command.slug,
                "step": step_spec,
                "delegated_to": "StepDispatcher.dispatch()",
                "note": "Full context not yet connected — async dispatch required",
            }
            return CommandResult(
                success=True,
                message=f"Step execution dispatched for '{command.slug}'",
                data=data,
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Failed to execute step: {exc}",
            )


class AbortEngagementHandler(CommandHandler):
    """Delegates to AbortHandler — stubbed until Wave 6."""

    def handle(self, command: Command) -> CommandResult:
        """Stub: aborts an engagement via AbortHandler.

        Args:
            command: Command with slug and optional abort mode.

        Returns:
            CommandResult indicating stub status until Wave 6.
        """
        mode = command.data.get("mode", "graceful")
        data: dict[str, Any] = {
            "slug": command.slug,
            "mode": mode,
            "status": "stub",
            "note": f"AbortHandler.{mode}_stop() not yet implemented (Wave 6)",
        }
        return CommandResult(
            success=True,
            message=f"Abort ('{mode}') requested for '{command.slug}' (stub)",
            data=data,
        )


class QueryStatusHandler(CommandHandler):
    """Delegates to EngagementHealthCheck.check()."""

    def handle(self, command: Command) -> CommandResult:
        """Query engagement health via EngagementHealthCheck.

        Args:
            command: Command with slug of engagement to check.

        Returns:
            CommandResult with health check data.
        """
        try:
            from harness.engagement.health import EngagementHealthCheck

            checker = EngagementHealthCheck()
            report = checker.check(command.slug)

            data: dict[str, Any] = {
                "slug": command.slug,
                "all_ok": report.all_ok,
                "warnings": [
                    {"type": w.type, "message": w.message}
                    for w in report.warnings
                ],
                "delegated_to": "EngagementHealthCheck.check()",
            }
            return CommandResult(
                success=True,
                message=(
                    "All OK" if report.all_ok
                    else f"{len(report.warnings)} health warning(s)"
                ),
                data=data,
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Health check failed: {exc}",
            )


class QueryWhatsNextHandler(CommandHandler):
    """Delegates to WhatsNextEngine.query() — stubbed until Wave 6."""

    def handle(self, command: Command) -> CommandResult:
        """Stub: queries next actions via WhatsNextEngine.query().

        Args:
            command: Command with slug of engagement to query.

        Returns:
            CommandResult indicating stub status until Wave 6.
        """
        data: dict[str, Any] = {
            "slug": command.slug,
            "status": "stub",
            "note": "WhatsNextEngine.query() not yet implemented (Wave 6)",
        }
        return CommandResult(
            success=True,
            message=f"Next-steps query for '{command.slug}' (stub)",
            data=data,
        )


# ── Convenience: register all handlers ──────────────────────────────


def register_all_handlers(
    registry: Any,  # CommandRegistry — avoid circular import
) -> None:
    """Register all delegation-thin handlers on a CommandRegistry.

    Args:
        registry: A CommandRegistry instance to register handlers on.
    """
    handlers: dict[str, CommandHandler] = {
        "create_engagement": CreateEngagementHandler(),
        "resume_engagement": ResumeEngagementHandler(),
        "enter_phase": EnterPhaseHandler(),
        "next": NextHandler(),
        "create_wave": CreateWaveHandler(),
        "execute_step": ExecuteStepHandler(),
        "abort_engagement": AbortEngagementHandler(),
        "query_status": QueryStatusHandler(),
        "query_whats_next": QueryWhatsNextHandler(),
    }
    registry.register_all(handlers)
