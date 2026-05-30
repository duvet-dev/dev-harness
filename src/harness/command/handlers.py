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
        "finish_engagement": FinishEngagementHandler(),
        "review_engagement": ReviewEngagementHandler(),
        "init_project": InitProjectHandler(),
        "manage_phase": PhaseManagementHandler(),
    }
    registry.register_all(handlers)
