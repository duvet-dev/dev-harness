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
