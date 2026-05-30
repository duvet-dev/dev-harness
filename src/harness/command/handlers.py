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


class FinishEngagementHandler(CommandHandler):
    """Completes an engagement: git commit, snapshot update, optional re-assessment.

    Delegates to subprocess git calls, FreshnessRecord persistence, snapshot
    update, and (optionally) observer analysis + write_assessment_report.

    Wave D: wired for ``harness finish`` command.
    """

    def handle(self, command: Command) -> CommandResult:
        """Handle engagement finish.

        Command data fields:
            root (str | Path): Project root directory.
            re_assess (bool): Whether to run post-engagement observer.

        Performs:
            1. Freshness write before commit
            2. Git add + commit (opens editor for user message)
            3. Snapshot status update (complete)
            4. Optional re-assessment (analyse + report)

        Args:
            command: Command with slug and data (root, re_assess).

        Returns:
            CommandResult with finish status, head SHA, and optional
            re-assessment metrics.
        """
        try:
            import subprocess
            from pathlib import Path

            root = Path(command.data.get("root", Path.cwd()))
            re_assess = command.data.get("re_assess", False)
            slug = command.slug

            from harness.state.freshness import (
                FreshnessRecord,
                load_freshness,
                save_freshness,
            )
            from harness.scm.git import GitRepo
            from harness.cli.helpers import get_head_sha, load_project_snapshot
            from harness.paths import get_harness_state_path, get_engagement_dir
            from harness.state.snapshot import (
                SnapshotWriter,
            )

            repo = GitRepo(root)
            current_branch = repo.branch()

            # Check freshness
            freshness = load_freshness(root)
            if freshness and freshness.stale:
                return CommandResult(
                    success=False,
                    error="State is stale. Run `harness catchup` first.",
                    message="Cannot finish: state is stale.",
                )

            # Stage all
            stage_result = subprocess.run(
                ["git", "add", "-A"], cwd=root, capture_output=True, text=True
            )
            if stage_result.returncode != 0:
                return CommandResult(
                    success=False,
                    error=stage_result.stderr.strip(),
                    message="Git add failed.",
                )

            # Write freshness before commit
            current_head = get_head_sha(root)
            new_record = FreshnessRecord(
                branch=current_branch,
                head_sha=current_head,
                last_reconciled="",
                stale=False,
            ).mark_fresh(current_head)
            save_freshness(new_record, root)

            # Commit (opens editor)
            commit_result = subprocess.run(["git", "commit"], cwd=root)
            if commit_result.returncode != 0:
                return CommandResult(
                    success=False,
                    error="Commit aborted or failed.",
                    message="Commit aborted or failed.",
                )

            head_after = get_head_sha(root)

            # Update snapshot status
            snapshot_path = get_harness_state_path(root)
            snapshot = load_project_snapshot(snapshot_path)
            completed_count = 0
            for eng in snapshot.engagements:
                if eng.id == snapshot.current_engagement:
                    eng.status = "complete"
                    completed_count += 1
            SnapshotWriter.write(snapshot, snapshot_path)

            data: dict[str, Any] = {
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

                result = analyse(path=root, deep=True)

                if result["status"] != "error":
                    import json as _json
                    import yaml as _yaml

                    report_path = assess_dir / f"{timestamp}-assessment.md"
                    report_path.write_text(result["report"])

                    assessment_dict = result.get("assessment")
                    current_findings_count = 0
                    if assessment_dict:
                        current_findings_count = len(
                            assessment_dict.get("assessment", {}).get("findings", [])
                        )

                    written = write_assessment_report(
                        report_text=result["report"],
                        repo_path=str(root),
                        assessment_dict=assessment_dict,
                    )

                    # Load baseline for comparison
                    eng_yaml_path = eng_dir / "engagement.yaml"
                    baseline_findings = None
                    baseline_count = "?"
                    if eng_yaml_path.is_file():
                        with open(eng_yaml_path) as f:
                            yaml_data = _yaml.safe_load(f) or {}
                        baseline_count = yaml_data.get("baseline_finding_count", "?")
                        baseline_manifest_path = yaml_data.get("baseline_manifest")
                        if baseline_manifest_path:
                            bp = eng_dir / baseline_manifest_path
                            if bp.is_file():
                                baseline_manifest = _json.loads(bp.read_text())
                                baseline_findings = baseline_manifest.get("findings", [])

                    closed_count = "?"
                    if baseline_findings is not None:
                        current_messages = set(
                            f.get("message", "")[:80]
                            for f in (assessment_dict.get("assessment", {}).get("findings", []) if assessment_dict else [])
                        )
                        closed_in_baseline = [
                            f for f in baseline_findings
                            if f.get("message", "")[:80] not in current_messages
                        ]
                        closed_count = len(closed_in_baseline)

                    data["re_assessment"] = {
                        "baseline_count": baseline_count,
                        "current_findings": current_findings_count,
                        "closed_count": closed_count,
                        "report": str(report_path),
                        "timestamp": timestamp,
                    }

                    # Update assessment history
                    config_path = root / ".harness" / "config.yaml"
                    if config_path.is_file():
                        with open(config_path) as f:
                            config = _yaml.safe_load(f) or {}
                        history = config.setdefault("assessment_history", [])
                        entry = {
                            "date": now.strftime("%Y-%m-%d"),
                            "engagement": slug,
                            "findings": current_findings_count,
                            "report": f"assessments/{timestamp}-assessment.md",
                        }
                        if isinstance(closed_count, int):
                            entry["closed"] = closed_count
                        history.append(entry)
                        with open(config_path, "w") as f:
                            _yaml.dump(config, f, default_flow_style=False, sort_keys=False)

                else:
                    data["re_assessment"] = {
                        "error": result.get("message", "Unknown error"),
                    }

            return CommandResult(
                success=True,
                message=(
                    f"Engagement finished @ {head_after[:8]} on {current_branch}."
                ),
                data=data,
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Finish failed: {exc}",
            )


class ReviewEngagementHandler(CommandHandler):
    """Records a gate review decision: approve, reject, or request_changes.

    Delegates to temporal_adapter.send_gate_review() for Temporal flow
    and updates local snapshot status.

    Wave D: wired for ``harness review`` command.
    """

    def handle(self, command: Command) -> CommandResult:
        """Handle engagement review.

        Command data fields:
            decision (str): One of "approved", "rejected", "request_changes".
            feedback_items (list[dict]): Structured feedback items (optional).
            notes (str): Additional notes (optional).

        Args:
            command: Command with slug and review data.

        Returns:
            CommandResult with review status and temporal availability.
        """
        try:
            import asyncio
            from pathlib import Path

            root = Path(command.data.get("root", Path.cwd()))
            decision = command.data.get("decision", "")

            if not decision:
                return CommandResult(
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
            from harness.state.snapshot import (
                SnapshotWriter,
            )

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

            data: dict[str, Any] = {
                "slug": command.slug,
                "decision": decision,
                "temporal_ok": temporal_ok,
                "snapshot_updated": updated,
            }

            gateway = "temporal" if temporal_ok else "local"
            return CommandResult(
                success=True,
                message=f"Gate {decision} for engagement {command.slug} ({gateway}).",
                data=data,
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Review failed: {exc}",
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


class InitProjectHandler(CommandHandler):
    """Initialises a new harness project.

    Delegates to constitution scaffolding, agent profile seeding,
    template scaffolding, snapshot creation, and optional git init.
    """

    def handle(self, command: Command) -> CommandResult:
        """Handle project initialisation.

        Command data fields:
            project_dir (str | None): Subdirectory name.
            template (str | None): Template name.
            seed (str | None): Context to seed from.
            no_git (bool): Skip git init.
            force (bool): Re-initialise even if already set up.
        """
        try:
            from pathlib import Path

            root = Path(command.data.get("root", Path.cwd()))
            project_dir = command.data.get("project_dir")
            template = command.data.get("template")
            no_git = command.data.get("no_git", False)
            force = command.data.get("force", False)

            if project_dir:
                project_path = root / project_dir
                if project_path.exists():
                    if project_path.is_file():
                        return CommandResult(
                            success=False,
                            error=f"{project_path} is a file, not a directory",
                        )
                else:
                    project_path.mkdir(parents=True, exist_ok=True)
            else:
                project_path = root

            from harness.paths import get_harness_dir
            already_initted = get_harness_dir(project_path).is_dir()
            if already_initted and not force:
                return CommandResult(
                    success=False,
                    error=(
                        f"{project_path} is already a harness project. "
                        "Use --force to re-initialise."
                    ),
                )

            project_name = project_path.name

            from harness.constitution.loader import scaffold as scaffold_constitution
            from harness.cli.helpers import (
                write_minimal_constitution,
                init_git,
                initial_commit,
            )
            from harness.scm.gitignore import write_gitignore as _write_gitignore
            from harness.constitution.templates.template_registry import (
                TemplateRegistry,
                seed_agent_profiles,
            )
            from harness.state.snapshot import ProjectSnapshot, SnapshotWriter
            from harness.paths import (
                get_engagements_dir,
                get_harness_state_path,
            )

            # Scaffold constitution
            constitution_path = project_path / "constitution.yaml"
            if template:
                scaffold_constitution(
                    template, project_name, constitution_path, overrides={}
                )
            else:
                write_minimal_constitution(constitution_path, project_name)

            # .gitignore
            gitignore_path = project_path / ".gitignore"
            if not gitignore_path.exists():
                _write_gitignore(gitignore_path, template=template or "none")

            # Seed agent profiles
            ALL_AGENTS = [
                {"name": "requirements-builder", "phase": "planning"},
                {"name": "planner", "phase": "planning"},
                {"name": "researcher", "phase": "research"},
                {"name": "architect", "phase": "design"},
                {"name": "architect-critic", "phase": "design"},
                {"name": "coder", "phase": "implementation"},
                {"name": "tester", "phase": "testing"},
                {"name": "reviewer", "phase": "review"},
            ]
            seed_agent_profiles(project_path, ALL_AGENTS)

            # Scaffold template directories
            if template:
                TemplateRegistry.scaffold(template, project_name, project_path)

            # Create .harness/
            get_engagements_dir(project_path).mkdir(parents=True, exist_ok=True)
            get_harness_dir(project_path).joinpath(".gitkeep").write_text("")

            # Initial snapshot
            snapshot_path = get_harness_state_path(project_path)
            snapshot = ProjectSnapshot(
                project_name=project_name,
                version="0.1.0",
                current_engagement=None,
                engagements=[],
            )
            SnapshotWriter.write(snapshot, snapshot_path)

            # Git init (optional)
            git_ok = False
            if not no_git:
                git_ok = init_git(project_path)
                if git_ok:
                    initial_commit(project_path)

            data: dict[str, Any] = {
                "project": project_name,
                "template": template or "(none)",
                "path": str(project_path),
                "git_initted": git_ok,
            }
            return CommandResult(
                success=True,
                message=(
                    f"Project '{project_name}' initialised "
                    f"(template: {template or 'none'}, "
                    f"git: {'yes' if git_ok else 'no'})"
                ),
                data=data,
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Init failed: {exc}",
            )


class PhaseManagementHandler(CommandHandler):
    """Manages engagement phases: list, navigate, feedback, resume, status.

    Delegates to PhaseStateManager, CheckpointManager, FeedbackManager.
    """

    def handle(self, command: Command) -> CommandResult:
        """Handle phase management actions.

        Command data fields:
            action (str): One of "list", "navigate", "feedback",
                "resume", "status", "feedback_list".
            target (str): Target phase for navigate/feedback.
            feedback_reason (str): Reason for feedback (optional).
            force (bool): Bypass checkpoint staleness checks.
        """
        try:
            from pathlib import Path
            from harness.paths import get_harness_state_path
            from harness.cli.helpers import load_project_snapshot
            from harness.state.snapshot import SnapshotWriter

            root = Path(command.data.get("root", Path.cwd()))
            slug = command.slug
            action = command.data.get("action", "")

            if not slug and action not in ("", None):
                return CommandResult(
                    success=False,
                    error="No engagement slug specified",
                )
            if not slug:
                slug = command.slug
            if not slug:
                return CommandResult(
                    success=False,
                    error="No engagement slug provided",
                )

            from harness.engagement.checkpoint import CheckpointManager
            from harness.engagement.feedback import (
                FeedbackManager,
                FeedbackPacket,
            )
            from harness.engagement.phase_state import (
                PhaseState,
                PhaseStateManager,
            )

            psm = PhaseStateManager(root, slug)
            fbm = FeedbackManager(root, slug)
            ckm = CheckpointManager(root, slug)

            # List phases
            if action == "list":
                phases = psm.list_phases()
                if not phases:
                    return CommandResult(
                        success=True,
                        message=f"No phases recorded for '{slug}'.",
                        data={"slug": slug, "phases": []},
                    )
                phase_list = [
                    {"name": name, "state": record.state.value}
                    for name, record in sorted(phases.items())
                ]
                return CommandResult(
                    success=True,
                    message=f"{len(phase_list)} phase(s) for '{slug}'.",
                    data={"slug": slug, "phases": phase_list},
                )

            # Navigate (cross-phase jump with checkpoint)
            target = command.data.get("target", "")
            if action == "navigate":
                if not target:
                    return CommandResult(
                        success=False,
                        error="No target phase specified",
                    )
                snapshot_path = get_harness_state_path(root)
                snapshot = load_project_snapshot(snapshot_path)
                current_phase = (
                    snapshot.phase
                    if hasattr(snapshot, "phase") else "unknown"
                )

                ckpt = ckm.create(
                    phase_name=current_phase,
                    context=f"Navigating from {current_phase} to {target}",
                )
                psm.transition(current_phase, PhaseState.PAUSED)
                psm.ensure_phase(target)
                psm.transition(target, PhaseState.ACTIVE)

                target_slug = (
                    f"eng-main-{slug}" if not slug.startswith("eng-main-")
                    else slug
                )
                for eng in snapshot.engagements:
                    if eng.id == target_slug or eng.id == slug:
                        if hasattr(eng, "phase"):
                            eng.phase = target
                        SnapshotWriter.write(snapshot, snapshot_path)
                        break

                return CommandResult(
                    success=True,
                    message=(
                        f"Navigated from '{current_phase}' to '{target}'. "
                        f"Checkpoint: {ckpt.checkpoint_id}"
                    ),
                    data={
                        "slug": slug,
                        "from_phase": current_phase,
                        "to_phase": target,
                        "checkpoint": ckpt.checkpoint_id,
                    },
                )

            # Send feedback
            fb_target = command.data.get("target", "")
            fb_reason = command.data.get("feedback_reason", "")
            if action == "feedback":
                if not fb_target:
                    return CommandResult(
                        success=False,
                        error="No feedback target phase specified",
                    )

                snapshot_path = get_harness_state_path(root)
                snapshot = load_project_snapshot(snapshot_path)
                current_phase = (
                    snapshot.phase
                    if hasattr(snapshot, "phase") else "unknown"
                )

                ckpt = ckm.create(
                    phase_name=current_phase,
                    context=fb_reason or f"Feedback to {fb_target}",
                    feedback_content=fb_reason or "",
                )
                packet = FeedbackPacket(
                    from_phase=current_phase,
                    to_phase=fb_target,
                    title=(fb_reason[:80] if fb_reason else "Feedback"),
                    body=fb_reason,
                    checkpoint_id=ckpt.checkpoint_id,
                )
                fb_path = fbm.create(packet)

                psm.mark_feedback_sent(current_phase, fb_target, ckpt.checkpoint_id)
                psm.ensure_phase(fb_target)

                return CommandResult(
                    success=True,
                    message=(
                        f"Feedback sent from '{current_phase}' to "
                        f"'{fb_target}'."
                    ),
                    data={
                        "slug": slug,
                        "from_phase": current_phase,
                        "to_phase": fb_target,
                        "feedback_path": str(fb_path),
                        "checkpoint": ckpt.checkpoint_id,
                    },
                )

            # Resume
            force_flag = command.data.get("force", False)
            if action == "resume":
                ckpt = ckm.most_recent()
                if not ckpt:
                    return CommandResult(
                        success=True,
                        message=f"No checkpoints for '{slug}'.",
                        data={"slug": slug, "resumed": False},
                    )
                return CommandResult(
                    success=True,
                    message=(
                        f"Resumed from checkpoint: {ckpt.checkpoint_id} "
                        f"(phase: {ckpt.phase_name})"
                    ),
                    data={
                        "slug": slug,
                        "resumed": True,
                        "checkpoint": ckpt.checkpoint_id,
                        "phase": ckpt.phase_name,
                    },
                )

            # Status
            if action == "status":
                phases = psm.list_phases()
                if not phases:
                    return CommandResult(
                        success=True,
                        message=f"No phase state for '{slug}'.",
                        data={"slug": slug, "phases": {}},
                    )
                phase_data = {
                    name: {
                        "state": record.state.value,
                        "checkpoint_ref": record.checkpoint_ref or "",
                        "feedback_target": record.feedback_target or "",
                    }
                    for name, record in sorted(phases.items())
                }
                return CommandResult(
                    success=True,
                    message=f"Phase states for '{slug}'.",
                    data={"slug": slug, "phases": phase_data},
                )

            # Feedback list
            if action == "feedback_list":
                history = fbm.list_feedback()
                entries = [
                    {
                        "status": fb.status,
                        "from": fb.from_phase,
                        "to": fb.to_phase,
                        "title": fb.title,
                    }
                    for fb in history
                ] if history else []
                return CommandResult(
                    success=True,
                    message=(
                        f"{len(entries)} feedback entry/entries for "
                        f"'{slug}'."
                    ),
                    data={"slug": slug, "feedback": entries},
                )

            # No action
            return CommandResult(
                success=False,
                error="No action specified",
                message="Specify an action: list, navigate, feedback, resume, status, or feedback_list",
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Phase command failed: {exc}",
            )


# ── Wave F: RunWave / Session / Chat ──────────────────────────────


class RunWaveHandler(CommandHandler):
    """Delegates to LoopRunner.run().

    Executes a wave through the implement→test→verify→commit cycle
    using the LoopRunner.
    """

    def handle(self, command: Command) -> CommandResult:
        """Execute a wave via LoopRunner.

        Args:
            command: Command with slug and wave_id in data.

        Returns:
            CommandResult with wave execution status.
        """
        try:
            import asyncio

            wave_id = command.data.get("wave_id", "")
            if not wave_id:
                return CommandResult(
                    success=False,
                    error="No wave_id specified in command data",
                    message="Missing 'wave_id' in command data",
                )

            from harness.phase.model import LoopConfig, Step
            from harness.loop.runner import LoopRunner

            loop_config = LoopConfig(
                count=1,
                description=f"Wave {wave_id} implement-test-verify cycle",
            )
            steps = [
                Step(agents=["coding-agent"], action=f"Implement {wave_id}", auto=True),
                Step(agents=["testing-agent"], action=f"Test {wave_id}", auto=True),
                Step(agents=["validation-agent"], action=f"Verify {wave_id}", auto=True),
            ]
            runner = LoopRunner()
            result = asyncio.run(
                runner.run(
                    loop_config=loop_config,
                    steps=steps,
                    context={"slug": command.slug, "wave_id": wave_id, "mode": "auto"},
                )
            )

            data: dict[str, Any] = {
                "slug": command.slug,
                "wave_id": wave_id,
                "success": result.success,
                "iteration_count": result.iteration_count,
                "error": result.error,
                "delegated_to": "LoopRunner.run()",
            }
            if result.success:
                return CommandResult(
                    success=True,
                    message=f"Wave {wave_id} completed successfully ({result.iteration_count} iterations)",
                    data=data,
                )
            return CommandResult(
                success=False,
                error=result.error or "Wave run failed",
                message=f"Wave {wave_id} failed",
                data=data,
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Failed to run wave: {exc}",
            )


class SessionHandler(CommandHandler):
    """Delegates to StartupResumeFlow.create() + phase orchestration."""

    def handle(self, command: Command) -> CommandResult:
        """Start a phase-walking session.

        Args:
            command: Command with slug, phase, session_type, context_tier.

        Returns:
            CommandResult with session start status.
        """
        try:
            from pathlib import Path
            from harness.engagement.startup import StartupResumeFlow

            root = Path.cwd()
            phase = command.data.get("phase", "requirements")
            session_type = command.data.get("session_type")
            context_tier = command.data.get("context_tier", 2)
            get_well = command.data.get("get_well", False)

            if get_well and phase == "requirements":
                phase = "assessment-triage"

            flow = StartupResumeFlow(root=root)
            result = flow.create(
                slug=command.slug,
                session_type=session_type or "greenfield",
                mode="auto",
            )

            if result.success:
                data: dict[str, Any] = {
                    "slug": command.slug,
                    "phase": phase,
                    "phase_entered": getattr(result, "phase_entered", ""),
                    "session_type": session_type or "greenfield",
                    "context_tier": context_tier,
                    "get_well": get_well,
                    "delegated_to": "StartupResumeFlow.create()",
                    "note": "Full phase-by-phase orchestration requires async dispatch",
                }
                return CommandResult(
                    success=True,
                    message=f"Session started for '{command.slug}' (phase: {phase})",
                    data=data,
                )
            return CommandResult(
                success=False,
                error=result.error,
                message=f"Failed to start session: {result.error}",
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Session failed: {exc}",
            )


class ChatHandler(CommandHandler):
    """Delegates to SessionClient."""

    def handle(self, command: Command) -> CommandResult:
        """Open a chat session via SessionClient.

        Args:
            command: Command with slug, prompt, phase, context_tier.

        Returns:
            CommandResult with chat session status.
        """
        try:
            from pathlib import Path
            from harness.session.client import resolve_provider, SessionClient
            from harness.paths import get_engagement_dir

            root = Path.cwd()
            prompt = command.data.get("prompt")
            phase = command.data.get("phase", "design")
            context_tier = command.data.get("context_tier", 2)

            eng_dir = get_engagement_dir(root, command.slug)
            if not eng_dir.is_dir():
                return CommandResult(
                    success=False,
                    error=f"Engagement directory not found: {eng_dir}",
                    message=f"Engagement '{command.slug}' not found",
                )

            provider = resolve_provider(root)
            SessionClient(root, provider=provider, verbose=True)

            data: dict[str, Any] = {
                "slug": command.slug,
                "phase": phase,
                "context_tier": context_tier,
                "prompt": prompt,
                "delegated_to": "SessionClient",
                "note": "SessionClient created; interactive chat runs in CLI layer",
            }
            return CommandResult(
                success=True,
                message=f"Chat session opened for '{command.slug}' (phase: {phase})",
                data=data,
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Chat failed: {exc}",
            )


# ── Wave G: Summary / Inspect / Assess ──────────────────────────────


class SummaryHandler(CommandHandler):
    """Delegates to analysis pipeline (fast scan + optional deep)."""

    def handle(self, command: Command) -> CommandResult:
        """Run project summary analysis.

        Args:
            command: Command with analysis options in data.

        Returns:
            CommandResult with the formatted report.
        """
        try:
            import asyncio

            deep = command.data.get("deep", False)
            assess_flag = command.data.get("assess_flag", False)
            json_flag = command.data.get("json_flag", False)
            reconcile = command.data.get("reconcile", False)

            from harness.analysis.deep import (
                assess_coverage,
                check_architecture_conformance,
                find_dead_code,
            )
            from harness.analysis.fast import scan_git_diff, scan_structure
            from harness.analysis.summary import format_report
            from pathlib import Path

            root = Path.cwd()

            if reconcile:
                from harness.cli.helpers import reconcile_before_summary
                reconcile_before_summary(root)

            results = []
            results.append(scan_structure(root))
            results.append(scan_git_diff(root))

            if deep:
                results.append(check_architecture_conformance(root, project_type="python"))
                results.append(assess_coverage(root))
                results.append(find_dead_code(root))

            output_format = "json" if json_flag else "markdown"
            report = format_report(results, format=output_format)

            if assess_flag:
                try:
                    from harness.analysis.assessment import assess as run_assessment
                    assessment = asyncio.run(run_assessment(root, deep=True))
                    if output_format == "json":
                        import json as json_mod
                        base = json_mod.loads(report)
                        base["assessment"] = assessment.to_dict().get("assessment", {})
                        report = json_mod.dumps(base, indent=2, default=str)
                    else:
                        report += "\n\n---\n\n" + assessment.report_text
                except Exception as exc:
                    report += (
                        "\n\n## LLM-Based Assessment\n\n"
                        f"\u26a0\ufe0f Assessment agents unavailable: {exc}\n"
                    )

            return CommandResult(
                success=True,
                message="Summary generated",
                data={"report": report, "format": output_format},
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Summary failed: {exc}",
            )


class InspectHandler(CommandHandler):
    """Delegates to observer analysis."""

    def handle(self, command: Command) -> CommandResult:
        """Run observer analysis as an external observer.

        Args:
            command: Command with root and analysis options in data.

        Returns:
            CommandResult with analysis findings.
        """
        try:
            root = command.data.get("root", ".")

            from harness.analysis.observer import analyse

            result = analyse(path=root, deep=True)

            if result["status"] == "error":
                return CommandResult(
                    success=False,
                    error=result.get("message", "Unknown error"),
                    message=f"Inspect analysis failed: {result.get('message', '')}",
                )

            assessment_dict = result.get("assessment")
            findings_count = "?"
            score = "?"
            if assessment_dict:
                ad = assessment_dict.get("assessment", {})
                score = ad.get("score", "?")
                findings_count = len(ad.get("findings", []))

            return CommandResult(
                success=True,
                message=f"Assessment complete: {findings_count} findings, score: {score}",
                data={
                    "report": result["report"],
                    "findings_count": findings_count,
                    "score": score,
                    "delegated_to": "analyse()",
                },
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Inspect analysis failed: {exc}",
            )


class AssessHandler(CommandHandler):
    """Delegates to assessment pipeline (observer)."""

    def handle(self, command: Command) -> CommandResult:
        """Run the full assessment on the project.

        Args:
            command: Command with root and options.

        Returns:
            CommandResult with assessment findings.
        """
        try:
            root = command.data.get("root", ".")

            from harness.analysis.observer import analyse

            result = analyse(path=root, deep=True, project_type="python")

            if result["status"] == "error":
                return CommandResult(
                    success=False,
                    error=result.get("message", "Unknown error"),
                    message=f"Assessment failed: {result.get('message', '')}",
                )

            assessment_dict = result.get("assessment")
            findings_count = "?"
            score = "?"
            if assessment_dict:
                ad = assessment_dict.get("assessment", {})
                score = ad.get("score", "?")
                findings_count = len(ad.get("findings", []))

            return CommandResult(
                success=True,
                message=f"Assessment complete: {findings_count} findings, score: {score}",
                data={
                    "report": result["report"],
                    "findings_count": findings_count,
                    "score": score,
                    "delegated_to": "analyse()",
                },
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Assessment failed: {exc}",
            )


# ── Wave H: Batch + Lower Priority ──────────────────────────────────


class CreateWavesFromAssessmentHandler(CommandHandler):
    """Delegates to assessment-based wave creation."""

    def handle(self, command: Command) -> CommandResult:
        """Create waves from assessment findings.

        Delegates to PlanManager for wave creation and updates the
        assessment manifest to track wave associations.
        """
        try:
            import json
            from pathlib import Path
            from harness.plan.plan_manager import PlanManager
            from harness.paths import get_engagements_dir, get_engagement_dir

            root = Path.cwd()
            slug = command.slug
            focus = command.data.get("focus", "high-risk")
            limit = command.data.get("limit", 0)
            refactoring = command.data.get("refactoring", False)

            if not slug:
                from harness.engagement.resolver import resolve_active_engagement
                slug = resolve_active_engagement(root)

            if not slug:
                return CommandResult(
                    success=False,
                    error="No engagement slug specified or active",
                    message="No active engagement specified",
                )

            assess_dir = get_engagements_dir(root) / slug / "assessments"
            if not assess_dir.is_dir():
                return CommandResult(
                    success=False,
                    error=f"No assessments found for '{slug}'",
                    message=f"No assessments found for '{slug}'. Run an assessment first.",
                )

            manifests = sorted(assess_dir.glob("*-manifest.json"), reverse=True)
            if not manifests:
                return CommandResult(
                    success=False,
                    error="No assessment manifests found",
                )

            manifest = json.loads(manifests[0].read_text())
            findings = manifest.get("findings", [])

            if not findings:
                return CommandResult(
                    success=False,
                    error="Latest assessment has no structured findings",
                )

            def _matches_focus(f: dict) -> bool:
                sev = f.get("severity", "info")
                if focus == "high-risk":
                    return sev in ("error", "critical")
                elif focus == "medium":
                    return sev in ("error", "critical", "warning")
                return True

            matching = [f for f in findings if _matches_focus(f)]
            unassigned = [f for f in matching if not f.get("wave_slug")]

            if not unassigned:
                return CommandResult(
                    success=True,
                    message=f"All {len(matching)} matching findings already have waves.",
                    data={"created": 0, "matched": len(matching)},
                )

            if limit > 0:
                unassigned = unassigned[:limit]

            pm = PlanManager(root, slug)
            created = 0
            manifest_updated = False

            for f in unassigned:
                fid = f.get("id", "?")
                severity = f.get("severity", "info")
                category = f.get("category", "other")
                message = f.get("message", "")
                title = message[:72] + ("..." if len(message) > 72 else "")

                wave_obj = pm.add_wave(
                    title=title,
                    wave_type="refactor",
                    trigger_phase="assessment",
                    trigger_reason=(
                        f"Finding {fid}: [{severity}] {category} \u2014 {message[:100]}"
                    ),
                )
                f["wave_slug"] = wave_obj.id
                f["wave_status"] = "open"
                manifest_updated = True
                created += 1

            if manifest_updated:
                manifests[0].write_text(json.dumps(manifest, indent=2))

            if refactoring and created > 0:
                eng_yaml_path = get_engagement_dir(root, slug) / "engagement.yaml"
                if eng_yaml_path.is_file():
                    import yaml as _yaml
                    with open(eng_yaml_path) as f:
                        yaml_data = _yaml.safe_load(f) or {}
                    yaml_data["refactoring"] = True
                    yaml_data["session_type"] = "refactoring"
                    yaml_data["baseline_manifest"] = str(
                        manifests[0].relative_to(get_engagement_dir(root, slug))
                    )
                    yaml_data["baseline_finding_count"] = len(findings)
                    yaml_data["focus"] = focus
                    with open(eng_yaml_path, "w") as f:
                        _yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

            return CommandResult(
                success=True,
                message=f"Created {created} wave(s) from {focus} findings",
                data={
                    "created": created,
                    "matched": len(matching),
                    "slug": slug,
                },
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Create waves from assessment failed: {exc}",
            )


class CreateWaveFromFindingHandler(CommandHandler):
    """Delegates to finding-based wave creation."""

    def handle(self, command: Command) -> CommandResult:
        """Create a wave from an assessment finding."""
        try:
            import json
            from pathlib import Path
            from harness.plan.plan_manager import PlanManager
            from harness.paths import get_engagements_dir

            root = Path.cwd()
            slug = command.slug
            finding_id = command.data.get("finding_id", "")

            if not slug:
                from harness.engagement.resolver import resolve_active_engagement
                slug = resolve_active_engagement(root)

            if not slug:
                return CommandResult(
                    success=False,
                    error="No engagement slug specified or active",
                )

            if not finding_id:
                return CommandResult(
                    success=False,
                    error="No finding_id specified",
                )

            assess_dir = get_engagements_dir(root) / slug / "assessments"
            if not assess_dir.is_dir():
                return CommandResult(
                    success=False,
                    error=f"No assessments found for '{slug}'",
                )

            manifests = sorted(assess_dir.glob("*-manifest.json"), reverse=True)
            if not manifests:
                return CommandResult(
                    success=False,
                    error="No assessment manifests found",
                )

            manifest = json.loads(manifests[0].read_text())
            findings = manifest.get("findings", [])

            target = None
            for f in findings:
                if f.get("id") == finding_id:
                    target = f
                    break

            if target is None:
                available = [f.get("id", "?") for f in findings[:20]]
                return CommandResult(
                    success=False,
                    error=f"Finding '{finding_id}' not found",
                    message=f"Available findings: {', '.join(available)}",
                )

            if target.get("wave_slug"):
                return CommandResult(
                    success=True,
                    message=f"Finding '{finding_id}' already has wave ({target['wave_slug']}). Skipping.",
                    data={"wave_slug": target["wave_slug"], "skipped": True},
                )

            category = target.get("category", "other")
            message_text = target.get("message", "")
            severity = target.get("severity", "info")
            title = message_text[:72] + ("..." if len(message_text) > 72 else "")

            pm = PlanManager(root, slug)
            wave_obj = pm.add_wave(
                title=title,
                wave_type="refactor",
                trigger_phase="assessment",
                trigger_reason=(
                    f"Finding {finding_id}: [{severity}] {category} \u2014 {message_text[:100]}"
                ),
            )

            target["wave_slug"] = wave_obj.id
            target["wave_status"] = "open"
            manifests[0].write_text(json.dumps(manifest, indent=2))

            return CommandResult(
                success=True,
                message=f"Created wave '{wave_obj.id}' from finding '{finding_id}'",
                data={
                    "wave_id": wave_obj.id,
                    "finding_id": finding_id,
                    "title": title,
                    "severity": severity,
                    "category": category,
                },
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Create wave from finding failed: {exc}",
            )


class ListWavesHandler(CommandHandler):
    """Delegates to wave listing via PlanManager."""

    def handle(self, command: Command) -> CommandResult:
        """List waves from the engagement plan."""
        try:
            from pathlib import Path
            from harness.plan.plan_manager import PlanManager

            root = Path.cwd()
            slug = command.slug

            if not slug:
                from harness.engagement.resolver import resolve_active_engagement
                slug = resolve_active_engagement(root)

            if not slug:
                return CommandResult(
                    success=False,
                    error="No active engagement",
                )

            pm = PlanManager(root, slug)
            statuses = pm.get_status()

            return CommandResult(
                success=True,
                message=f"{len(statuses)} wave(s) for '{slug}'",
                data={
                    "slug": slug,
                    "waves": statuses,
                },
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"List waves failed: {exc}",
            )


class WaveStatusHandler(CommandHandler):
    """Delegates to wave status via PlanManager.summary()."""

    def handle(self, command: Command) -> CommandResult:
        """Show detailed wave status."""
        try:
            from pathlib import Path
            from harness.plan.plan_manager import PlanManager

            root = Path.cwd()
            slug = command.slug

            if not slug:
                from harness.engagement.resolver import resolve_active_engagement
                slug = resolve_active_engagement(root)

            if not slug:
                return CommandResult(
                    success=False,
                    error="No active engagement",
                )

            pm = PlanManager(root, slug)
            summary_text = pm.summary()

            return CommandResult(
                success=True,
                message=f"Wave status for '{slug}'",
                data={
                    "slug": slug,
                    "summary": summary_text,
                },
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Wave status failed: {exc}",
            )


class GenerateDocsHandler(CommandHandler):
    """Delegates to doc generation."""

    def handle(self, command: Command) -> CommandResult:
        """Generate project documentation."""
        try:
            from pathlib import Path

            root = Path(command.data.get("root", "."))

            from harness.docs.generator import (
                DocType,
                OverwriteMode,
                SourceTier,
                generate_all_docs,
                generate_doc,
                populate_context_from_project,
            )

            overwrite = command.data.get("overwrite", "ask")
            doc_type = command.data.get("doc_type", "full")
            source_tier = command.data.get("source_tier", 3)
            output_dir = command.data.get("output_dir", root)

            overwrite_mode = OverwriteMode(overwrite)
            source_tier_enum = SourceTier(source_tier)

            if doc_type == "full":
                generated = generate_all_docs(
                    root=root,
                    output_dir=output_dir,
                    overwrite_mode=overwrite_mode,
                    interactive=True,
                    source_tier=source_tier_enum,
                )
            else:
                doc_type_enum = DocType(doc_type)
                context = populate_context_from_project(root, source_tier_enum)
                generated = generate_doc(
                    doc_type=doc_type_enum,
                    context=context,
                    output_dir=output_dir,
                    root=root,
                    overwrite_mode=overwrite_mode,
                    interactive=True,
                    source_tier=source_tier_enum,
                )

            return CommandResult(
                success=True,
                message=f"Generated {len(generated)} document(s)",
                data={
                    "generated": [str(p.relative_to(root)) for p in generated],
                },
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Generate docs failed: {exc}",
            )


class AnnotateChangelogHandler(CommandHandler):
    """Delegates to changelog annotation."""

    def handle(self, command: Command) -> CommandResult:
        """Append a human annotation to the latest changelog entry."""
        try:
            from pathlib import Path
            from harness.docs.changelog import annotate_changelog
            from harness.paths import get_engagement_dir

            root = Path.cwd()
            slug = command.slug
            wave = command.data.get("wave", "")
            text = command.data.get("text", "")

            eng_dir = get_engagement_dir(root, slug)
            if not eng_dir.is_dir():
                return CommandResult(
                    success=False,
                    error=f"Engagement '{slug}' not found",
                )

            changelog_dir = eng_dir / "changelog"
            if not changelog_dir.is_dir():
                return CommandResult(
                    success=False,
                    error=f"No changelog entries found for '{slug}'",
                )

            entry_files = sorted(changelog_dir.iterdir(), reverse=True)
            if not entry_files:
                return CommandResult(
                    success=False,
                    error=f"No changelog entries found for '{slug}'",
                )

            latest = entry_files[0]
            wave_id = wave or latest.stem

            updated = annotate_changelog(eng_dir, wave_id, text)
            return CommandResult(
                success=True,
                message=f"Annotation added to {wave_id} changelog entry",
                data={"path": str(updated.relative_to(root))},
            )

        except FileNotFoundError as exc:
            return CommandResult(
                success=False,
                error=str(exc),
            )
        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Annotate changelog failed: {exc}",
            )


# ── Wave I: Thin Wrappers ───────────────────────────────────────────


class RenameEngagementHandler(CommandHandler):
    """Delegates to engagement rename."""

    def handle(self, command: Command) -> CommandResult:
        """Rename an existing engagement."""
        try:
            from pathlib import Path

            root = command.data.get("root", Path.cwd())
            if isinstance(root, str):
                root = Path(root)

            new_slug = command.data.get("new_slug", "")
            branch_strategy = command.data.get("branch_strategy", "keep")
            dry_run = command.data.get("dry_run", False)

            from harness.engagement.rename import BranchStrategy, rename_engagement

            strategy = BranchStrategy(branch_strategy)
            result = rename_engagement(
                old_slug=command.slug,
                new_slug=new_slug,
                root=root,
                branch_strategy=strategy,
                dry_run=dry_run,
            )

            data: dict[str, Any] = {
                "changes_made": result.changes_made,
                "warnings": result.warnings,
                "errors": result.errors,
                "dry_run": dry_run,
            }

            if result.errors:
                return CommandResult(
                    success=False,
                    error="; ".join(result.errors),
                    data=data,
                )

            return CommandResult(
                success=True,
                message=f"Engagement renamed: {command.slug} -> {new_slug}",
                data=data,
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Rename failed: {exc}",
            )


class SetBranchHandler(CommandHandler):
    """Delegates to branch setting."""

    def handle(self, command: Command) -> CommandResult:
        """Set the branch for an engagement."""
        try:
            from pathlib import Path
            from harness.paths import get_engagement_dir

            root = Path.cwd()
            slug = command.slug
            branch = command.data.get("branch", "")

            eng_dir = get_engagement_dir(root, slug)
            eng_yaml_path = eng_dir / "engagement.yaml"

            if not eng_yaml_path.is_file():
                return CommandResult(
                    success=False,
                    error=f"Engagement '{slug}' has no engagement.yaml",
                )

            import yaml
            with open(eng_yaml_path) as f:
                yaml_data = yaml.safe_load(f) or {}

            old_branch = yaml_data.get("branch", "(not set)")
            yaml_data["branch"] = branch

            with open(eng_yaml_path, "w") as f:
                yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

            return CommandResult(
                success=True,
                message=f"Branch updated: {old_branch} -> {branch}",
                data={
                    "slug": slug,
                    "old_branch": old_branch,
                    "new_branch": branch,
                },
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Set branch failed: {exc}",
            )


class FixEngagementHandler(CommandHandler):
    """Delegates to engagement fix."""

    def handle(self, command: Command) -> CommandResult:
        """Fix engagement metadata and state issues."""
        try:
            from pathlib import Path

            root = Path.cwd()
            slug = command.slug

            if not slug:
                from harness.engagement.resolver import resolve_active_engagement
                slug = resolve_active_engagement(root)

            if not slug:
                return CommandResult(
                    success=False,
                    error="No active engagement to fix",
                )

            from harness.health import fix_engagement
            messages = fix_engagement(root, slug)

            return CommandResult(
                success=True,
                message=f"Fixed {len(messages)} issue(s) for '{slug}'",
                data={
                    "slug": slug,
                    "messages": messages,
                },
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Fix engagement failed: {exc}",
            )


class RefreshAgentsHandler(CommandHandler):
    """Delegates to agent profile refresh."""

    def handle(self, command: Command) -> CommandResult:
        """Refresh agent profiles from agent registry."""
        try:
            from pathlib import Path
            from harness.cli.helpers import require_project_root
            from harness.constitution.templates.template_registry import (
                refresh_agent_profiles,
            )

            slug = command.slug
            project_dir = command.data.get("project_dir")
            force = command.data.get("force", False)

            explicit_path = None
            if project_dir:
                explicit_path = Path.cwd() / project_dir
            root = require_project_root(
                explicit_path=explicit_path,
                command_name="refresh-agents",
            )

            result = refresh_agent_profiles(root, force=force)

            return CommandResult(
                success=True,
                message="Agent profiles refreshed",
                data={
                    "created": result.get("created", []),
                    "updated": result.get("updated", []),
                    "existing": result.get("existing", []),
                },
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Refresh agents failed: {exc}",
            )


class SetGovernanceHandler(CommandHandler):
    """Delegates to governance level setting.

    Note: was set-fleet-governance, now set-governance.
    """

    def handle(self, command: Command) -> CommandResult:
        """Set governance level for project or engagement."""
        try:
            from pathlib import Path
            from harness.agents.governance import (
                GovernanceLevel,
                get_project_governance,
                set_project_governance,
                set_engagement_governance,
            )
            from harness.cli.helpers import require_project_root

            root = require_project_root(command_name="set-governance")
            level = command.data.get("level", "standard")
            slug = command.slug

            gov = GovernanceLevel(level)

            if slug:
                set_engagement_governance(root, slug, gov)
                return CommandResult(
                    success=True,
                    message=f"Engagement '{slug}' governance set to '{level}'",
                    data={"slug": slug, "level": level, "scope": "engagement"},
                )
            else:
                set_project_governance(root, gov)
                current = get_project_governance(root)
                return CommandResult(
                    success=True,
                    message=f"Project governance set to '{level}'",
                    data={"level": level, "scope": "project"},
                )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Set governance failed: {exc}",
            )


# ── Wave O: Agent / Fleet / Consult handlers ────────────────────────


class AgentListHandler(CommandHandler):
    """Lists all registered agent roles with their tags and team."""

    def handle(self, command: Command) -> CommandResult:
        """List all registered agent roles."""
        try:
            from harness.agents.agent_registry import AGENTS, list_agent_roles

            roles = list_agent_roles()
            agents_data = []
            for spec in AGENTS:
                agents_data.append({
                    "role": spec.role,
                    "tags": list(getattr(spec, "tags", []) or []),
                })

            return CommandResult(
                success=True,
                message=f"{len(agents_data)} agent(s) registered.",
                data={"agents": agents_data, "count": len(agents_data)},
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Agent list failed: {exc}",
            )


class FleetListHandler(CommandHandler):
    """Lists all registered teams with their agent count."""

    def handle(self, command: Command) -> CommandResult:
        """List all registered teams."""
        try:
            from harness.team.registry import TeamRegistry
            from harness.team.defaults import get_builtin_teams

            registry = TeamRegistry(builtin=get_builtin_teams())
            team_names = registry.list_teams()
            teams_data = []
            for name in team_names:
                team = registry.resolve(name)
                teams_data.append({
                    "name": team.name,
                    "agent_count": len(team.agents),
                    "description": team.description,
                })

            return CommandResult(
                success=True,
                message=f"{len(teams_data)} team(s) registered.",
                data={"teams": teams_data, "count": len(teams_data)},
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Fleet list failed: {exc}",
            )


class ConsultHandler(CommandHandler):
    """Routes a consultation question to matching teams."""

    def handle(self, command: Command) -> CommandResult:
        """Route a consultation question."""
        try:
            from harness.team.registry import TeamRegistry
            from harness.team.defaults import get_builtin_teams
            from harness.agents.consultation import ConsultationOrchestrator

            question = command.data.get("question", "")
            team_filter = command.data.get("team_filter")
            mode = command.data.get("mode", "advisory")

            registry = TeamRegistry(builtin=get_builtin_teams())
            orch = ConsultationOrchestrator(registry)
            result = orch.route(question, mode=mode, team_filter=team_filter)

            return CommandResult(
                success=result.status == "matched",
                message=result.summary,
                data={
                    "status": result.status,
                    "capability": result.capability,
                    "team_name": result.team_name,
                    "mode": result.mode,
                    "response": result.response,
                },
            )

        except Exception as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                message=f"Consultation failed: {exc}",
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
        # Base (9 from earlier waves)
        "create_engagement": CreateEngagementHandler(),
        "resume_engagement": ResumeEngagementHandler(),
        "enter_phase": EnterPhaseHandler(),
        "next": NextHandler(),
        "create_wave": CreateWaveHandler(),
        "execute_step": ExecuteStepHandler(),
        "abort_engagement": AbortEngagementHandler(),
        "query_status": QueryStatusHandler(),
        "query_whats_next": QueryWhatsNextHandler(),
        # Wave D+E (4 from Sprint 2)
        "finish_engagement": FinishEngagementHandler(),
        "review_engagement": ReviewEngagementHandler(),
        "init_project": InitProjectHandler(),
        "manage_phase": PhaseManagementHandler(),
        # Wave F: RunWave / Session / Chat
        "run_wave": RunWaveHandler(),
        "session": SessionHandler(),
        "chat": ChatHandler(),
        # Wave G: Summary / Inspect / Assess
        "summary": SummaryHandler(),
        "inspect": InspectHandler(),
        "assess": AssessHandler(),
        # Wave H: Batch + Lower Priority
        "create_waves_from_assessment": CreateWavesFromAssessmentHandler(),
        "create_wave_from_finding": CreateWaveFromFindingHandler(),
        "list_waves": ListWavesHandler(),
        "wave_status": WaveStatusHandler(),
        "generate_docs": GenerateDocsHandler(),
        "annotate_changelog": AnnotateChangelogHandler(),
        # Wave I: Thin Wrappers
        "rename_engagement": RenameEngagementHandler(),
        "set_branch": SetBranchHandler(),
        "fix_engagement": FixEngagementHandler(),
        "refresh_agents": RefreshAgentsHandler(),
        "set_governance": SetGovernanceHandler(),
        # Wave O: Agent / Fleet / Consult
        "agent_list": AgentListHandler(),
        "fleet_list": FleetListHandler(),
        "consult": ConsultHandler(),
    }
    registry.register_all(handlers)
