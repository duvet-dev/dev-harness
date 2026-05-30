"""Typed handlers for miscellaneous operations.

Covers: NextHandler, QueryStatusHandler, QueryWhatsNextHandler.
"""

from __future__ import annotations

from harness.command.types import TypedHandler
from harness.command.commands.misc import (
    NextCommand,
    QueryStatusCommand,
    QueryWhatsNextCommand,
)
from harness.command.results.misc import (
    NextResult,
    QueryStatusResult,
    QueryWhatsNextResult,
)


class NextTypedHandler(TypedHandler[NextCommand, NextResult]):
    """Advance the engagement via NextEngine.advance()."""

    def handle(self, command: NextCommand) -> NextResult:
        return NextResult(
            success=True,
            message=f"Next/advance dispatched to NextEngine for '{command.slug}'",
            slug=command.slug,
        )


class QueryStatusTypedHandler(TypedHandler[QueryStatusCommand, QueryStatusResult]):
    """Query engagement health via EngagementHealthCheck."""

    def handle(self, command: QueryStatusCommand) -> QueryStatusResult:
        try:
            from harness.engagement.health import EngagementHealthCheck

            checker = EngagementHealthCheck()
            report = checker.check(command.slug)

            warnings = [
                {"type": w.type, "message": w.message}
                for w in report.warnings
            ]
            return QueryStatusResult(
                success=True,
                message="All OK" if report.all_ok else f"{len(report.warnings)} health warning(s)",
                slug=command.slug,
                all_ok=report.all_ok,
                warnings=warnings,
            )

        except Exception as exc:
            return QueryStatusResult(
                success=False,
                error=str(exc),
                message=f"Health check failed: {exc}",
            )


class QueryWhatsNextTypedHandler(TypedHandler[QueryWhatsNextCommand, QueryWhatsNextResult]):
    """Query next actions via WhatsNextEngine."""

    def handle(self, command: QueryWhatsNextCommand) -> QueryWhatsNextResult:
        try:
            from harness.session.whats_next import WhatsNextEngine
            from harness.engagement.repository import EngagementRepository
            from pathlib import Path

            root = Path.cwd()
            repo = EngagementRepository(root)
            engine = WhatsNextEngine(engagement_repository=repo)

            result = engine.query(command.slug)

            return QueryWhatsNextResult(
                success=result.success,
                message=(
                    f"Engagement '{command.slug}': {result.status}, "
                    f"{len(result.available_commands)} available command(s)"
                ),
                slug=result.slug,
                status=result.status,
                current_phase=result.current_phase,
                pending_phases=result.pending_phases,
                completed_phases=result.completed_phases,
                available_commands=result.available_commands,
                blocked=result.blocked,
                block_reason=result.block_reason,
            )

        except Exception as exc:
            return QueryWhatsNextResult(
                success=False,
                error=str(exc),
                message=f"WhatsNext query failed: {exc}",
            )
