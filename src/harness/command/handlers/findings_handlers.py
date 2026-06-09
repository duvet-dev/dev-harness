"""Typed handlers for Findings Registry operations.

Provides handlers for list, show, update-status, confirm-signoff,
and sync operations on engagement findings.
"""

from __future__ import annotations

from pathlib import Path

from harness.command.types import TypedHandler
from harness.command.commands.findings import (
    FindingsListCommand,
    FindingsShowCommand,
    FindingsUpdateStatusCommand,
    FindingsConfirmSignoffCommand,
    FindingsSyncCommand,
)
from harness.command.results.findings import (
    FindingsListResult,
    FindingsShowResult,
    FindingsUpdateStatusResult,
    FindingsConfirmSignoffResult,
    FindingsSyncResult,
)


def _open_store(slug: str):
    """Open the FindingsStore for the given engagement slug.

    Resolves the project root from CWD and returns the (root, store) tuple.
    """
    from harness.paths import resolve_project_root
    from harness.domain.engagement.findings import FindingsStore
    root = resolve_project_root()
    return root, FindingsStore(root, slug)


# ── List handler ─────────────────────────────────────────────────────────────


class FindingsListTypedHandler(TypedHandler[FindingsListCommand, FindingsListResult]):
    """List findings from the registry, with optional filtering."""

    def handle(self, command: FindingsListCommand) -> FindingsListResult:
        try:
            _, store = _open_store(command.slug)
            findings = store.all_findings

            if command.status:
                findings = [f for f in findings if f.status == command.status]
            if command.severity:
                findings = [f for f in findings if f.severity == command.severity]
            if command.source:
                findings = [f for f in findings if f.source == command.source]

            return FindingsListResult(
                success=True,
                message=f"{len(findings)} finding(s)",
                findings=[f.to_dict() for f in findings],
                total=len(findings),
            )
        except Exception as exc:
            return FindingsListResult(
                success=False,
                error=str(exc),
                message=f"Failed to list findings: {exc}",
            )


# ── Show handler ──────────────────────────────────────────────────────────────


class FindingsShowTypedHandler(TypedHandler[FindingsShowCommand, FindingsShowResult]):
    """Show a single finding by ID."""

    def handle(self, command: FindingsShowCommand) -> FindingsShowResult:
        try:
            _, store = _open_store(command.slug)
            finding = store.get(command.finding_id)
            if finding is None:
                return FindingsShowResult(
                    success=False,
                    error="not_found",
                    message=f"Finding '{command.finding_id}' not found",
                )
            return FindingsShowResult(
                success=True,
                message=f"Finding {command.finding_id}",
                finding=finding.to_dict(),
            )
        except Exception as exc:
            return FindingsShowResult(
                success=False,
                error=str(exc),
                message=f"Failed to show finding: {exc}",
            )


# ── Update status handler ──────────────────────────────────────────────────────


class FindingsUpdateStatusTypedHandler(
    TypedHandler[FindingsUpdateStatusCommand, FindingsUpdateStatusResult]
):
    """Update a finding's status with lifecycle validation."""

    def handle(self, command: FindingsUpdateStatusCommand) -> FindingsUpdateStatusResult:
        try:
            _, store = _open_store(command.slug)
            finding = store.get(command.finding_id)
            if finding is None:
                return FindingsUpdateStatusResult(
                    success=False,
                    error="not_found",
                    message=f"Finding '{command.finding_id}' not found",
                )
            old_status = finding.status
            store.update_status(command.finding_id, command.new_status)
            store.save()
            return FindingsUpdateStatusResult(
                success=True,
                message=f"Finding '{command.finding_id}': {old_status} → {command.new_status}",
                finding_id=command.finding_id,
                old_status=old_status,
                new_status=command.new_status,
            )
        except Exception as exc:
            return FindingsUpdateStatusResult(
                success=False,
                error=str(exc),
                message=f"Failed to update finding status: {exc}",
            )


# ── Confirm sign-off handler ──────────────────────────────────────────────────


class FindingsConfirmSignoffTypedHandler(
    TypedHandler[FindingsConfirmSignoffCommand, FindingsConfirmSignoffResult]
):
    """Confirm human sign-off for a resolved/pending finding."""

    def handle(self, command: FindingsConfirmSignoffCommand) -> FindingsConfirmSignoffResult:
        try:
            _, store = _open_store(command.slug)
            finding = store.confirm_human_signoff(command.finding_id)
            if finding is None:
                return FindingsConfirmSignoffResult(
                    success=False,
                    error="not_found",
                    message=f"Finding '{command.finding_id}' not found",
                )
            return FindingsConfirmSignoffResult(
                success=True,
                message=f"Human sign-off confirmed for '{command.finding_id}'",
                finding_id=command.finding_id,
                confirmed=True,
            )
        except Exception as exc:
            return FindingsConfirmSignoffResult(
                success=False,
                error=str(exc),
                message=f"Failed to confirm sign-off: {exc}",
            )


# ── Sync handler ────────────────────────────────────────────────────────────────


class FindingsSyncTypedHandler(TypedHandler[FindingsSyncCommand, FindingsSyncResult]):
    """Run analysis and sync results into the Findings Registry."""

    def handle(self, command: FindingsSyncCommand) -> FindingsSyncResult:
        try:
            from harness.analysis.observer import analyse
            from harness.domain.engagement.findings import FindingsStore
            root, store = _open_store(command.slug)

            # Run observer analysis
            result = analyse(path=str(root), deep=command.deep)

            if result["status"] == "error":
                return FindingsSyncResult(
                    success=False,
                    error=result.get("message", "Unknown error"),
                    message=f"Analysis failed: {result.get('message', '')}",
                )

            # Sync scan results from observer
            from harness.analysis.base import ScanResult
            scans: list = result.get("scans", [])
            delta_from_scans = store.sync_from_scan_results(
                [ScanResult(scan_name=k, findings=[]) for k in scans],
                scope="observer",
            )

            # Sync assessment findings if available
            delta_from_assessment = None
            assessment = result.get("assessment")
            if assessment and command.assess:
                ad = assessment.get("assessment", {})
                assessment_findings = ad.get("findings", [])
                if assessment_findings:
                    delta_from_assessment = store.sync_from_assessment(
                        assessment_findings,
                        source="assessment",
                        scope="observer",
                    )

            # Combine deltas
            new_total = len(delta_from_scans.new)
            resolved_total = len(delta_from_scans.resolved)
            regression_total = len(delta_from_scans.regressions)
            wf_regression_total = len(delta_from_scans.wont_fix_regressions)

            if delta_from_assessment:
                new_total += len(delta_from_assessment.new)
                resolved_total += len(delta_from_assessment.resolved)
                regression_total += len(delta_from_assessment.regressions)
                wf_regression_total += len(delta_from_assessment.wont_fix_regressions)

            delta_lines = delta_from_scans.summary_lines()

            return FindingsSyncResult(
                success=True,
                message=f"Analysis synced: {new_total} new, "
                        f"{resolved_total} resolved, "
                        f"{regression_total} regressions, "
                        f"{wf_regression_total} wont-fix regressions",
                new_count=new_total,
                resolved_count=resolved_total,
                regression_count=regression_total,
                wont_fix_regression_count=wf_regression_total,
                delta_summary=delta_lines,
            )
        except Exception as exc:
            return FindingsSyncResult(
                success=False,
                error=str(exc),
                message=f"Failed to sync findings: {exc}",
            )
