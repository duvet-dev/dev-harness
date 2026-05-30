"""CLI helper functions ported from the legacy monolithic cli.py.

Contains utility functions and constants used by CLI commands.
These were extracted from ``cli.py`` (3,908 lines → deleted) and
placed here as part of the Phase 1 package migration.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from harness.state.snapshot import ProjectSnapshot

from harness.paths import (
    find_project_root as _py_find_project_root,
)
from harness.paths import (
    resolve_explicit_project_root as _py_resolve_explicit_project_root,
)
from harness.paths import (
    resolve_project_root as _py_resolve_project_root,
)


# ── Project Root Discovery ──────────────────────────────────────────────


def find_project_root(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from *start* (default: CWD) to find the nearest
    directory containing a ``.harness/`` folder.

    Returns the first ancestor with ``.harness/``, or ``None`` if no
    project root is found (the walk stops at filesystem root).

    This is the canonical way to locate a harness project — it works
    regardless of which subdirectory the user runs the tool from.
    """
    return _py_find_project_root(start)


def require_project_root(
    explicit_path: Optional[str] = None,
    command_name: str = "this command",
) -> Path:
    """Resolve the project root given an optional explicit path.

    Raises ``click.Abort`` if no project root is found.
    """
    if explicit_path is not None:
        try:
            return _py_resolve_explicit_project_root(
                Path(explicit_path).resolve(), command_name=command_name
            )
        except SystemExit:
            import click
            raise click.Abort()

    try:
        return _py_resolve_project_root(command_name=command_name)
    except SystemExit:
        import click
        raise click.Abort()


# ── Formatting Constants ────────────────────────────────────────────────


def bold(text: str) -> str:
    """Wrap *text* in ANSI bold escape codes when stdout is a terminal."""
    if sys.stdout.isatty():
        return f"\x1b[1m{text}\x1b[0m"
    return text


WORKFLOWS_EPILOG = """

{hr}

{getting_started}
  init          Create a new harness project (or add harness to an existing one).
                Use this once per project to set up the constitution, agents, and
                git scaffolding.

{engagement_lifecycle}
  work          Start a full engagement with auto-pilot mode. Harness runs all phases
                (requirements → understanding → design → build → review) autonomously
                with optional gate reviews. Best for: well-understood tasks where you
                want end-to-end execution with minimal interaction.

  session       Run a phase-by-phase interactive session. You control when to advance,
                approve, or request changes. Best for: exploratory work, when you want
                to guide each phase individually and review outputs as they're produced.

  chat          Open an interactive LLM chat within an engagement. Simpler than session
                — just you and an agent talking, no phase structure. Best for: quick
                questions, research, brainstorming within an existing engagement.

  agent run     Run a single harness agent by name for a specific task. Best for:
                targeted work like "write tests for this module" or "review this file"
                without starting a full engagement.

{engagement_mgmt}
  engagement    Sub-commands to create, list, set active, and close engagements.
                Use before any engagement-based workflow (work, session, chat) to
                set up the engagement container.

  review        Review work at a gate checkpoint. Approve, reject, or request changes
                on a phase. Best for: manual gate reviews in auto-pilot mode.

  phase         List phases or advance to the next one. Use to navigate an engagement
                when not using the interactive session flow.

  finish        Complete the current engagement with a final commit. Call this when
                all phases are done and you want to seal the engagement.

  status        Quick view of the active engagement. See current phase, agent, status.

{analysis}
  summary       Deep project status with phase-by-phase breakdown. Shows artifacts,
                findings, and overall progress. Use when you need a comprehensive
                picture of where the project stands.

  inspect       Analyse any codebase without harness initialisation. Point at any
                directory and get fast structure, conformance, and health metrics.
                Use --deep to run the full LLM-based analysis. Best for: CI pipelines,
                pre-review checks, or evaluating an external project.

  assess        Run the full assessment on the current project. Produces structured
                findings for use in engagement planning and refactoring. Best for:
                establishing baselines and driving self-improvement workflows.

{state_mgmt}
  catchup       Reconcile harness state with current git state. Run this if you've
                made changes outside the harness (e.g. manual commits) and need
                harness to catch up.

  absorb        Detect and absorb external changes (manual file edits, reviewer
                feedback, etc.) into the harness state. Best for: incorporating
                feedback or changes made outside the structured workflow.

{infrastructure}
  refresh-agents  Sync local agent definitions with the harness's current registry.
                  Updates ``agents/<role>/identity.md`` and ``procedures.md``
                  without touching engagement state.

{tips}
  \u2022 Start with ``harness init`` to set up your project.
  \u2022 Use ``harness engagement create <name>`` to create an engagement.
  \u2022 For guided end-to-end work: ``harness session`` or ``harness work``.
  \u2022 For quick questions: ``harness chat`` within an engagement.
  \u2022 For code analysis: ``harness observe`` (no engagement needed).
  \u2022 For a full list of options per command: ``harness <command> --help``.
""".format(
    hr=bold("\u2501" * 60),
    getting_started=bold("Getting Started"),
    engagement_lifecycle=bold(
        "Engagement Lifecycle \u2014 plan, track, and execute development work"
    ),
    engagement_mgmt=bold("Engagement Management"),
    analysis=bold("Analysis & Reporting"),
    state_mgmt=bold("State Management"),
    infrastructure=bold("Infrastructure"),
    tips=bold("Tips"),
)


