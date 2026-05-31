"""Typed handlers for review operations.

Covers: FinishEngagementHandler, ReviewEngagementHandler.
"""

from __future__ import annotations

from pathlib import Path

from harness.command.types import TypedHandler
from harness.command.commands.review import (
    FinishEngagementCommand,
    ReviewEngagementCommand,
)
from harness.command.results.review import (
    FinishEngagementResult,
    ReviewEngagementResult,
)


class FinishEngagementTypedHandler(TypedHandler[FinishEngagementCommand, FinishEngagementResult]):
    """Complete an engagement: git commit, snapshot update, optional re-assessment."""

    def handle(self, command: FinishEngagementCommand) -> FinishEngagementResult:
        try:
            import subprocess

            root = Path(command.root)
            re_assess = command.re_assess
            slug = command.slug

            from harness.state.freshness import (
                FreshnessRecord,
                load_freshness,
                save_freshness,
            )
            from harness.scm.git import GitRepo
            from harness.cli.helpers import load_project_snapshot
            from harness.paths import get_harness_state_path, get_engagement_dir
            from harness.state.snapshot import SnapshotWriter

            repo = GitRepo(root)
            current_branch = repo.branch()

            # Check freshness
            freshness = load_freshness(root)
            if freshness and freshness.stale:
                return FinishEngagementResult(
                    success=False,
                    error="State is stale. Run `harness catchup` first.",
                    message="Cannot finish: state is stale.",
                )

            # Stage all
            try:
                repo.add()
            except Exception as exc:
                return FinishEngagementResult(
                    success=False,
                    error=str(exc),
                    message="Git add failed.",
                )

            # Write freshness before commit
            current_head = repo.head_sha()
            new_record = FreshnessRecord(
                branch=current_branch,
                head_sha=current_head,
                last_reconciled="",
                stale=False,
            ).mark_fresh(current_head)
            save_freshness(new_record, root)

            # Commit (opens editor when message is empty)
            try:
                head_after = repo.commit()
            except Exception as exc:
                return FinishEngagementResult(
                    success=False,
                    error=str(exc),
                    message="Commit aborted or failed.",
                )

            # Update snapshot status
            snapshot_path = get_harness_state_path(root)
            snapshot = load_project_snapshot(snapshot_path)
            completed_count = 0
            for eng in snapshot.engagements:
                if eng.id == snapshot.current_engagement:
                    eng.status = "complete"
                    completed_count += 1
            SnapshotWriter.write(snapshot, snapshot_path)

            data: dict = {
                "head_sha": head_after,
                "branch": current_branch,
                "slug": slug,
                "completed_engagement": True,
            }

            # Optional re-assessment
            if re_assess:
                from harness.analysis.observer import analyse
                from harness.cli.helpers import write_assessment_report
                from datetime import datetime, timezone

                eng_dir = get_engagement_dir(root, slug)
                assess_dir = eng_dir / "assessments"
                if not assess_dir.is_dir():
                    assess_dir.mkdir(parents=True, exist_ok=True)

                now = datetime.now(timezone.utc)
                timestamp = now.strftime("%Y%m%d-%H%M%S")

                analysis_result = analyse(path=root, deep=True)

                if analysis_result["status"] != "error":
                    import json as _json
                    import yaml as _yaml

                    report_path = assess_dir / f"{timestamp}-assessment.md"
                    report_path.write_text(analysis_result["report"])

                    assessment_dict = analysis_result.get("assessment")
                    current_findings_count = 0
                    if assessment_dict:
                        current_findings_count = len(
                            assessment_dict.get("assessment", {}).get("findings", [])
                        )

                    write_assessment_report(
                        report_text=analysis_result["report"],
                        repo_path=str(root),
                        assessment_dict=assessment_dict,
                    )

                    data["re_assessment"] = {
                        "current_findings": current_findings_count,
                        "report": str(report_path),
                        "timestamp": timestamp,
                    }

            return FinishEngagementResult(
                success=True,
                message=f"Engagement finished @ {head_after[:8]} on {current_branch}.",
                head_sha=head_after,
                branch=current_branch,
                slug=slug,
                completed_engagement=True,
                re_assessment=data.get("re_assessment"),
            )

        except Exception as exc:
            return FinishEngagementResult(
                success=False,
                error=str(exc),
                message=f"Finish failed: {exc}",
            )


class ReviewEngagementTypedHandler(TypedHandler[ReviewEngagementCommand, ReviewEngagementResult]):
    """Record a gate review decision."""

    def handle(self, command: ReviewEngagementCommand) -> ReviewEngagementResult:
        try:
            import asyncio
            from pathlib import Path

            root = Path(command.root)
            decision = command.decision

            if not decision:
                return ReviewEngagementResult(
                    success=False,
                    error="No decision specified.",
                    message="Specify a decision: approved, rejected, or request_changes.",
                )

            temporal_ok = False
            try:
                from harness.state.temporal_server import ensure_temporal_server
                from harness.state.temporal_adapter import send_gate_review

                if ensure_temporal_server():
                    asyncio.run(send_gate_review(command.slug, "", decision))
                    temporal_ok = True
            except Exception:
                pass

            # Update local snapshot
            from harness.cli.helpers import load_project_snapshot
            from harness.paths import get_harness_state_path
            from harness.state.snapshot import SnapshotWriter

            snapshot_path = get_harness_state_path(root)
            snapshot = load_project_snapshot(snapshot_path)
            updated = False
            for eng in snapshot.engagements:
                if eng.id == command.slug:
                    if decision == "approved":
                        eng.status = "complete"
                    elif decision == "rejected":
                        eng.status = "blocked"
                    elif decision == "request_changes":
                        eng.status = "changes_requested"
                    updated = True
                    break

            if updated:
                SnapshotWriter.write(snapshot, snapshot_path)

            gateway = "temporal" if temporal_ok else "local"
            return ReviewEngagementResult(
                success=True,
                message=f"Gate {decision} for engagement {command.slug} ({gateway}).",
                slug=command.slug,
                decision=decision,
                temporal_ok=temporal_ok,
                snapshot_updated=updated,
            )

        except Exception as exc:
            return ReviewEngagementResult(
                success=False,
                error=str(exc),
                message=f"Review failed: {exc}",
            )
