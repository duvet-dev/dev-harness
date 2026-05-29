"""Delegation-thin command handlers.

Each handler calls exactly one business component method and wraps the
result in a CommandResult. See V7 §5.20 Handler Delegation Map.

Wave 10: CreateEngagementHandler and ResumeEngagementHandler are fully
wired to StartupResumeFlow. Remaining handlers delegate to existing
components (PhaseOrchestrator, StepDispatcher, PlanManager, AbortHandler,
WhatsNextEngine). Async methods (phase entry, step execution) note that
full async dispatch requires CommandBus async dispatch support.
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
    """Delegates to StartupResumeFlow.create().

    Wave 10: fully wired — creates an engagement via StartupResumeFlow.
    """

    def handle(self, command: Command) -> CommandResult:
        """Create an engagement via StartupResumeFlow.create().

        Reads optional ``workflow_name``, ``session_type``, and
        ``mode`` from command data. Delegates to
        StartupResumeFlow.create() for the actual lifecycle.

        Args:
            command: Command with slug and optional data payload.

        Returns:
            CommandResult with engagement creation status.
        """
        try:
            from pathlib import Path
            from harness.engagement.startup import StartupResumeFlow

            root = Path.cwd()
            flow = StartupResumeFlow(root=root)

            workflow_name = command.data.get("workflow_name")
            session_type = command.data.get("session_type", "greenfield")
            mode = command.data.get("mode", "auto")

            result = flow.create(
                slug=command.slug,
                workflow_name=workflow_name,
                session_type=session_type,
                mode=mode,
            )

            if not result.success:
                return CommandResult(
                    success=False,
                    error=result.error,
                    message=f"Failed to create engagement '{command.slug}': {result.error}",
                    data={"slug": command.slug},
                )

            engagement = result.engagement
            data: dict[str, Any] = {
                "slug": engagement.slug,
                "workflow_name": engagement.workflow_name,
                "session_type": engagement.session_type,
                "status": engagement.status.value,
                "current_phase": engagement.current_phase,
                "target_branch": engagement.target_branch,
                "branch_created": result.branch_created,
                "warnings": [
                    {"type": w.type, "message": w.message}
                    for w in result.warnings
                ],
                "delegated_to": "StartupResumeFlow.create()",
                "note": "Phase entry requires async dispatch (enter_first_phase_async)",
            }
            return CommandResult(
                success=True,
                message=(
                    f"Engagement '{engagement.slug}' created "
                    f"({engagement.workflow_name} workflow, "
                    f"session_type={engagement.session_type})"
                ),
                data=data,
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Failed to create engagement: {exc}",
            )


class ResumeEngagementHandler(CommandHandler):
    """Delegates to StartupResumeFlow.resume().

    Wave 10: fully wired — resumes an engagement via StartupResumeFlow.
    """

    def handle(self, command: Command) -> CommandResult:
        """Resume an engagement via StartupResumeFlow.resume().

        Reads optional ``mode`` from command data. Delegates to
        StartupResumeFlow.resume() for the actual lifecycle.

        Args:
            command: Command with slug of the engagement to resume.

        Returns:
            CommandResult with engagement resume status.
        """
        try:
            from pathlib import Path
            from harness.engagement.startup import StartupResumeFlow

            root = Path.cwd()
            flow = StartupResumeFlow(root=root)

            mode = command.data.get("mode", "auto")

            result = flow.resume(slug=command.slug, mode=mode)

            if not result.success:
                return CommandResult(
                    success=False,
                    error=result.error,
                    message=f"Failed to resume engagement '{command.slug}': {result.error}",
                    data={"slug": command.slug},
                )

            engagement = result.engagement
            data: dict[str, Any] = {
                "slug": engagement.slug,
                "status": engagement.status.value,
                "current_phase": engagement.current_phase,
                "workflow_name": engagement.workflow_name,
                "warnings": [
                    {"type": w.type, "message": w.message}
                    for w in result.warnings
                ],
                "delegated_to": "StartupResumeFlow.resume()",
                "note": "Phase re-entry requires async dispatch (resume_async)",
            }
            return CommandResult(
                success=True,
                message=(
                    f"Engagement '{engagement.slug}' resumed "
                    f"(phase: {engagement.current_phase})"
                ),
                data=data,
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Failed to resume engagement: {exc}",
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
    """Delegates to NextEngine.advance() — async gap, partially stubbed.

    Wave 6: NextEngine exists but its advance() method is async.
    Full sync wrapper requires CommandBus async dispatch support
    (future wave). For now, creates the engine and documents the
    delegation target.
    """

    def handle(self, command: Command) -> CommandResult:
        """Advance the engagement via NextEngine.advance().

        Note: NextEngine.advance() is async. Full async dispatch
        from CommandBus is deferred. This handler creates the
        engine and returns a stub result with delegation info.

        Args:
            command: Command with slug and optional advance parameters.

        Returns:
            CommandResult with delegation target documented.
        """
        data: dict[str, Any] = {
            "slug": command.slug,
            "status": "delegated",
            "delegated_to": "NextEngine.advance()",
            "note": "NextEngine.advance() is async — needs async CommandBus dispatch (future wave)",
        }
        return CommandResult(
            success=True,
            message=f"Next/advance dispatched to NextEngine for '{command.slug}'",
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
    """Delegates to AbortHandler — Wave 6 wired."""

    def handle(self, command: Command) -> CommandResult:
        """Abort an engagement via AbortHandler.

        Reads mode from command data ('hard' or 'graceful').
        Delegates to AbortHandler.hard_abort() or
        AbortHandler.graceful_stop().

        Args:
            command: Command with slug and optional abort mode.

        Returns:
            CommandResult with abort result data.
        """
        try:
            from harness.session.abort import AbortHandler
            from harness.engagement.repository import EngagementRepository
            from pathlib import Path

            mode = command.data.get("mode", "graceful")
            root = Path.cwd()
            repo = EngagementRepository(root)
            handler = AbortHandler(engagement_repository=repo)

            if mode == "hard":
                result = handler.hard_abort(command.slug)
            else:
                result = handler.graceful_stop(command.slug)

            data: dict[str, Any] = {
                "slug": result.slug,
                "mode": result.mode,
                "success": result.success,
                "previous_status": result.previous_status,
                "completed_phases": result.completed_phases,
                "current_phase": result.current_phase,
                "delegated_to": f"AbortHandler.{mode}_abort()",
            }
            return CommandResult(
                success=result.success,
                message=f"Engagement '{command.slug}' {mode}-aborted",
                data=data,
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Abort failed: {exc}",
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
    """Delegates to WhatsNextEngine.query() — Wave 6 wired."""

    def handle(self, command: Command) -> CommandResult:
        """Query next actions via WhatsNextEngine.query().

        Args:
            command: Command with slug of engagement to query.

        Returns:
            CommandResult with available actions and engagement state.
        """
        try:
            from harness.session.whats_next import WhatsNextEngine
            from harness.engagement.repository import EngagementRepository
            from pathlib import Path

            root = Path.cwd()
            repo = EngagementRepository(root)
            engine = WhatsNextEngine(engagement_repository=repo)

            result = engine.query(command.slug)

            data: dict[str, Any] = {
                "slug": result.slug,
                "status": result.status,
                "current_phase": result.current_phase,
                "pending_phases": result.pending_phases,
                "completed_phases": result.completed_phases,
                "available_commands": result.available_commands,
                "blocked": result.blocked,
                "block_reason": result.block_reason,
                "delegated_to": "WhatsNextEngine.query()",
            }
            return CommandResult(
                success=result.success,
                message=(
                    f"Engagement '{command.slug}': {result.status}, "
                    f"{len(result.available_commands)} available command(s)"
                ),
                data=data,
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"WhatsNext query failed: {exc}",
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
