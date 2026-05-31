"""Typed handlers for batch and lower priority wave operations.

Covers: CreateWavesFromAssessmentHandler, CreateWaveFromFindingHandler,
ListWavesHandler, WaveStatusHandler, GenerateDocsHandler, AnnotateChangelogHandler.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness.command.types import TypedHandler
from harness.command.commands.batch import (
    AnnotateChangelogCommand,
    CreateWaveFromFindingCommand,
    CreateWavesFromAssessmentCommand,
    GenerateDocsCommand,
    ListWavesCommand,
    WaveStatusCommand,
)
from harness.command.results.batch import (
    AnnotateChangelogResult,
    CreateWaveFromFindingResult,
    CreateWavesFromAssessmentResult,
    GenerateDocsResult,
    ListWavesResult,
    WaveStatusResult,
)


class CreateWavesFromAssessmentTypedHandler(
    TypedHandler[CreateWavesFromAssessmentCommand, CreateWavesFromAssessmentResult]
):
    """Create waves from assessment findings."""

    def handle(self, command: CreateWavesFromAssessmentCommand) -> CreateWavesFromAssessmentResult:
        try:
            from harness.plan.plan_manager import PlanManager
            from harness.paths import get_engagements_dir, get_engagement_dir

            root = Path.cwd()
            slug = command.slug
            focus = command.focus
            limit = command.limit
            refactoring = command.refactoring

            if not slug:
                from harness.domain.engagement.resolver import resolve_active_engagement
                slug = resolve_active_engagement(root)

            if not slug:
                return CreateWavesFromAssessmentResult(
                    success=False,
                    error="No engagement slug specified or active",
                )

            assess_dir = get_engagements_dir(root) / slug / "assessments"
            if not assess_dir.is_dir():
                return CreateWavesFromAssessmentResult(
                    success=False,
                    error=f"No assessments found for '{slug}'",
                )

            manifests = sorted(assess_dir.glob("*-manifest.json"), reverse=True)
            if not manifests:
                return CreateWavesFromAssessmentResult(
                    success=False,
                    error="No assessment manifests found",
                )

            manifest = json.loads(manifests[0].read_text())
            findings = manifest.get("findings", [])

            if not findings:
                return CreateWavesFromAssessmentResult(
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
                return CreateWavesFromAssessmentResult(
                    success=True,
                    message=f"All {len(matching)} matching findings already have waves.",
                    created=0,
                    matched=len(matching),
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

            return CreateWavesFromAssessmentResult(
                success=True,
                message=f"Created {created} wave(s) from {focus} findings",
                created=created,
                matched=len(matching),
                slug=slug,
            )

        except Exception as exc:
            return CreateWavesFromAssessmentResult(
                success=False,
                error=str(exc),
                message=f"Create waves from assessment failed: {exc}",
            )


class CreateWaveFromFindingTypedHandler(
    TypedHandler[CreateWaveFromFindingCommand, CreateWaveFromFindingResult]
):
    """Create a wave from an assessment finding."""

    def handle(self, command: CreateWaveFromFindingCommand) -> CreateWaveFromFindingResult:
        try:
            from pathlib import Path
            from harness.plan.plan_manager import PlanManager
            from harness.paths import get_engagements_dir

            root = Path.cwd()
            slug = command.slug
            finding_id = command.finding_id

            if not slug:
                from harness.domain.engagement.resolver import resolve_active_engagement
                slug = resolve_active_engagement(root)

            if not slug:
                return CreateWaveFromFindingResult(
                    success=False,
                    error="No engagement slug specified or active",
                )

            if not finding_id:
                return CreateWaveFromFindingResult(
                    success=False,
                    error="No finding_id specified",
                )

            assess_dir = get_engagements_dir(root) / slug / "assessments"
            if not assess_dir.is_dir():
                return CreateWaveFromFindingResult(
                    success=False,
                    error=f"No assessments found for '{slug}'",
                )

            manifests = sorted(assess_dir.glob("*-manifest.json"), reverse=True)
            if not manifests:
                return CreateWaveFromFindingResult(
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
                return CreateWaveFromFindingResult(
                    success=False,
                    error=f"Finding '{finding_id}' not found",
                    message=f"Available findings: {', '.join(available)}",
                )

            if target.get("wave_slug"):
                return CreateWaveFromFindingResult(
                    success=True,
                    message=f"Finding '{finding_id}' already has wave ({target['wave_slug']}). Skipping.",
                    wave_id=target["wave_slug"],
                    skipped=True,
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

            return CreateWaveFromFindingResult(
                success=True,
                message=f"Created wave '{wave_obj.id}' from finding '{finding_id}'",
                wave_id=wave_obj.id,
                finding_id=finding_id,
                title=title,
                severity=severity,
                category=category,
            )

        except Exception as exc:
            return CreateWaveFromFindingResult(
                success=False,
                error=str(exc),
                message=f"Create wave from finding failed: {exc}",
            )


class ListWavesTypedHandler(TypedHandler[ListWavesCommand, ListWavesResult]):
    """List waves from the engagement plan."""

    def handle(self, command: ListWavesCommand) -> ListWavesResult:
        try:
            from pathlib import Path
            from harness.plan.plan_manager import PlanManager

            root = Path.cwd()
            slug = command.slug

            if not slug:
                from harness.domain.engagement.resolver import resolve_active_engagement
                slug = resolve_active_engagement(root)

            if not slug:
                return ListWavesResult(
                    success=False,
                    error="No active engagement",
                )

            pm = PlanManager(root, slug)
            statuses = pm.get_status()

            return ListWavesResult(
                success=True,
                message=f"{len(statuses)} wave(s) for '{slug}'",
                slug=slug,
                waves=statuses,
            )

        except Exception as exc:
            return ListWavesResult(
                success=False,
                error=str(exc),
                message=f"List waves failed: {exc}",
            )


class WaveStatusTypedHandler(TypedHandler[WaveStatusCommand, WaveStatusResult]):
    """Show detailed wave status."""

    def handle(self, command: WaveStatusCommand) -> WaveStatusResult:
        try:
            from pathlib import Path
            from harness.plan.plan_manager import PlanManager

            root = Path.cwd()
            slug = command.slug

            if not slug:
                from harness.domain.engagement.resolver import resolve_active_engagement
                slug = resolve_active_engagement(root)

            if not slug:
                return WaveStatusResult(
                    success=False,
                    error="No active engagement",
                )

            pm = PlanManager(root, slug)
            summary_text = pm.summary()

            return WaveStatusResult(
                success=True,
                message=f"Wave status for '{slug}'",
                slug=slug,
                summary=summary_text,
            )

        except Exception as exc:
            return WaveStatusResult(
                success=False,
                error=str(exc),
                message=f"Wave status failed: {exc}",
            )


class GenerateDocsTypedHandler(TypedHandler[GenerateDocsCommand, GenerateDocsResult]):
    """Generate project documentation."""

    def handle(self, command: GenerateDocsCommand) -> GenerateDocsResult:
        try:
            from pathlib import Path

            root = Path(command.root)

            from harness.docs.generator import (
                DocType,
                OverwriteMode,
                SourceTier,
                generate_all_docs,
                generate_doc,
                populate_context_from_project,
            )

            overwrite = command.overwrite
            doc_type = command.doc_type
            source_tier = command.source_tier
            output_dir = Path(command.output_dir) if command.output_dir else root

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

            return GenerateDocsResult(
                success=True,
                message=f"Generated {len(generated)} document(s)",
                generated=[str(p.relative_to(root)) for p in generated],
            )

        except Exception as exc:
            return GenerateDocsResult(
                success=False,
                error=str(exc),
                message=f"Generate docs failed: {exc}",
            )


class AnnotateChangelogTypedHandler(
    TypedHandler[AnnotateChangelogCommand, AnnotateChangelogResult]
):
    """Append a human annotation to the latest changelog entry."""

    def handle(self, command: AnnotateChangelogCommand) -> AnnotateChangelogResult:
        try:
            from pathlib import Path
            from harness.docs.changelog import annotate_changelog
            from harness.paths import get_engagement_dir

            root = Path.cwd()
            slug = command.slug
            wave = command.wave
            text = command.text

            eng_dir = get_engagement_dir(root, slug)
            if not eng_dir.is_dir():
                return AnnotateChangelogResult(
                    success=False,
                    error=f"Engagement '{slug}' not found",
                )

            changelog_dir = eng_dir / "changelog"
            if not changelog_dir.is_dir():
                return AnnotateChangelogResult(
                    success=False,
                    error=f"No changelog entries found for '{slug}'",
                )

            entry_files = sorted(changelog_dir.iterdir(), reverse=True)
            if not entry_files:
                return AnnotateChangelogResult(
                    success=False,
                    error=f"No changelog entries found for '{slug}'",
                )

            latest = entry_files[0]
            wave_id = wave or latest.stem

            updated = annotate_changelog(eng_dir, wave_id, text)
            return AnnotateChangelogResult(
                success=True,
                message=f"Annotation added to {wave_id} changelog entry",
                path=str(updated.relative_to(root)),
            )

        except FileNotFoundError as exc:
            return AnnotateChangelogResult(
                success=False,
                error=str(exc),
            )
        except Exception as exc:
            return AnnotateChangelogResult(
                success=False,
                error=str(exc),
                message=f"Annotate changelog failed: {exc}",
            )