# ── Git Helpers ─────────────────────────────────────────────────────────


def init_git(path: Path) -> bool:
    """Run ``git init`` in *path*. Returns ``True`` on success."""
    try:
        result = subprocess.run(
            ["git", "init"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except subprocess.TimeoutExpired:
        import click
        click.echo("  Warning: git init timed out")
        return False


def initial_commit(path: Path) -> None:
    """Make an initial commit in *path* after scaffolding."""
    try:
        subprocess.run(
            ["git", "add", "."],
            cwd=path,
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial harness scaffold"],
            cwd=path,
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass


def get_head_sha(repo_root: Path) -> str:
    """Return the full SHA of HEAD."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


# ── Scaffold Helpers ────────────────────────────────────────────────────


def write_minimal_constitution(path: Path, project_name: str) -> None:
    """Write a minimal constitution.yaml when no template is chosen."""
    import yaml
    constitution = {
        "project": {
            "name": project_name,
            "template": "none",
            "description": "",
        },
        "gates": {"default_mode": "wild"},
        "agents": [],
    }
    path.write_text(
        yaml.dump(constitution, default_flow_style=False, sort_keys=False)
    )


def load_project_snapshot(path: Path) -> ProjectSnapshot:
    """Load or create a ProjectSnapshot from a YAML file."""
    from harness.state.snapshot import EngagementSnapshot, ProjectSnapshot

    import yaml
    if path.is_file():
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
        engagements = [
            EngagementSnapshot(**e) for e in raw.get("engagements", [])
        ]
        return ProjectSnapshot(
            project_name=raw.get("project_name", "unknown"),
            version=raw.get("version", "0.0.0"),
            current_engagement=raw.get("current_engagement"),
            engagements=engagements,
            last_updated=raw.get("last_updated", ""),
        )
    return ProjectSnapshot(
        project_name="unknown",
        version="0.0.0",
        current_engagement=None,
        engagements=[],
    )


# ── Session Type Resolution ─────────────────────────────────────────────


def resolve_session_type_flag(
    flag_value: Optional[str],
    root: Path,
    slug: Optional[str],
) -> Optional[str]:
    """Resolve the session type from CLI flag or engagement metadata.

    Returns the session type string ('greenfield', 'brownfield', 'refactoring')
    or ``None`` for auto-detection.
    """
    if flag_value:
        return flag_value
    # Try to read from engagement metadata
    if slug:
        try:
            from harness.paths import get_engagement_dir
            import yaml as _yaml
            _p = get_engagement_dir(root, slug) / "engagement.yaml"
            if _p.is_file():
                with open(_p) as _f:
                    _yd = _yaml.safe_load(_f) or {}
                st = _yd.get("session_type")
                if st:
                    return st
        except Exception:
            pass
    return None


# ── Assessment & Summary Helpers ────────────────────────────────────────


def write_assessment_report(
    report_text: str,
    repo_path: str,
    report_file=None,
    assessment_dict=None,
) -> str | None:
    """Write an assessment report, optionally to the engagement space.

    If inside a harness project with an active engagement, writes to:
        .harness/engagements/<slug>/assessments/<timestamp>-assessment.md

    Also writes to ``report_file`` if provided.

    Args:
        report_text: The full report text.
        repo_path: The analysed repository path.
        assessment_dict: Optional dict from ``AssessmentReport.to_dict()``
            containing findings, score, and recommendations. When provided,
            the manifest will include per-finding entries for later reference
            (e.g. by ``harness wave create-from-finding``).
        report_file: Optional explicit file path.

    Returns:
        The path the report was written to, or ``None``.
    """
    import json
    from datetime import datetime, timezone
    from harness.paths import get_harness_dir, get_engagements_dir
    from harness.engagement.lifecycle import read_active_engagement

    import click

    written_to: str | None = None
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d-%H%M%S")

    # Always write to explicit report file if provided
    if report_file:
        Path(report_file).parent.mkdir(parents=True, exist_ok=True)
        Path(report_file).write_text(report_text)
        written_to = report_file

    # If inside a harness project with an active engagement, write there too
    try:
        root = find_project_root(Path(repo_path)) if Path(repo_path).is_dir() else None
        if root:
            active = read_active_engagement(root)
            if active:
                slug = active.get("slug") if isinstance(active, dict) else str(active)
                if slug:
                    assess_dir = (
                        get_engagements_dir(root) / slug / "assessments"
                    )
                    assess_dir.mkdir(parents=True, exist_ok=True)

                    # Write report
                    report_path = assess_dir / f"{timestamp}-assessment.md"
                    report_path.write_text(report_text)

                    # Write structured findings (JSON manifest)
                    manifest = {
                        "timestamp": now.isoformat(),
                        "repository": str(Path(repo_path).resolve()),
                        "report_file": str(report_path),
                        "type": "full-assessment",
                    }

                    # Include findings from assessment if available
                    if assessment_dict:
                        assessment_data = assessment_dict.get("assessment", {})
                        raw_findings = assessment_data.get("findings", [])
                        manifest["score"] = assessment_data.get("score", "unknown")
                        manifest["finding_count"] = len(raw_findings)
                        manifest["recommendations"] = assessment_data.get(
                            "recommendations", []
                        )

                        # Add structured findings with unique IDs
                        manifest["findings"] = []
                        for idx, f in enumerate(raw_findings):
                            finding_id = f"finding-{idx+1:03d}"
                            manifest["findings"].append({
                                "id": finding_id,
                                "severity": f.get("severity", "info"),
                                "category": f.get("category", ""),
                                "message": f.get("message", ""),
                                "file": f.get("file", ""),
                                "wave_slug": None,
                                "wave_status": "unassigned",
                            })

                    manifest_path = assess_dir / f"{timestamp}-manifest.json"
                    manifest_path.write_text(json.dumps(manifest, indent=2))

                    written_to = str(report_path)
                    click.echo(f"\nAssessment saved to engagement: {slug}")

    except Exception:
        pass  # Non-critical — engagement space may not exist

    return written_to


def reconcile_before_summary(root: Path) -> None:
    """Reconcile freshness before running summary analysis."""
    try:
        from harness.scm.git import GitRepo
        from harness.state.freshness import (
            load_freshness,
            save_freshness,
        )
        from harness.state.reconciliation import BranchReconciler

        freshness = load_freshness(root)
        if freshness and not freshness.stale:
            repo = GitRepo(root)
            reconciler = BranchReconciler(repo, root)
            report = reconciler.reconcile(
                last_known_sha=freshness.head_sha,
                engagement_id=freshness.branch,
            )
            if report.merge_detected or report.external_changes > 0:
                current_head = get_head_sha(root)
                new_record = freshness.mark_fresh(current_head)
                save_freshness(new_record, root)
    except Exception:
        pass  # Non-critical — best-effort


__all__ = [
    "bold",
    "find_project_root",
    "get_head_sha",
    "init_git",
    "initial_commit",
    "load_project_snapshot",
    "reconcile_before_summary",
    "require_project_root",
    "resolve_session_type_flag",
    "write_assessment_report",
    "write_minimal_constitution",
    "WORKFLOWS_EPILOG",
]
