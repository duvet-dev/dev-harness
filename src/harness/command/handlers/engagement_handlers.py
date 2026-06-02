"""Typed handlers for engagement lifecycle.

Covers: CreateEngagementHandler, ResumeEngagementHandler, AbortEngagementHandler.
"""

from __future__ import annotations

from typing import Any

from harness.command.types import TypedHandler
from harness.command.commands.engagement import (
    AbortEngagementCommand,
    CreateEngagementCommand,
    ResumeEngagementCommand,
)
from harness.command.results.engagement import (
    AbortEngagementResult,
    CreateEngagementResult,
    ResumeEngagementResult,
)


class CreateEngagementHandler(TypedHandler[CreateEngagementCommand, CreateEngagementResult]):
    """Create an engagement via StartupResumeFlow.create()."""

    def handle(self, command: CreateEngagementCommand) -> CreateEngagementResult:
        try:
            from pathlib import Path
            from harness.domain.engagement.startup import StartupResumeFlow

            root = Path.cwd()
            flow = StartupResumeFlow(root=root)

            result = flow.create(
                slug=command.slug,
                workflow_name=command.workflow_name,
                session_type=command.session_type,
                mode=command.mode,
            )

            if not result.success:
                return CreateEngagementResult(
                    success=False,
                    error=result.error,
                    message=f"Failed to create engagement '{command.slug}': {result.error}",
                    slug=command.slug,
                )

            engagement = result.engagement
            return CreateEngagementResult(
                success=True,
                message=(
                    f"Engagement '{engagement.slug}' created "
                    f"({engagement.workflow_name} workflow, "
                    f"session_type={engagement.session_type})"
                ),
                slug=engagement.slug,
                workflow_name=engagement.workflow_name,
                status=engagement.status.value,
                current_phase=engagement.current_phase,
                target_branch=engagement.target_branch,
                branch_created=result.branch_created,
                warnings=[
                    {"type": w.type, "message": w.message}
                    for w in result.warnings
                ],
            )

        except Exception as exc:
            return CreateEngagementResult(
                success=False,
                error=str(exc),
                message=f"Failed to create engagement: {exc}",
            )


class ResumeEngagementHandler(TypedHandler[ResumeEngagementCommand, ResumeEngagementResult]):
    """Resume an engagement via StartupResumeFlow.resume()."""

    def handle(self, command: ResumeEngagementCommand) -> ResumeEngagementResult:
        try:
            from pathlib import Path
            from harness.domain.engagement.startup import StartupResumeFlow

            root = Path.cwd()
            flow = StartupResumeFlow(root=root)

            result = flow.resume(slug=command.slug, mode=command.mode)

            if not result.success:
                return ResumeEngagementResult(
                    success=False,
                    error=result.error,
                    message=f"Failed to resume engagement '{command.slug}': {result.error}",
                    slug=command.slug,
                )

            engagement = result.engagement
            return ResumeEngagementResult(
                success=True,
                message=(
                    f"Engagement '{engagement.slug}' resumed "
                    f"(phase: {engagement.current_phase})"
                ),
                slug=engagement.slug,
                status=engagement.status.value,
                current_phase=engagement.current_phase,
                workflow_name=engagement.workflow_name,
                warnings=[
                    {"type": w.type, "message": w.message}
                    for w in result.warnings
                ],
            )

        except Exception as exc:
            return ResumeEngagementResult(
                success=False,
                error=str(exc),
                message=f"Failed to resume engagement: {exc}",
            )


class AbortEngagementTypedHandler(TypedHandler[AbortEngagementCommand, AbortEngagementResult]):
    """Abort an engagement via AbortHandler."""

    def handle(self, command: AbortEngagementCommand) -> AbortEngagementResult:
        try:
            from harness.session.abort import AbortHandler
            from harness.domain.engagement.repository import EngagementRepository
            from pathlib import Path

            root = Path.cwd()
            repo = EngagementRepository(root)
            handler = AbortHandler(engagement_repository=repo)

            if command.mode == "hard":
                result = handler.hard_abort(command.slug)
            else:
                result = handler.graceful_stop(command.slug)

            return AbortEngagementResult(
                success=result.success,
                message=f"Engagement '{command.slug}' {command.mode}-aborted",
                slug=result.slug,
                mode=result.mode,
                previous_status=result.previous_status,
                completed_phases=result.completed_phases,
                current_phase=result.current_phase,
            )

        except Exception as exc:
            return AbortEngagementResult(
                success=False,
                error=str(exc),
                message=f"Abort failed: {exc}",
            )
