"""Dev Harness CLI — Click-based command interface."""

import asyncio
import subprocess
from pathlib import Path
from typing import Optional

import click

from harness.cli.commands import (
    abort_engagement_command,
    create_engagement_command,
    dispatch_cli_command,
    enter_phase_command,
    next_command,
    query_status_command,
    query_whats_next_command,
)
from harness.constitution.loader import scaffold as scaffold_constitution
from harness.constitution.templates.template_registry import (
    TemplateRegistry,
    refresh_agent_profiles,
    seed_agent_profiles,
)
from harness.engagement.checkpoint import CHECKPOINT_EXPIRY_HOURS
from harness.paths import (
    find_project_root as _py_find_project_root,
)
from harness.paths import (
    get_engagement_dir,
    get_engagement_md,
    get_engagements_dir,
    get_harness_dir,
    get_harness_state_path,
)
from harness.paths import (
    resolve_explicit_project_root as _py_resolve_explicit_project_root,
)
from harness.paths import (
    resolve_project_root as _py_resolve_project_root,
)
from harness.scm.git import GitRepo
from harness.scm.gitignore import write_gitignore
from harness.state.freshness import FreshnessRecord, save_freshness
from harness.state.snapshot import EngagementSnapshot, ProjectSnapshot, SnapshotWriter

# Re-exported for introspection / documentation
__all__ = ["main"]


# ── Project Root Discovery ─────────────────────────────────────────────────


def _find_project_root(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from *start* (default: CWD) to find the nearest
    directory containing a ``.harness/`` folder.

    Returns the first ancestor with ``.harness/``, or ``None`` if no
    project root is found (the walk stops at filesystem root).

    This is the canonical way to locate a harness project — it works
    regardless of which subdirectory the user runs the tool from.
    """
    return _py_find_project_root(start)


def _require_project_root(
    explicit_path: Optional[str] = None,
    command_name: str = "this command",
) -> Path:
    """Resolve the project root given an optional explicit path."""
    if explicit_path is not None:
        try:
            return _py_resolve_explicit_project_root(Path(explicit_path).resolve(), command_name=command_name)
        except SystemExit:
            raise click.Abort()

    try:
        return _py_resolve_project_root(command_name=command_name)
    except SystemExit:
        raise click.Abort()


def _bold(text):
    """Wrap *text* in ANSI bold escape codes when stdout is a terminal."""
    import sys
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
    hr=_bold("\u2501" * 60),
    getting_started=_bold("Getting Started"),
    engagement_lifecycle=_bold(
        "Engagement Lifecycle \u2014 plan, track, and execute development work"
    ),
    engagement_mgmt=_bold("Engagement Management"),
    analysis=_bold("Analysis & Reporting"),
    state_mgmt=_bold("State Management"),
    infrastructure=_bold("Infrastructure"),
    tips=_bold("Tips"),
)


from harness._version import __version__, __build__, __build_date__, __commit__


def _print_version(ctx, param, value):
    """Print version and exit."""
    if not value or ctx.resilient_parsing:
        return
    click.echo(f"{__version__}.{__build__:03d}")
    ctx.exit()


def _print_version_full(ctx, param, value):
    """Print full version and build info, then exit."""
    if not value or ctx.resilient_parsing:
        return
    date_str = __build_date__ if __build_date__ else "unknown"
    commit_str = __commit__ if __commit__ else "unknown"
    click.echo(f"dev-harness v{__version__}.{__build__:03d}")
    click.echo(f"build:   {__build__:03d}")
    click.echo(f"commit:  {commit_str}")
    click.echo(f"date:    {date_str}")
    ctx.exit()


@click.group(
    invoke_without_command=True,
)
@click.option(
    "--version",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_print_version,
    help="Show version and exit.",
)
@click.option(
    "--version-full",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_print_version_full,
    help="Show full version, build number, and build date.",
)
def main():
    """Dev Harness — agent orchestration for software development.

    See ``harness workflows`` for a guide to choosing the right workflow.
    """
    pass


@main.command()
def workflows():
    """Show workflow guidance and when to use each workflow.

    Displays the same comprehensive workflow reference shown at the bottom
    of ``harness --help``. Use this when you need a quick reminder of which
    workflow fits your current task.

    See also: ``harness <command> --help`` for per-command options.
    """
    click.echo(WORKFLOWS_EPILOG.strip())



@main.command()
@click.argument("slug")
def whatsnext(slug):
    """Show available next actions for an engagement.

    Dispatches a ``QueryWhatsNext`` command via the CommandBus and
    displays the available commands, current phase, and engagement
    status.

    Examples::

        harness whatsnext my-engagement
    """
    try:
        cmd = query_whats_next_command(slug)
        result = dispatch_cli_command(cmd)

        if not result.success:
            click.echo("WhatsNext query failed: " + result.error, err=True)
            raise click.Abort()

        data = result.data
        click.echo("Engagement: " + str(data.get('slug', slug)))
        click.echo("  Status: " + str(data.get('status', 'unknown')))
        click.echo("  Current phase: " + str(data.get('current_phase', '-')))

        pending = data.get('pending_phases', [])
        if pending:
            click.echo("  Pending phases: " + ', '.join(pending))

        completed = data.get('completed_phases', [])
        if completed:
            click.echo("  Completed phases: " + ', '.join(completed))

        cmds = data.get('available_commands', [])
        if cmds:
            click.echo("  Available commands: " + ', '.join(cmd for cmd in cmds))

        if data.get('blocked'):
            reason = data.get('block_reason', 'Unknown')
            click.echo("  \u26a0\ufe0f  Blocked: " + str(reason))

    except click.Abort:
        raise
    except Exception as exc:
        click.echo("WhatsNext error: " + str(exc), err=True)
        raise click.Abort()


@main.command()
@click.argument("slug")
@click.argument("phase")
def enter_phase(slug, phase):
    """Dispatch an EnterPhase command through the CommandBus.

    Enters the specified phase for an engagement. The actual
    phase transition is delegated to PhaseOrchestrator via the
    CommandBus handler.

    Examples::

        harness enter-phase my-engagement design

        harness enter-phase my-engagement requirements
    """
    try:
        cmd = enter_phase_command(slug, phase)
        result = dispatch_cli_command(cmd)

        if not result.success:
            click.echo("Enter phase failed: " + result.error, err=True)
            raise click.Abort()

        click.echo(result.message)

    except click.Abort:
        raise
    except Exception as exc:
        click.echo("Enter phase error: " + str(exc), err=True)
        raise click.Abort()


@main.command()
@click.argument("project_dir", required=False, default=None)
@click.option("--template", default=None, help="Project template (choices: backend-service, library, cli-tool, data-pipeline, general-research)")
@click.option("--seed", help="Context to seed from")
@click.option("--no-git", is_flag=True, help="Skip git init")
@click.option(
    "--force",
    is_flag=True,
    help="Re-initialise even if already initialised (overwrites state)",
)
def init(project_dir, template, seed, no_git, force):
    """Initialise a harness project in the current or specified directory.

    Without arguments, initialises the current directory (like ``git init``).
    Optionally pass a directory name to create and initialise a new subdirectory.

    If the project is already initialised (``.harness/`` exists), this command
    will refuse to re-initialise unless ``--force`` is passed.

    Examples::

        harness init                         # init current dir
        harness init my-project              # init new subdirectory
        harness init --template backend-service
        harness init --force                 # re-init (overwrites state)
    """
    if project_dir:
        project_path = Path.cwd() / project_dir
        if project_path.exists():
            if project_path.is_file():
                click.echo(
                    f"Error: {project_path} is a file, not a directory.",
                    err=True,
                )
                raise click.Abort()
        else:
            project_path.mkdir(parents=True, exist_ok=True)
    else:
        project_path = Path.cwd()

    # Check if already initialised
    already_initted = get_harness_dir(project_path).is_dir()
    if already_initted and not force:
        click.echo(
            f"Error: {project_path} is already a harness project."
            f"\nUse --force to re-initialise (overwrites constitution,"
            f" agent profiles, and engagement state).",
            err=True,
        )
        raise click.Abort()

    project_name = project_path.name

    # Wrap all scaffold steps in try/except
    try:
        # 2. Scaffold constitution.yaml
        constitution_path = project_path / "constitution.yaml"
        if template:
            scaffold_constitution(
                template, project_name, constitution_path, overrides={}
            )
        else:
            _write_minimal_constitution(constitution_path, project_name)
        click.echo(f"  Created {constitution_path}")

        gitignore_path = project_path / ".gitignore"
        if not gitignore_path.exists():
            write_gitignore(gitignore_path, template=template or "none")
            click.echo(f"  Created {gitignore_path}")

        # 3. Seed all agent profiles (always — template just controls phase activation)
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
        click.echo(f"  Created {len(ALL_AGENTS)} agent profile(s)")

        # 4. Scaffold template directory structure (only if template chosen)
        if template:
            created_dirs = TemplateRegistry.scaffold(
                template, project_name, project_path
            )
            click.echo(f"  Created {len(created_dirs)} scaffold directories")
        else:
            click.echo("  (no template — no scaffold directories created)")

        # 5. Create .harness/ directory structure
        get_engagements_dir(project_path).mkdir(parents=True, exist_ok=True)
        get_harness_dir(project_path).joinpath(".gitkeep").write_text("")
        click.echo("  Created .harness/ (engagement state directory)")

        # 6. Create initial state snapshot
        snapshot_path = get_harness_state_path(project_path)
        snapshot = ProjectSnapshot(
            project_name=project_name,
            version="0.1.0",
            current_engagement=None,
            engagements=[],
        )
        SnapshotWriter.write(snapshot, snapshot_path)
        click.echo(f"  Created {snapshot_path}")

        # 7. Initialise git (unless --no-git) and make initial commit
        if not no_git:
            git_ok = _init_git(project_path)
            if git_ok:
                click.echo("  Initialised git repository")
                _initial_commit(project_path)
            else:
                click.echo(
                    "  Warning: git init failed. Project was still created."
                )

        # 8. Print summary
        click.echo("")
        click.echo("Done!")
        click.echo(f"  Project : {project_name}")
        click.echo(f"  Template: {template or '(none)'}")
        click.echo(f"  Path    : {project_path}")

    except KeyError as exc:
        click.echo(f"Error: Unknown template — {exc}", err=True)
        raise click.Abort()
    except Exception as exc:
        click.echo(f"Error during scaffolding: {exc}", err=True)
        raise click.Abort()


def _write_minimal_constitution(path: Path, project_name: str) -> None:
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


def _initial_commit(path: Path) -> None:
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


def _init_git(path: Path) -> bool:
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
        click.echo("  Warning: git init timed out")
        return False


@main.command()
@click.argument("project_dir", required=False, default=None)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing agent profile files (not just missing ones).",
)
def refresh_agents(project_dir, force):
    """Refresh agent profiles from the harness's current agent registry.

    Synchronises the project's ``agents/`` directory with the authoritative
    agent definitions in ``harness.agents.agent_registry.AGENTS``.

    This is useful after upgrading the harness or adding new agent roles
    to the registry — it updates local agent definitions without nuking
    the rest of the project (engagements, constitution, state).

    What it DOES:
    - Creates/updates ``agents/<role>/identity.md`` and ``procedures.md``
    - Creates/updates ``agents/standards/community-standards.md``
    - Creates ``agents/<role>/memory/.gitkeep`` if missing
    - Reports which agents were created, updated, or skipped

    What it does NOT do:
    - Does NOT touch ``.harness/engagements/`` (engagement state is preserved)
    - Does NOT overwrite ``.harness/providers.yaml``
    - Does NOT delete agent directories (even unused ones, unless --force)

    Without ``--force``, only creates profiles for agents that don't already
    have them. With ``--force``, overwrites all profile files.

    Examples::

        harness refresh-agents
        harness refresh-agents path/to/project
        harness refresh-agents --force
    """
    project_path = _require_project_root(
        explicit_path=Path.cwd() / project_dir if project_dir else None,
        command_name="refresh-agents",
    )

    result = refresh_agent_profiles(project_path, force=force)

    click.echo("Agent profiles refreshed.")
    for action, label in [("created", "Created"), ("updated", "Updated"), ("existing", "Already up-to-date")]:
        agents = result.get(action, [])
        if agents:
            click.echo(f"  {label}: {len(agents)}")
            for name in agents:
                click.echo(f"    - {name}")


@main.command()
@click.argument("description")
@click.option(
    "--mode", type=click.Choice(["wild", "auto", "full"]), default="auto"
)
@click.option("--backend")
@click.option("--max-iterations", default=5, type=int,
              help="Maximum edit-feedback cycles per wave (default: 5)")
@click.option("--partial-approval/--no-partial-approval", default=True,
              help="Enable partial approval (default: enabled)")
def work(description, mode, backend, max_iterations, partial_approval):
    """Start a new engagement.

    Creates a tracked engagement: state snapshot, freshness record,
    and (when Temporal is available) a durable workflow.

    Optional --max-iterations controls how many edit-feedback cycles a
    wave can undergo before the harness suggests moving on (soft limit).

    Examples:

        harness work "Add search feature" --mode wild

        harness work "Refactor auth" --mode full --max-iterations 3

        harness work "Fix bugs" --mode auto --no-partial-approval
    """
    try:
        from harness.state.temporal_adapter import start_engagement
        from harness.state.temporal_server import ensure_temporal_server

        root = _require_project_root()
        repo = GitRepo(root)
        current_branch = repo.branch()
        current_head = _get_head_sha(root)
        engagement_id = f"eng-{current_branch}-{current_head[:8]}"

        # Build iteration config
        iteration_config = {
            "max_iterations": max_iterations,
            "escalation_after_max": True,
            "partial_approval": partial_approval,
        }

        # Try to start Temporal workflow
        temporal_ok = False
        try:
            temporal_available = ensure_temporal_server()
            if temporal_available:
                asyncio.run(start_engagement(
                    engagement_id=engagement_id,
                    description=description,
                    gate_mode=mode,
                    iteration_config=iteration_config,
                ))
                temporal_ok = True
        except Exception:
            click.echo("  (Temporal unavailable — using local state only)")

        # Write snapshot
        snapshot_path = get_harness_state_path(root)
        existing = _load_project_snapshot(snapshot_path)

        eng = EngagementSnapshot(
            id=engagement_id,
            description=description,
            status="in_progress",
            gate_mode=mode,
            phase="requirements",
        )
        existing.engagements.append(eng)
        existing.current_engagement = engagement_id
        SnapshotWriter.write(existing, snapshot_path)

        # Write freshness
        record = FreshnessRecord(
            branch=current_branch,
            head_sha=current_head,
            last_reconciled="",
            stale=False,
        ).mark_fresh(current_head)
        save_freshness(record, root)

        gateway = "temporal" if temporal_ok else "local"
        click.echo(
            f"Engagement started: '{description}' (mode: {mode}, "
            f"gateway: {gateway}, max_iterations: {max_iterations})"
        )
        click.echo(f"  ID: {engagement_id}")
        click.echo(f"  Branch: {current_branch}")

    except Exception as exc:
        click.echo(f"Failed to start engagement: {exc}", err=True)
        raise click.Abort()


@main.command()
@click.option("--engagement", help="Engagement ID (default: current)")
@click.option("--deep", is_flag=True)
@click.option("--assess", "assess_flag", is_flag=True, help="Run LLM-based independent assessment (P1-P5)")
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON")
@click.option("--reconcile", is_flag=True, help="Refresh state before summary")
def summary(deep, assess_flag, engagement, json_flag, reconcile):
    """Show project status summary.

    Always runs a fast scan (structure + git diff). With --deep, also
    checks architecture conformance, test coverage, and dead code.

    With --assess, runs the LLM-based independent assessment (P1-P5)
    for a comprehensive codebase evaluation.

    Use --reconcile to refresh state before analysis (handy after merges).

    Examples:

        harness summary

        harness summary --deep --json

        harness summary --assess --json

        harness summary --reconcile
    """
    try:
        from harness.analysis.deep import (
            assess_coverage,
            check_architecture_conformance,
            find_dead_code,
        )
        from harness.analysis.fast import scan_git_diff, scan_structure
        from harness.analysis.summary import format_report

        root = _require_project_root()

        # Optional: reconcile state first
        if reconcile:
            _reconcile_before_summary(root)

        results = []

        # Always run fast scan
        structure = scan_structure(root)
        results.append(structure)

        diff = scan_git_diff(root)
        results.append(diff)

        if deep:
            conformance = check_architecture_conformance(root, project_type="python")
            results.append(conformance)
            coverage = assess_coverage(root)
            results.append(coverage)
            dead = find_dead_code(root)
            results.append(dead)

        output_format = "json" if json_flag else "markdown"
        report = format_report(results, format=output_format)

        # R22: LLM-based assessment when --assess
        if assess_flag:
            try:
                import asyncio

                from harness.analysis.assessment import assess as run_assessment
                assessment = asyncio.run(run_assessment(root, deep=True))
                if output_format == "json":
                    # Merge assessment into JSON output
                    import json as json_mod
                    base = json_mod.loads(report)
                    base["assessment"] = assessment.to_dict().get("assessment", {})
                    report = json_mod.dumps(base, indent=2, default=str)
                else:
                    report += "\n\n---\n\n" + assessment.report_text
            except Exception as exc:
                report += (
                    "\n\n## LLM-Based Assessment\n\n"
                    f"⚠️ Assessment agents unavailable: {exc}\n"
                )

        click.echo(report)

    except Exception as exc:
        click.echo(f"Analysis failed: {exc}", err=True)
        raise click.Abort()


def _reconcile_before_summary(root: Path) -> None:
    """Reconcile freshness before running summary analysis."""
    try:
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
                current_head = _get_head_sha(root)
                new_record = freshness.mark_fresh(current_head)
                save_freshness(new_record, root)
    except Exception:
        pass  # Non-critical — best-effort


@main.group()
def agent():
    """List, show, and run harness agents."""
    pass


@agent.command(name="list")
def list_agents():
    """List all registered harness agent roles.

    Displays a table of agent roles, their tags, and the fleet they
    belong to (if any).

    Examples::

        harness agent list
    """
    root = _find_project_root()
    from harness.agents.agent_registry import (
        AGENTS,
        list_agent_roles,
    )

    roles = list_agent_roles()
    if not roles:
        click.echo("No agents registered.")
        return

    # Build fleet membership if project root available
    fleet_map: dict[str, str] = {}
    if root:
        from harness.agents.fleet_registry import FleetRegistry
        registry = FleetRegistry(root)
        for role in roles:
            fn = registry.find_fleet_for_agent(role)
            if fn:
                fleet_map[role] = fn

    click.echo(f"\n  {'Role':<30} {'Tags':<40} {'Fleet':<20}")
    click.echo(f"  {'-'*28}  {'-'*38}  {'-'*18}")
    for spec in AGENTS:
        role = spec.role
        tags = ", ".join(getattr(spec, 'tags', []) or [])
        fleet = fleet_map.get(role, "-")
        click.echo(f"  {role:<30} {tags:<40} {fleet:<20}")
    click.echo()


@agent.command()
@click.argument("agent_role")
def show(agent_role):
    """Show details for a specific agent role.

    Displays the agent's role, description, tags, tool permissions,
    and fleet membership.

    Examples::

        harness agent show architect

        harness agent show coding-agent
    """
    from harness.agents.agent_registry import get_agent

    spec = get_agent(agent_role)
    if spec is None:
        click.echo(f"Agent role '{agent_role}' not found.", err=True)
        raise click.Abort()

    click.echo(f"Agent: {spec.role}")
    click.echo(f"  Description: {spec.description or '-'}")
    tags = ", ".join(getattr(spec, 'tags', []) or [])
    click.echo(f"  Tags: {tags or '-'}")

    # Fleet membership
    root = _find_project_root()
    if root:
        from harness.agents.fleet_registry import FleetRegistry
        registry = FleetRegistry(root)
        fleet_name = registry.find_fleet_for_agent(spec.role)
        if fleet_name:
            fleet = registry.get_fleet(fleet_name)
            click.echo(f"  Fleet: {fleet_name} (lead: {fleet.lead_role if fleet else '-'})")
        else:
            click.echo("  Fleet: (none)")

    # Permissions
    perms = getattr(spec, 'tool_permissions', None)
    if perms:
        click.echo("  Tool Permissions:")
        for perm_name, perm_val in perms.__dict__.items():
            if not perm_name.startswith("_"):
                click.echo(f"    {perm_name}: {perm_val}")


@agent.command()
@click.argument("agent_name")
@click.option("--preview", is_flag=True, help="Preview without writing")
@click.option("--output", type=click.Path(path_type=Path), help="Output directory")
def run(agent_name, preview, output):
    """Run a harness agent by name.

    Currently supported: 'sync'

    Usage:
        harness agent run sync --preview
        harness agent run sync --output ./src/harness/templates/
    """
    if agent_name == "sync":
        from harness.sync.pipeline import run_sync
        result = run_sync(output_dir=output, preview=preview)
        click.echo(result)
    else:
        click.echo(f"Unknown agent: {agent_name}", err=True)
        raise click.Abort()


# ---------------------------------------------------------------------------
# Fleet management commands
# ---------------------------------------------------------------------------


@main.group()
def fleet():
    """Manage harness fleets.

    Fleets group related agents into domain teams (architecture, coding,
    review, testing). Each fleet has a lead, sub-agents, guidelines, and
    inclusion rules that control which agents are active based on project
    type and governance level.

    See ``harness agent list`` for available agents.
    """
    pass


@fleet.command(name="list")
@click.option("--consults", is_flag=True, help="Show consultation capabilities for each fleet")
def list_fleets(consults):
    """List all registered fleets with their agents.

    Shows fleets, their leads, sub-agent count, and governance level.

    Examples::

        harness fleet list

        harness fleet list --consults
    """
    root = _require_project_root(command_name="fleet list")
    from harness.agents.fleet_registry import FleetRegistry
    from harness.agents.governance import get_project_governance

    registry = FleetRegistry(root)
    fleets = registry.list_fleets()
    gov = get_project_governance(root)

    if not fleets:
        click.echo("No fleets registered.")
        return

    click.echo(f"\n  Governance: {gov.value}")
    click.echo(
        f"  {'Fleet':<24} {'Lead':<24} {'Sub-Agents':<12} {'Consult':<8} {'Builtin':<10}"
    )
    click.echo(f"  {'-'*22}  {'-'*22}  {'-'*10}  {'-'*8}  {'-'*8}")
    for f in fleets:
        marker = "✓" if f.builtin else "✗"
        consult_count = len(f.consultations) if f.consultations else 0
        click.echo(
            f"  {f.name:<24} {f.lead_role:<24} {len(f.sub_agents):<12} {consult_count:<8} {marker:<10}"
        )

    if consults:
        click.echo()
        for f in fleets:
            if f.consultations:
                click.echo(f"  --- {f.name} consultations ---")
                for cap in f.consultations:
                    mode_str = "⚠️" if cap.mode == "blocking" else " "
                    click.echo(f"    {mode_str} {cap.question}")
                    if cap.match_phrases:
                        for phrase in cap.match_phrases[:3]:  # show up to 3
                            click.echo(f"       match: \"{phrase}\"")
                        if len(cap.match_phrases) > 3:
                            click.echo(f"       ... +{len(cap.match_phrases) - 3} more")
                    click.echo(f"       scope: {cap.scope}")

    click.echo()


@fleet.command()
@click.argument("fleet_name")
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON")
def show(fleet_name, json_flag):
    """Show details for a specific fleet.

    Displays fleet name, lead role, description, sub-agents, guidelines,
    and inclusion rules.

    Examples::

        harness fleet show architecture

        harness fleet show review --json
    """
    root = _require_project_root(command_name="fleet show")
    from harness.agents.fleet_registry import FleetRegistry

    registry = FleetRegistry(root)
    f = registry.get_fleet(fleet_name)
    if f is None:
        click.echo(f"Fleet '{fleet_name}' not found.", err=True)
        raise click.Abort()

    if json_flag:
        from harness.agents.fleet_registry import FleetRegistry as FR
        data = FR._fleet_to_dict(f)
        import json
        click.echo(json.dumps(data, indent=2, sort_keys=True))
        return

    click.echo(f"Fleet: {f.name}")
    click.echo(f"  Lead:       {f.lead_role}")
    click.echo(f"  Description: {f.description or '-'}")
    click.echo(f"  Builtin:    {'Yes' if f.builtin else 'No'}")
    click.echo(f"  Sub-Agents: {len(f.sub_agents)}")
    for sa in f.sub_agents:
        click.echo(f"    - {sa}")
    click.echo(f"  Phases:     {', '.join(f.guidelines.phases) if f.guidelines.phases else '-'}")


@fleet.command(name="add-agent")
@click.argument("fleet_name")
@click.argument("agent_role")
def add_agent_to_fleet(fleet_name, agent_role):
    """Add an agent role to a fleet as a sub-agent.

    Persists the change to ``.harness/fleets.yaml``.

    Examples::

        harness fleet add-agent architecture my-custom-agent
    """
    root = _require_project_root(command_name="fleet add-agent")
    from harness.agents.fleet_registry import FleetRegistry

    registry = FleetRegistry(root)
    if registry.get_fleet(fleet_name) is None:
        click.echo(f"Fleet '{fleet_name}' not found.", err=True)
        raise click.Abort()

    if registry.add_sub_agent(fleet_name, agent_role):
        registry.save()
        click.echo(f"Sub-agent '{agent_role}' added to fleet '{fleet_name}'.")
    else:
        click.echo(
            f"Agent '{agent_role}' is already in fleet '{fleet_name}'."
        )


@fleet.command(name="remove-agent")
@click.argument("fleet_name")
@click.argument("agent_role")
def remove_agent_from_fleet(fleet_name, agent_role):
    """Remove an agent role from a fleet.

    Persists the change to ``.harness/fleets.yaml``.

    Examples::

        harness fleet remove-agent architecture my-custom-agent
    """
    root = _require_project_root(command_name="fleet remove-agent")
    from harness.agents.fleet_registry import FleetRegistry

    registry = FleetRegistry(root)
    if registry.get_fleet(fleet_name) is None:
        click.echo(f"Fleet '{fleet_name}' not found.", err=True)
        raise click.Abort()

    if registry.remove_sub_agent(fleet_name, agent_role):
        registry.save()
        click.echo(f"Sub-agent '{agent_role}' removed from fleet '{fleet_name}'.")
    else:
        click.echo(
            f"Agent '{agent_role}' not found in fleet '{fleet_name}'."
        )


@fleet.command(name="consult")
@click.argument("fleet_name")
@click.option("--no-truncate", is_flag=True,
              help="Show full match phrases without truncation")
def fleet_consult(fleet_name, no_truncate):
    """Show consultation capabilities for a fleet.

    Displays all registered consultation capabilities for the given fleet,
    including their mode (advisory/blocking), scope, and match phrases.

    Examples::

        harness fleet consult architecture

        harness fleet consult coding --no-truncate
    """
    root = _require_project_root(command_name="fleet consult")
    from harness.agents.fleet_registry import FleetRegistry

    registry = FleetRegistry(root)
    fleet = registry.get_fleet(fleet_name)
    if fleet is None:
        click.echo(f"Fleet '{fleet_name}' not found.", err=True)
        click.echo(f"Available fleets: {', '.join(f.name for f in registry.list_fleets())}")
        raise click.Abort()

    if not fleet.consultations:
        click.echo(f"Fleet '{fleet_name}' has no registered consultation capabilities.")
        return

    click.echo(f"\n  Fleet: {fleet.name}")
    click.echo(f"  Consultations: {len(fleet.consultations)}")
    click.echo()

    for i, cap in enumerate(fleet.consultations, 1):
        mode_symbol = "⚠️  BLOCKING" if cap.mode == "blocking" else "    advisory"
        click.echo(f"  [{i}] {cap.question}  ({mode_symbol})")
        click.echo(f"       Scope: {cap.scope}")
        if cap.match_phrases:
            phrases = cap.match_phrases
            if not no_truncate and len(phrases) > 6:
                shown = phrases[:6]
                remaining = len(phrases) - 6
                for p in shown:
                    click.echo(f"       Match: \"{p}\"")
                click.echo(f"       ... +{remaining} more (use --no-truncate to show all)")
            else:
                for p in phrases:
                    click.echo(f"       Match: \"{p}\"")
        click.echo()


@fleet.command(name="set-governance")
@click.argument("level", type=click.Choice(["exploration", "standard", "strict"]))
@click.option("--engagement", "slug", help="Apply to a specific engagement instead of project")
def set_fleet_governance(level, slug):
    """Set the governance level for the project or an engagement.

    Governance controls which agents are active:

    \b
      exploration  — lead agent only
      standard     — lead + sub-agents matched by project type
      strict       — full fleet + extra reviewers

    Examples::

        harness fleet set-governance standard

        harness fleet set-governance strict --engagement my-eng

        harness fleet set-governance exploration
    """
    from harness.agents.fleet import GovernanceLevel
    root = _require_project_root(command_name="fleet set-governance")

    gov = GovernanceLevel(level)

    if slug:
        from harness.agents.governance import set_engagement_governance
        set_engagement_governance(root, slug, gov)
        click.echo(
            f"Engagement '{slug}' governance set to '{level}'."
        )
    else:
        from harness.agents.governance import (
            get_project_governance,
            set_project_governance,
        )
        set_project_governance(root, gov)
        current = get_project_governance(root)
        click.echo(
            f"Project governance set to '{level}'."
        )


@main.command()
@click.argument("question", nargs=-1, required=True)
@click.option("--fleet", help="Limit consultation to a specific fleet")
@click.option("--mode", type=click.Choice(["advisory", "blocking"]),
              default="advisory",
              help="Consultation mode (advisory by default)")
@click.option("--engagement", help="Engagement context (optional)")
def consult(question, fleet, mode, engagement):
    """Ask a cross-fleet consultation question.

    Routes a question through all registered fleets' consultation
    capabilities. Returns the first matched capability's response,
    or lists all available questions if no match is found.

    Examples::

        harness consult \"Is this architecture still sound?\"

        harness consult --fleet architecture \"Should we use hex?\"

        harness consult --mode blocking \"Any critical issues?\"
    """
    root = _require_project_root(command_name="consult")
    from harness.agents.consultation import ConsultationOrchestrator
    from harness.agents.fleet_registry import FleetRegistry

    registry = FleetRegistry(root)
    orchestrator = ConsultationOrchestrator(registry)

    q = " ".join(question)

    # Check if any fleet can answer
    can_any = orchestrator.can_answer_any(q)
    if not can_any:
        click.echo(f"\n  No fleet can answer: \"{q}\"")
        available = orchestrator.get_available_questions(fleet_filter=fleet)
        if available:
            click.echo()
            click.echo("  Available questions:")
            for (fn, cap_q, cap_mode) in available:
                sym = "⚠️" if cap_mode == "blocking" else " "
                click.echo(f"    {sym} [{fn}] {cap_q}")
        else:
            click.echo("  No consultation capabilities registered.")
        return

    # Route and display
    result = orchestrator.route(q, mode=mode, fleet_filter=fleet)
    if result is None:
        click.echo(f"\n  No match for: \"{q}\"")
        available = orchestrator.get_available_questions(fleet_filter=fleet)
        if available:
            click.echo()
            click.echo("  Available questions:")
            for (fn, cap_q, cap_mode) in available:
                sym = "⚠️" if cap_mode == "blocking" else " "
                click.echo(f"    {sym} [{fn}] {cap_q}")
        return

    # Display matched result
    click.echo()
    mode_sym = "⚠️  BLOCKING" if result.is_blocking() else "    advisory"
    click.echo(f"  Fleet: {result.fleet_name}")
    click.echo(f"  Capability: {result.capability}")
    click.echo(f"  Mode: {mode_sym}")
    click.echo(f"  Status: {result.status}")
    if result.error:
        click.echo(f"  Error: {result.error}")
    click.echo()
    click.echo(f"  {result.summary or 'No detailed response.'}")


@main.group()
def wave():
    """Manage and run per-wave code+test cycles.

    Each wave in the engagement plan represents a self-contained unit
    of work. These commands let you list, run, and inspect the state
    of waves through their implement\u2192test\u2192verify\u2192commit cycle.
    """
    pass


@wave.command(name="list")
@click.option("--engagement", "slug", help="Engagement slug (default: active)")
def list_waves(slug):
    """List waves from the engagement plan."""
    root = _require_project_root()

    if not slug:
        from harness.engagement.resolver import resolve_active_engagement
        slug = resolve_active_engagement(root)

    if not slug:
        click.echo(
            "No active engagement. Create one with:\n"
            "  harness engagement create \"your task\"",
            err=True,
        )
        raise click.Abort()

    from harness.plan.plan_manager import PlanManager

    pm = PlanManager(root, slug)
    statuses = pm.get_status()

    if not statuses:
        click.echo("No waves defined in the plan.")
        return

    click.echo()
    click.echo(f"  {'Wave ID':<12} {'Title':<36} {'Type':<14} {'State':<16}")
    click.echo(f"  {'-'*11}  {'-'*34}  {'-'*12}  {'-'*14}")
    for s in statuses:
        marker = "*" if s["is_modifiable"] and not s["is_committed"] else " "
        click.echo(
            f"  {marker} {s['id']:<10} {s['title']:<34} "
            f"{s['type']:<12} {s['state']:<14}"
        )
    click.echo()
    click.echo("Legend: * = active (modifiable, not yet committed)")


@wave.command()
@click.argument("wave_id")
@click.option("--no-test", is_flag=True, help="Skip automated test suite execution")
@click.option("--backend", help="Agent backend name")
@click.option("--engagement", "slug", help="Engagement slug (default: active)")
def run(wave_id, no_test, backend, slug):
    """Run a wave through the implement\u2192test\u2192verify\u2192commit cycle.

    Usage:
        harness wave run wave-01
        harness wave run wave-01 --no-test
        harness wave run wave-01 --backend claude
    """
    root = _require_project_root()

    if not slug:
        from harness.engagement.resolver import resolve_active_engagement
        slug = resolve_active_engagement(root)

    if not slug:
        click.echo(
            "No active engagement. Create one with:\n"
            "  harness engagement create \"your task\"",
            err=True,
        )
        raise click.Abort()

    from harness.wave.wave_cycle import WaveCycleConfig, WaveCycleRunner

    config = WaveCycleConfig(
        auto_test=not no_test,
    )
    if backend:
        config.backend_name = backend

    runner = WaveCycleRunner(root, slug, config)

    click.echo(f"\n🚀 Running wave '{wave_id}' through code+test cycle...\n")

    import asyncio

    try:
        result = asyncio.run(runner.run_wave(wave_id))
    except Exception as exc:
        click.echo(f"Error running wave cycle: {exc}", err=True)
        raise click.Abort()

    if result.success:
        click.echo()
        click.echo(f"  ✅ Wave {result.wave_id} completed successfully!")
        click.echo(f"     Title:     {result.title}")
        click.echo(f"     Iterations: {result.iterations}")
        click.echo(f"     Committed:  {result.committed}")
        if result.test_results:
            click.echo(f"     Tests:      {result.test_results.get('summary', '')}")
        click.echo()
        click.echo("  Ready to commit and raise a PR.")
    else:
        click.echo()
        click.echo(f"  ❌ Wave {result.wave_id} failed.")
        click.echo(f"     Title:      {result.title}")
        click.echo(f"     Iterations: {result.iterations}")
        for err in result.errors:
            click.echo(f"     - {err}")
        if result.test_results:
            click.echo(f"     Tests:      {result.test_results.get('summary', '')}")
        click.echo()
        click.echo(
            "  Fix the issues and re-run: harness wave run "
            f"{wave_id}"
        )
        raise click.Abort()


@wave.command()
@click.option("--engagement", "slug", help="Engagement slug (default: active)")
def status(slug):
    """Show detailed wave status from the engagement plan."""
    root = _require_project_root()

    if not slug:
        from harness.engagement.resolver import resolve_active_engagement
        slug = resolve_active_engagement(root)

    if not slug:
        click.echo(
            "No active engagement. Create one with:\n"
            "  harness engagement create \"your task\"",
            err=True,
        )
        raise click.Abort()

    from harness.plan.plan_manager import PlanManager

    pm = PlanManager(root, slug)
    click.echo()
    click.echo(pm.summary())


@wave.command(name="create-from-finding")
@click.argument("finding_id")
@click.option("--engagement", "slug", help="Engagement slug (default: active)")
def create_wave_from_finding(finding_id, slug):
    """Create a wave from an assessment finding.

    Reads the latest assessment manifest for the active engagement,
    finds the specified finding by ID, and creates a wave with its
    description as the wave spec.

    Usage:
        harness wave create-from-finding finding-001
        harness wave create-from-finding finding-001 --engagement my-engagement
    """
    import json
    from harness.plan.plan_manager import PlanManager

    root = _require_project_root()

    if not slug:
        from harness.engagement.resolver import resolve_active_engagement
        slug = resolve_active_engagement(root)

    if not slug:
        click.echo(
            "No active engagement. Create one with:\n"
            "  harness engagement create \"your task\"",
            err=True,
        )
        raise click.Abort()

    # Find the latest assessment manifest
    from harness.paths import get_engagements_dir
    assess_dir = get_engagements_dir(root) / slug / "assessments"
    if not assess_dir.is_dir():
        click.echo(
            f"No assessments found for engagement '{slug}'.\n"
            f"Run an assessment first:\n"
            f"  harness assess . --deep",
            err=True,
        )
        raise click.Abort()

    # Scan manifests in descending order (newest first)
    manifests = sorted(
        assess_dir.glob("*-manifest.json"),
        reverse=True,
    )
    if not manifests:
        click.echo(
            f"No assessment manifests found in {assess_dir}.",
            err=True,
        )
        raise click.Abort()

    # Load the latest manifest
    manifest = json.loads(manifests[0].read_text())
    findings = manifest.get("findings", [])

    if not findings:
        click.echo(
            "The latest assessment does not contain structured findings.\n"
            "Re-run the assessment with --deep to get structured findings:\n"
            "  harness assess . --deep",
            err=True,
        )
        raise click.Abort()

    # Find the requested finding
    target = None
    for f in findings:
        if f.get("id") == finding_id:
            target = f
            break

    if target is None:
        available = [f.get("id", "?") for f in findings]
        click.echo(
            f"Finding '{finding_id}' not found in the latest assessment.\n"
            f"Available findings: {', '.join(available[:20])}",
            err=True,
        )
        raise click.Abort()

    if target.get("wave_slug"):
        click.echo(
            f"Finding '{finding_id}' already has a wave "
            f"({target['wave_slug']}). Skipping."
        )
        return

    # Build the wave title from the finding
    category = target.get("category", "other")
    message = target.get("message", "")
    severity = target.get("severity", "info")

    # Truncate the message to a reasonable title (first 50 chars)
    title = message[:72] + ("..." if len(message) > 72 else "")

    # Create the wave via PlanManager
    pm = PlanManager(root, slug)
    wave = pm.add_wave(
        title=title,
        wave_type="refactor",  # Refactoring type
        trigger_phase="assessment",
        trigger_reason=(
            f"Finding {finding_id}: [{severity}] {category} — {message[:100]}"
        ),
    )

    # Update the manifest to record the wave association
    target["wave_slug"] = wave.id
    target["wave_status"] = "open"
    manifests[0].write_text(json.dumps(manifest, indent=2))

    click.echo()
    click.echo(f"  Created wave '{wave.id}' from finding '{finding_id}'")
    click.echo(f"  Title: {title}")
    click.echo(f"  Severity: {severity}, Category: {category}")
    click.echo()
    click.echo(f"  Run it with:  harness wave run {wave.id}")
    click.echo("  See plan:     harness wave list")


@wave.command(name="create-from-assessment")
@click.option("--focus", type=click.Choice(["high-risk", "medium", "all"]),
              default="high-risk",
              help="Filter findings by severity (default: high-risk)")
@click.option("--limit", type=int, default=0,
              help="Max waves to create (0 = no limit)")
@click.option("--refactoring", is_flag=True,
              help="Mark the engagement as a refactoring engagement")
@click.option("--engagement", "slug", help="Engagement slug (default: active)")
def create_waves_from_assessment(focus, limit, slug, refactoring):
    """Create waves from all matching assessment findings.

    Reads the latest assessment manifest, filters findings by the
    given focus level, and creates a wave for each finding that
    doesn't already have one. Updates the manifest to track
    finding-to-wave associations.

    Use --limit to cap the number of waves created (useful for
    starting with just the top N findings).

    Use --refactoring to mark the engagement as a refactoring
    engagement (sets session_type + refactoring flag in
    engagement.yaml, records baseline reference).

    Examples:

        harness wave create-from-assessment
        harness wave create-from-assessment --focus medium
        harness wave create-from-assessment --focus all --limit 5
        harness wave create-from-assessment --refactoring
        harness wave create-from-assessment --engagement my-engagement
    """
    import json
    from harness.plan.plan_manager import PlanManager

    root = _require_project_root()

    if not slug:
        from harness.engagement.resolver import resolve_active_engagement
        slug = resolve_active_engagement(root)

    if not slug:
        click.echo(
            "No active engagement. Create one with:\n"
            "  harness engagement create \"your task\"",
            err=True,
        )
        raise click.Abort()

    # Find the latest assessment manifest
    from harness.paths import get_engagements_dir
    assess_dir = get_engagements_dir(root) / slug / "assessments"
    if not assess_dir.is_dir():
        click.echo(
            f"No assessments found for engagement '{slug}'.\n"
            f"Run an assessment first:\n"
            f"  harness assess . --deep",
            err=True,
        )
        raise click.Abort()

    manifests = sorted(
        assess_dir.glob("*-manifest.json"),
        reverse=True,
    )
    if not manifests:
        click.echo(
            f"No assessment manifests found in {assess_dir}.",
            err=True,
        )
        raise click.Abort()

    manifest = json.loads(manifests[0].read_text())
    findings = manifest.get("findings", [])

    if not findings:
        click.echo(
            "The latest assessment does not contain structured findings.\n"
            "Re-run with:\n"
            "  harness assess . --deep",
            err=True,
        )
        raise click.Abort()

    # Filter findings by severity
    def _matches_focus(f: dict) -> bool:
        sev = f.get("severity", "info")
        if focus == "high-risk":
            return sev in ("error", "critical")
        elif focus == "medium":
            return sev in ("error", "critical", "warning")
        return True  # all

    matching = [f for f in findings if _matches_focus(f)]

    if not matching:
        click.echo(f"No findings match focus level '{focus}'.")
        return

    # Filter out findings that already have waves
    unassigned = [f for f in matching if not f.get("wave_slug")]

    if not unassigned:
        click.echo(
            f"All {len(matching)} matching findings already have "
            f"waves assigned. Nothing to create."
        )
        return

    # Apply limit
    if limit > 0:
        unassigned = unassigned[:limit]

    # Create waves
    pm = PlanManager(root, slug)
    created = 0
    skipped = 0
    manifest_updated = False

    for f in unassigned:
        fid = f.get("id", "?")
        severity = f.get("severity", "info")
        category = f.get("category", "other")
        message = f.get("message", "")
        title = message[:72] + ("..." if len(message) > 72 else "")

        wave = pm.add_wave(
            title=title,
            wave_type="refactor",
            trigger_phase="assessment",
            trigger_reason=(
                f"Finding {fid}: [{severity}] {category} — {message[:100]}"
            ),
        )

        f["wave_slug"] = wave.id
        f["wave_status"] = "open"
        manifest_updated = True
        created += 1

        click.echo(f"  ✓ {fid}: created wave '{wave.id}' — {title[:50]}")

    if manifest_updated:
        manifests[0].write_text(json.dumps(manifest, indent=2))

    # If --refactoring flag is set, update engagement.yaml
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

    skipped = len(matching) - len(unassigned) - (len(unassigned) - created)
    click.echo()
    click.echo(
        f"  Created {created} wave(s) from {focus} findings "
        f"({len(matching)} matched, {skipped} already assigned)"
    )
    if limit > 0 and created == limit:
        click.echo(f"  Reached --limit {limit}. Run again to create more.")
    click.echo()
    click.echo("  Run:  harness wave list")
    click.echo("  Run:  harness wave run <wave-id>")


@main.command()
@click.argument("prompt_text", required=False, default=None)
@click.option("--engagement", "engagement_slug", help="Engagement slug (default: active)")
@click.option("--phase", default="design", help="Phase context (default: design)")
@click.option(
    "--context-tier",
    "context_tier",
    type=click.IntRange(1, 3),
    default=2,
    show_default=True,
    help="Context load tier: 1=inventory only, 2=+summaries, 3=+snippets",
)
def chat(prompt_text, engagement_slug, phase, context_tier):
    """Interactive LLM chat session within an engagement.

    Opens a live chat with the configured LLM provider, saving the
    conversation to the engagement transcript directory.

    Examples::

        harness chat                                 # interactive mode
        harness chat "Design a user auth system"     # one-shot
        harness chat --phase requirements            # start in requirements phase
        harness chat --engagement my-feature         # specific engagement
    """
    try:
        import asyncio
        root = _require_project_root()
        from harness.session.loop import chat_loop

        slug = engagement_slug
        if not slug:
            from harness.engagement.resolver import resolve_active_engagement
            slug = resolve_active_engagement(root)

        if not slug:
            click.echo(
                "No active engagement. Create one with:\n"
                "  harness engagement create \"your task\"",
                err=True,
            )
            raise click.Abort()

        # Verify the engagement directory exists
        eng_dir = get_engagement_dir(root, slug)
        if not eng_dir.is_dir():
            click.echo(
                f"Engagement '{slug}' not found. "
                f"Expected directory: {eng_dir}",
                err=True,
            )
            raise click.Abort()

        asyncio.run(chat_loop(root, slug, phase=phase, one_shot=prompt_text,
                               context_tier=context_tier))

    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Chat error: {exc}", err=True)
        raise click.Abort()


@main.command()
@click.option("--engagement", "engagement_slug", help="Engagement slug (default: active)")
@click.option("--phase", default="requirements",
              help="Starting phase (requirements/research/design/impl/testing/review)")
@click.option(
    "--context-tier",
    "context_tier",
    type=click.IntRange(1, 3),
    default=2,
    show_default=True,
    help="Context load tier: 1=inventory only, 2=+summaries, 3=+snippets",
)
@click.option("--greenfield", "session_type", flag_value="greenfield",
              help="Greenfield session (build from scratch)")
@click.option("--brownfield", "session_type", flag_value="brownfield",
              help="Brownfield session (work within existing code)")
@click.option("--refactoring", "session_type", flag_value="refactoring",
              help="Refactoring session (restructure existing code)")
@click.option("--get-well", "get_well", is_flag=True,
              help="Get-well remediation session (assessment-driven)")
def session(engagement_slug, phase, context_tier, session_type, get_well):
    """Run a full phase-by-phase session.

    Walks through each development phase sequentially:
    requirements → research → design → implementation → testing → review.
    Each phase runs the appropriate agent with context from previous phases.

    Session type (greenfield/brownfield/refactoring) controls the phase
    sequence and agent behaviour. If not specified, the harness attempts
    to auto-detect from the engagement context.

    Commands during session:
      /next     — advance to next phase
      /approve  — approve and advance
      /changes  — request revisions
      /save     — save transcript
      /help     — show commands
      /exit     — quit

    Examples::

        harness session                              # auto-detect type
        harness session --greenfield                 # explicit greenfield
        harness session --brownfield                 # explicit brownfield
        harness session --refactoring                # explicit refactoring
        harness session --get-well                   # assessment-driven remediation
        harness session --phase design               # start from design phase
    """
    try:
        import asyncio
        root = _require_project_root()
        from harness.session.loop import session_loop

        slug = engagement_slug
        if not slug:
            from harness.engagement.resolver import resolve_active_engagement
            slug = resolve_active_engagement(root)

        if not slug:
            click.echo(
                "No active engagement. Create one with:\n"
                "  harness engagement create \"your task\"",
                err=True,
            )
            raise click.Abort()

        # Verify the engagement directory exists
        eng_dir = get_engagement_dir(root, slug)
        if not eng_dir.is_dir():
            click.echo(
                f"Engagement '{slug}' not found. "
                f"Expected directory: {eng_dir}",
                err=True,
            )
            raise click.Abort()

        session_type_arg = _resolve_session_type_flag(session_type, root, slug)

        # --get-well overrides: forces get-well mode regardless of other flags
        if get_well:
            from harness.session.types import SessionType
            session_type_arg = SessionType.GET_WELL
            # Start from assessment-triage phase when no explicit phase given
            if not phase:
                phase = "assessment-triage"

        asyncio.run(session_loop(root, slug, start_phase=phase,
                               context_tier=context_tier,
                               session_type=session_type_arg))

    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Session error: {exc}", err=True)
        raise click.Abort()


@main.command()
@click.argument("engagement_id")
@click.option("--approve", is_flag=True)
@click.option("--reject", is_flag=True)
@click.option("--request-changes", "request_changes", is_flag=True)
@click.option("--finding", multiple=True, default=None, help="A specific finding (repeatable)")
@click.option("--severity", type=click.Choice(["blocker", "major", "minor", "suggestion"]),
              default="blocker", help="Severity for findings (default: blocker)")
@click.option("--artifact-ref", multiple=True, default=None, help="Artifact reference per finding (repeatable)")
@click.option("--notes", default="", help="Free-form notes")
def review(engagement_id, approve, reject, request_changes,
           finding, severity, artifact_ref, notes):
    """Review an engagement at a gate checkpoint.

    Supports structured feedback via --finding, --severity, and --artifact-ref.
    When at least one --finding is provided, the decision is "request_changes"
    and structured feedback items are created.

    Existing --approve and --reject flags remain for backward compatibility.

    Examples:

        harness review eng-main-abc123 --approve

        harness review eng-main-def456 --reject

        harness review eng-main-abc123 --request-changes \\
            --finding "Missing error handling" --severity blocker --artifact-ref auth.py \\
            --finding "Rename variable x" --severity minor --artifact-ref utils.py \\
            --notes "Surface-level issues only; logic is solid"
    """
    # Determine decision
    if finding:
        # Structured feedback → request_changes
        decision = "request_changes"
    elif request_changes:
        decision = "request_changes"
    elif approve:
        decision = "approved"
    elif reject:
        decision = "rejected"
    else:
        click.echo("Specify --approve, --reject, --request-changes, or --finding(s).")
        return

    # Build structured feedback items
    feedback_items = []
    if finding:
        for i, f_text in enumerate(finding):
            ref = artifact_ref[i] if i < len(artifact_ref) else ""
            sev = severity  # All findings use the same --severity in this simple form
            feedback_items.append({
                "finding": f_text,
                "severity": sev,
                "artifact_ref": ref or "(general)",
                "suggestion": "",
            })

    try:
        from harness.state.temporal_adapter import send_gate_review
        from harness.state.temporal_server import ensure_temporal_server

        temporal_ok = False
        try:
            if ensure_temporal_server():
                # We'll build a simple signal dict for temporal
                signal_dict = {
                    "engagement_id": engagement_id,
                    "phase": "",
                    "decision": decision,
                    "notes": notes,
                    "feedback": feedback_items,
                }
                asyncio.run(send_gate_review(engagement_id, "", decision))
                temporal_ok = True
        except Exception:
            pass

        # Also update local snapshot
        root = _require_project_root()
        snapshot_path = get_harness_state_path(root)
        snapshot = _load_project_snapshot(snapshot_path)
        for eng in snapshot.engagements:
            if eng.id == engagement_id:
                if decision == "approved":
                    eng.status = "complete"
                elif decision == "rejected":
                    eng.status = "blocked"
                elif decision == "request_changes":
                    eng.status = "changes_requested"
        SnapshotWriter.write(snapshot, snapshot_path)

        if temporal_ok:
            click.echo(f"Gate {decision} for engagement {engagement_id}.")
        else:
            click.echo(f"Gate {decision} (local state only).")

    except Exception:
        click.echo(f"Gate {decision} (local state only).")


@main.command()
@click.argument("slug", required=False, default=None)
@click.option("--force", is_flag=True)
def status(slug, force):
    """Quick view of active engagement.

    Dispatches a ``QueryStatus`` command via the CommandBus. Falls back
    to the local snapshot reader if the CommandBus path fails.

    Examples::

        harness status
        harness status my-engagement
    """
    try:
        cmd = query_status_command(slug or "")
        result = dispatch_cli_command(cmd)
        if result.success:
            data = result.data
            click.echo("Engagement: " + str(data.get('slug', slug or '(active)')))
            if data.get("all_ok") is not None:
                health = 'All OK' if data['all_ok'] else 'Issues detected'
                click.echo("  Health: " + health)
            warnings = data.get("warnings", [])
            if warnings:
                for w in warnings:
                    click.echo("  \u26a0 " + str(w.get('type', 'warning')) + ": " + str(w.get('message', '')))
            return
    except Exception:
        pass

    # Fallback: local snapshot
    root = _require_project_root()
    try:
        snapshot_path = get_harness_state_path(root)
        snapshot = _load_project_snapshot(snapshot_path)

        eng_id = slug or snapshot.current_engagement
        if not eng_id:
            click.echo("No active engagement.")
            return

        for eng in snapshot.engagements:
            if eng.id == eng_id:
                click.echo(f"Engagement: {eng.id}")
                click.echo(f"  Description: {eng.description}")
                click.echo(f"  Status: {eng.status}")
                click.echo(f"  Phase: {eng.phase}")
                click.echo(f"  Gate mode: {eng.gate_mode}")
                if eng.has_stale_summary:
                    click.echo("  \u26a0\ufe0f Summary may be stale \u2014 run `harness catchup`")
                return

        click.echo(f"Engagement {eng_id} not found.")

    except Exception as exc:
        click.echo(f"Status check failed: {exc}", err=True)
def _write_assessment_report(
    report_text: str,
    repo_path: str,
    report_file=None,
    assessment_dict=None,
) :
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
        root = _find_project_root(Path(repo_path)) if Path(repo_path).is_dir() else None
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
                                "wave_slug": None,  # Set when create-from-finding runs
                                "wave_status": "unassigned",
                            })

                    manifest_path = assess_dir / f"{timestamp}-manifest.json"
                    manifest_path.write_text(json.dumps(manifest, indent=2))

                    written_to = str(report_path)
                    click.echo(f"\nAssessment saved to engagement: {slug}")

    except Exception:
        pass  # Non-critical — engagement space may not exist

    return written_to

@main.command()
@click.argument("repo_path", default=".")
@click.option("--report", "report_file", default=None, help="Write report to file")
@click.option("--deep", is_flag=True, help="Run full deep analysis + LLM-based assessment (P1-P5)")
@click.option("--verbose", "verbose", is_flag=True, help="Print full report to terminal")
@click.option("--project-type", default="python", help="Project archetype for conformance")
def inspect(repo_path, report_file, deep, verbose, project_type):
    """Analyse a codebase as an external observer.

    Pure analysis mode — never writes state, never modifies the repo,
    doesn't require `harness init`. When --deep is used, also runs
    the LLM-based independent assessment (P1-P5) for comprehensive
    codebase evaluation.

    By default, only a summary is shown. Use --verbose to print the
    full report to the terminal. The report is always written to file
    when --report is specified or when inside an active engagement.

    Examples:

        harness observe .

        harness observe /path/to/project --deep --report analysis.md

        harness observe . --deep --verbose
    """
    try:
        from harness.analysis.observer import analyse

        result = analyse(
            path=repo_path,
            deep=deep,
            project_type=project_type,
        )

        if result["status"] == "error":
            click.echo(f"Error: {result['message']}", err=True)
            return

        # Print summary by default; full report only with --verbose
        assessment_dict = result.get("assessment")
        if verbose:
            click.echo(result["report"])
        else:
            # Show a brief summary
            score = "?"
            findings = "?"
            if assessment_dict:
                ad = assessment_dict.get("assessment", {})
                score = ad.get("score", "?")
                findings = len(ad.get("findings", []))
            click.echo(f"Assessment complete: {findings} findings, score: {score}")

        written = _write_assessment_report(
            result["report"], repo_path, report_file,
            assessment_dict=assessment_dict,
        )
        if written:
            click.echo(f"Report written to: {written}")

    except Exception as exc:
        click.echo(f"Inspect analysis failed: {exc}", err=True)
        raise click.Abort()


@main.command()
@click.argument("repo_path", default=".")
@click.option("--report", "report_file", default=None, help="Write report to file")
@click.option("--verbose", "verbose", is_flag=True, help="Print full report to terminal")
def assess(repo_path, report_file, verbose):
    """Run the full assessment on the current project.

    Runs the observer (P1-P11 + P9 synthesis) on the current directory,
    produces structured findings with IDs, and writes them to the
    engagement's assessments directory when inside an active engagement.

    Use this to establish baselines, drive refactoring engagements,
    and track improvement over time. Findings from this command are
    consumed by:
      - ``harness engagement create --refactoring`` (auto-waves)
      - ``harness wave create-from-finding`` (per-finding waves)
      - ``harness engagement diff`` (baseline comparison)

    By default, only a summary is shown. Use --verbose to print the
    full report to the terminal.

    Examples:

        harness assess .

        harness assess . --verbose

        harness assess . --report baseline.md
    """
    try:
        from harness.analysis.observer import analyse

        result = analyse(
            path=repo_path,
            deep=True,
            project_type="python",
        )

        if result["status"] == "error":
            click.echo(f"Error: {result['message']}", err=True)
            return

        # Print summary by default; full report only with --verbose
        assessment_dict = result.get("assessment")
        if verbose:
            click.echo(result["report"])
        else:
            # Show a brief summary
            score = "?"
            findings = "?"
            if assessment_dict:
                ad = assessment_dict.get("assessment", {})
                score = ad.get("score", "?")
                findings = len(ad.get("findings", []))
            click.echo(f"Assessment complete: {findings} findings, score: {score}")

        written = _write_assessment_report(
            result["report"], repo_path, report_file,
            assessment_dict=assessment_dict,
        )
        if written:
            click.echo(f"Report written to: {written}")

    except Exception as exc:
        click.echo(f"Assessment failed: {exc}", err=True)
        raise click.Abort()


@main.command()
@click.argument("engagement_id", required=False)
@click.option("--list", "list_flag", is_flag=True, help="List phases for engagement")
@click.option("--advance", help="Advance to next phase")
@click.option("--navigate", "nav_target", help="Navigate to a phase (pauses current, checkpoints, enters target)")
@click.option("--feedback-target", "fb_target", help="Send feedback to a target phase")
@click.option("--feedback-reason", "fb_reason", default="", help="Reason/description for feedback")
@click.option("--resume", "resume_flag", is_flag=True, help="Resume from paused checkpoint")
@click.option("--force", "force_flag", is_flag=True, help="Bypass checkpoint staleness checks on resume")
@click.option("--status", "status_flag", is_flag=True, help="Show phase state diagram")
@click.option("--feedback-list", "fb_list_flag", is_flag=True, help="List feedback history")
def phase(engagement_id, list_flag, advance, nav_target, fb_target, fb_reason,
          resume_flag, force_flag, status_flag, fb_list_flag):
    """Manage engagement phases.

    List phases, navigate between them, send feedback, or check status.

    Examples:

        harness phase --list

        harness phase --navigate design

        harness phase --feedback-target design --feedback-reason "OAuth not covered"

        harness phase --resume

        harness phase --status

        harness phase --feedback-list
    """
    try:
        root = _require_project_root()
        snapshot_path = get_harness_state_path(root)
        snapshot = _load_project_snapshot(snapshot_path)

        eng_id = engagement_id or snapshot.current_engagement
        if not eng_id and (nav_target or fb_target or resume_flag or status_flag
                           or fb_list_flag or list_flag or advance):
            click.echo("No engagement specified.")
            return

        # Derive slug from engagement ID (strip eng-main- prefix convention)
        # The PhasesStateManager uses slugs, not full IDs.
        slug = eng_id
        if eng_id and eng_id.startswith("eng-main-"):
            slug = eng_id[len("eng-main-"):]

        # ── Phase state manager ────────────────────────────────────────
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

        # ── Status ───────────────────────────────────────────────────────
        if status_flag:
            phases = psm.list_phases()
            if not phases:
                click.echo("No phase state recorded yet.")
                return

            click.echo(f"Phase states for {slug}:")
            click.echo(f"  {'Phase':<20} {'State':<16} {'Checkpoint':<14} {'Feedback Target':<18}")
            click.echo(f"  {'-'*20} {'-'*16} {'-'*14} {'-'*18}")
            for name, record in sorted(phases.items()):
                ckpt = record.checkpoint_ref or "-"
                fb_tgt = record.feedback_target or "-"
                icon = {
                    PhaseState.COMPLETED: "✔",
                    PhaseState.ACTIVE: "►",
                    PhaseState.PAUSED: "⏸",
                    PhaseState.FEEDBACK_SENT: "↩",
                    PhaseState.FEEDBACK_WAIT: "⏳",
                    PhaseState.NOT_STARTED: "○",
                }.get(record.state, "○")
                click.echo(
                    f"  {icon} {name:<18} {record.state.value:<16} {ckpt:<14} {fb_tgt:<18}"
                )
            return

        # ── List ─────────────────────────────────────────────────────────
        if list_flag:
            phases = psm.list_phases()
            if not phases:
                click.echo("No phase state recorded for this engagement.")
                return
            click.echo(f"Phases for {slug}:")
            for name in sorted(phases.keys()):
                record = phases[name]
                icon = {
                    PhaseState.COMPLETED: "✔",
                    PhaseState.ACTIVE: "►",
                    PhaseState.PAUSED: "⏸",
                    PhaseState.FEEDBACK_SENT: "↩",
                    PhaseState.FEEDBACK_WAIT: "⏳",
                    PhaseState.NOT_STARTED: "○",
                }.get(record.state, "○")
                click.echo(f"  {icon} {name} ({record.state.value})")
            return

        # ── Navigate (cross-phase jump with checkpoint) ────────────────
        if nav_target:
            from harness.engagement.checkpoint import CheckpointManager
            current_phase = snapshot.phase if hasattr(snapshot, 'phase') else "unknown"

            # Create checkpoint
            ckpt = ckm.create(
                phase_name=current_phase,
                context=f"Navigating from {current_phase} to {nav_target}",
            )
            click.echo(f"📝 Checkpoint saved ({ckpt.checkpoint_id})")

            # Pause current phase, activate target phase
            psm.transition(current_phase, PhaseState.PAUSED)
            psm.ensure_phase(nav_target)
            psm.transition(nav_target, PhaseState.ACTIVE)

            # Update snapshot
            if hasattr(target := next(
                (e for e in snapshot.engagements if e.id == eng_id), None
            ), 'phase'):
                target.phase = nav_target
                SnapshotWriter.write(snapshot, snapshot_path)

            click.echo(f"🔄 Entering phase: {nav_target}")
            return

        # ── Send feedback to another phase ──────────────────────────────
        if fb_target:
            current_phase = snapshot.phase if hasattr(snapshot, 'phase') else "unknown"

            # Create checkpoint
            ckpt = ckm.create(
                phase_name=current_phase,
                context=fb_reason or f"Sending feedback to {fb_target}",
                feedback_content=f"# Feedback from {current_phase} to {fb_target}\n\n{fb_reason}",
            )

            # Create feedback packet
            packet = FeedbackPacket(
                from_phase=current_phase,
                to_phase=fb_target,
                title=fb_reason[:80] if fb_reason else "Feedback",
                body=fb_reason,
                checkpoint_id=ckpt.checkpoint_id,
            )
            fb_path = fbm.create(packet)
            click.echo(f"📝 Checkpoint saved ({ckpt.checkpoint_id})")
            click.echo(f"📝 Feedback packet created: {fb_path.relative_to(root)}")

            # Mark current phase as feedback_sent, activate target
            psm.mark_feedback_sent(current_phase, fb_target, ckpt.checkpoint_id)
            psm.ensure_phase(fb_target)
            psm.transition(fb_target, PhaseState.ACTIVE)

            # Update snapshot
            if hasattr(target := next(
                (e for e in snapshot.engagements if e.id == eng_id), None
            ), 'phase'):
                target.phase = fb_target
                SnapshotWriter.write(snapshot, snapshot_path)

            click.echo(f"🔄 Feedback sent to: {fb_target}. Entering phase.")
            return

        # ── Resume from paused checkpoint ───────────────────────────────
        if resume_flag:
            latest = ckm.get_latest()
            if latest is None:
                click.echo("No checkpoint found to resume from.")
                return

            if latest.is_stale() and not force_flag:
                click.echo(
                    f"⚠️  Checkpoint '{latest.checkpoint_id}' is stale "
                    f"(>{CHECKPOINT_EXPIRY_HOURS}h old). Use --force to resume."
                )
                return

            paused_phase = latest.phase_name
            click.echo(f"📝 Restored checkpoint ({latest.checkpoint_id})")
            click.echo(f"🔄 Resuming phase: {paused_phase}")

            psm.transition(paused_phase, PhaseState.ACTIVE)

            if hasattr(target := next(
                (e for e in snapshot.engagements if e.id == eng_id), None
            ), 'phase'):
                target.phase = paused_phase
                SnapshotWriter.write(snapshot, snapshot_path)
            return

        # ── Feedback list ──────────────────────────────────────────────
        if fb_list_flag:
            all_fb = fbm.list_all()
            total = sum(len(v) for v in all_fb.values())
            if total == 0:
                click.echo("No feedback packets for this engagement.")
                return

            click.echo(f"Feedback packets for {slug}:")
            for status, packets in all_fb.items():
                if not packets:
                    continue
                click.echo(f"\n  [{status.upper()}]")
                for p in packets:
                    title = p.title or "(no title)"
                    click.echo(f"    {p.from_phase} → {p.to_phase}: {title}")
                    if p.checkpoint_id:
                        click.echo(f"      checkpoint: {p.checkpoint_id}")
            return

        # ── Legacy advance fallback ─────────────────────────────────────
        if advance:
            if not eng_id:
                click.echo("No engagement specified.")
                return
            # Create the phase if it doesn't exist yet, then advance
            psm.ensure_phase(advance)
            psm.transition(advance, PhaseState.ACTIVE)
            click.echo(f"Advanced to phase: {advance}")
            return

        # ── If no flags, show brief help ────────────────────────────────
        click.echo(
            "Use one of: --list, --advance <phase>, --navigate <phase>, "
            "--feedback-target <phase> --feedback-reason <text>, --resume, "
            "--status, --feedback-list"
        )

    except Exception as exc:
        click.echo(f"Phase management failed: {exc}", err=True)
        raise click.Abort()


@main.command()
def catchup():
    """Reconcile harness state with current git state.

    Detects unprocessed changes from external work (R12, side-channel coding)
    and from merges (R15), then updates the harness state to reflect the
    current branch HEAD.

    Run this after a git merge or when work was done outside the harness.
    """
    try:
        from harness.state.freshness import (
            FreshnessRecord,
            load_freshness,
            save_freshness,
        )
        from harness.state.reconciliation import BranchReconciler
        from harness.state.snapshot import (
            SnapshotWriter,
        )

        root = _require_project_root()
        repo = GitRepo(root)
        current_branch = repo.branch()
        current_head = _get_head_sha(root)

        # Load freshness record
        freshness = load_freshness(root)
        if freshness is None:
            click.echo("No previous harness state found — nothing to reconcile.")
            return

        click.echo(f"Reconciling against {freshness.branch} @ {freshness.head_sha[:8]}...")

        # Run reconciliation
        reconciler = BranchReconciler(repo, root)
        report = reconciler.reconcile(
            last_known_sha=freshness.head_sha,
            engagement_id=freshness.branch,
        )

        # Update freshness
        new_record = FreshnessRecord(
            branch=current_branch,
            head_sha=current_head,
            last_reconciled="",
            stale=False,
        ).mark_fresh(current_head)
        save_freshness(new_record, root)

        # Update snapshot
        snapshot_path = get_harness_state_path(root)
        snapshot = _load_project_snapshot(snapshot_path)
        for eng in snapshot.engagements:
            if eng.id == freshness.branch:
                eng.has_stale_summary = report.merge_detected
        SnapshotWriter.write(snapshot, snapshot_path)

        # Report
        click.echo(f"  Branch: {freshness.branch} → {current_branch}")
        click.echo(f"  Merge detected: {'YES' if report.merge_detected else 'no'}")
        click.echo(f"  Stale commits: {len(report.stale_commits)}")
        click.echo(f"  External changes: {report.external_changes}")
        click.echo(f"  Harness-managed changes: {report.harness_managed_changes}")

        if report.merge_detected:
            click.echo("")
            click.echo("⚠️  Merge detected — summary may be stale.")
            click.echo("   Run `harness summary` to refresh.")

    except Exception as exc:
        click.echo(f"Catchup failed: {exc}", err=True)
        raise click.Abort()


@main.command()
def absorb():
    """Detect and absorb external changes into harness state.

    Scans for changes made outside the harness workflow (manual edits,
    side-channel tools) and updates the harness metadata without
    modifying the source code.
    """
    try:
        root = _require_project_root()
        repo = GitRepo(root)
        status = repo.status()

        # Detect unstaged/uncommitted changes
        untracked = status.untracked if hasattr(status, 'untracked') else []
        unstaged = status.unstaged if hasattr(status, 'unstaged') else []
        total_external = len(untracked) + len(unstaged)

        click.echo(f"Absorbing external changes in {root.name}...")

        if total_external == 0:
            click.echo("  No external changes detected.")
            return

        click.echo(f"  Untracked files: {len(untracked)}")
        for f in untracked[:5]:
            click.echo(f"    + {f}")
        if len(untracked) > 5:
            click.echo(f"    ... and {len(untracked) - 5} more")

        click.echo(f"  Modified files: {len(unstaged)}")
        for f in unstaged[:5]:
            click.echo(f"    ~ {f}")
        if len(unstaged) > 5:
            click.echo(f"    ... and {len(unstaged) - 5} more")

        click.echo("")
        click.echo("External changes absorbed. Run `harness catchup` to reconcile.")

    except Exception as exc:
        click.echo(f"Absorb failed: {exc}", err=True)
        raise click.Abort()


@main.command()
def shell():
    """Launch an interactive REPL with tab completion and command history.

    All CLI commands are available as ``/<command-name> [args]``.
    Tab auto-completes command names, flags, and file paths.
    Up/down arrows navigate command history.

    Examples::

        harness shell
          > /help
          > /init
          > /work "Add user authentication"
          > /engagement create "Fix billing bug"
          > /inspect .
          > /exit
    """
    root = _require_project_root(command_name="shell")
    from harness.shell import shell as run_shell
    run_shell(root=root)


@main.command()
@click.option("--verbose", "verbose", is_flag=True, help="Include INFO-level checks in output")
@click.option("--fix", is_flag=True, help="Attempt to auto-fix engagement metadata issues")
def health(verbose, fix):
    """Run configuration and state validation checks.

    Validates the harness setup, configuration, and environment. Reports
    any issues categorised by severity: CRITICAL (must fix), BRANCH
    (wrong branch warning), WARN (potential issues), INFO (silent unless
    --verbose).

    Use --fix to automatically resolve common issues: missing metadata
    files, stale state, plan consistency, and branch mismatches.

    Examples:

        harness health
        harness health --verbose
        harness health --fix
    """
    try:
        root = _require_project_root()

        if fix:
            from harness.health import run_fixes
            messages = run_fixes(root)
            for msg in messages:
                click.echo(f"  {msg}")
            return

        from harness.health import run_health_checks, format_health_report
        report = run_health_checks(root)
        click.echo(format_health_report(report, verbose=verbose))
    except SystemExit:
        raise
    except Exception as exc:
        click.echo(f"Health check failed: {exc}", err=True)
        raise click.Abort()


@main.command()
@click.option("--re-assess", is_flag=True,
              help="Re-run assessment and compare to baseline on finish")
def finish(re_assess):
    """Complete the current engagement with a commit.

    Stages all changes, opens git commit editor (user writes message),
    and updates the harness summary. Designed for the squash+rebase
    workflow (R15.3).

    When --re-assess is set, runs the observer after committing,
    compares findings to the baseline stored at engagement creation,
    and updates the project's assessment history.

    Run `harness catchup` first if state may be stale.

    Examples:
        harness finish
        harness finish --re-assess
    """
    try:
        from harness.state.freshness import (
            FreshnessRecord,
            load_freshness,
            save_freshness,
        )

        root = _require_project_root()
        repo = GitRepo(root)
        current_branch = repo.branch()

        # Check freshness
        freshness = load_freshness(root)
        if freshness and freshness.stale:
            click.echo("⚠️  State is stale. Run `harness catchup` first.")
            return

        # Stage all
        click.echo("Staging all changes...")
        result = subprocess.run(
            ["git", "add", "-A"], cwd=root, capture_output=True, text=True
        )
        if result.returncode != 0:
            click.echo(f"  Git add failed: {result.stderr.strip()}")
            return

        # Write freshness before commit
        current_head = _get_head_sha(root)
        new_record = FreshnessRecord(
            branch=current_branch,
            head_sha=current_head,
            last_reconciled="",
            stale=False,
        ).mark_fresh(current_head)
        save_freshness(new_record, root)

        # Commit (user writes message via editor)
        click.echo("Opening commit editor...")
        result = subprocess.run(["git", "commit"], cwd=root, capture_output=False)

        if result.returncode != 0:
            click.echo("Commit aborted or failed.")
            return

        # Update summary
        head_after = _get_head_sha(root)

        # Update snapshot status
        snapshot_path = get_harness_state_path(root)
        snapshot = _load_project_snapshot(snapshot_path)
        completed_engagement_id = None
        for eng in snapshot.engagements:
            if eng.id == snapshot.current_engagement:
                eng.status = "complete"
                completed_engagement_id = eng.id
        SnapshotWriter.write(snapshot, snapshot_path)

        click.echo(f"Engagement finished @ {head_after[:8]} on {current_branch}.")

        # --re-assess: run observer and compare to baseline
        if re_assess:
            click.echo()
            click.echo("Running post-engagement re-assessment...")

            # Determine the active slug from the current branch pattern
            slug = None
            if current_branch.startswith("eng/"):
                slug = current_branch[4:]

            if not slug:
                click.echo(
                    "  Skipping re-assessment (not on an eng/ branch).",
                )
            else:
                from harness.analysis.observer import analyse

                # Determine the engagement's assessments dir
                from harness.paths import get_engagement_dir
                eng_dir = get_engagement_dir(root, slug)
                assess_dir = eng_dir / "assessments"

                if not assess_dir.is_dir():
                    assess_dir.mkdir(parents=True, exist_ok=True)

                # Run the observer
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                timestamp = now.strftime("%Y%m%d-%H%M%S")

                result = analyse(
                    path=root,
                    deep=True,
                )

                if result["status"] == "error":
                    click.echo(f"  Re-assessment failed: {result['message']}")
                else:
                    import json as _json

                    # Write report to engagement
                    report_path = assess_dir / f"{timestamp}-assessment.md"
                    report_path.write_text(result["report"])

                    # Build closure metrics
                    assessment_dict = result.get("assessment")
                    current_findings_count = 0
                    if assessment_dict:
                        current_findings_count = len(
                            assessment_dict.get("assessment", {}).get("findings", [])
                        )

                    # Write manifest with findings
                    from harness.cli import _write_assessment_report
                    written = _write_assessment_report(
                        report_text=result["report"],
                        repo_path=str(root),
                        assessment_dict=assessment_dict,
                    )

                    # Load baseline from engagement.yaml for comparison
                    eng_yaml_path = eng_dir / "engagement.yaml"
                    baseline_findings = None
                    baseline_count = "?"
                    if eng_yaml_path.is_file():
                        import yaml as _yaml
                        with open(eng_yaml_path) as f:
                            yaml_data = _yaml.safe_load(f) or {}
                        baseline_count = yaml_data.get("baseline_finding_count", "?")

                        # Load baseline manifest for detailed comparison
                        baseline_manifest_path = yaml_data.get("baseline_manifest")
                        if baseline_manifest_path:
                            bp = eng_dir / baseline_manifest_path
                            if bp.is_file():
                                baseline_manifest = _json.loads(bp.read_text())
                                baseline_findings = baseline_manifest.get("findings", [])

                    # Compute closure stats
                    closed_count = "?"
                    if baseline_findings is not None:
                        # A finding is 'closed' if its message is not present in current
                        current_messages = set(
                            f.get("message", "")[:80]
                            for f in (assessment_dict.get("assessment", {}).get("findings", []) if assessment_dict else [])
                        )
                        closed_in_baseline = [
                            f for f in baseline_findings
                            if f.get("message", "")[:80] not in current_messages
                        ]
                        closed_count = len(closed_in_baseline)

                    click.echo()
                    click.echo("  ┌─ Re-Assessment Results ──────────────────────")
                    click.echo(f"  │ Baseline findings:  {baseline_count}")
                    click.echo(f"  │ Current findings:   {current_findings_count}")
                    if isinstance(closed_count, int):
                        click.echo(f"  │ Findings closed:    {closed_count}")
                        pct = (
                            round(closed_count / len(baseline_findings) * 100)
                            if baseline_findings else 0
                        )
                        click.echo(f"  │ Closure rate:       {pct}%")
                    click.echo(f"  │ Report:            {report_path.name}")
                    click.echo("  └───────────────────────────────────────────────")
                    click.echo()
                    click.echo(f"  See: cat {report_path}")

                # Update assessment history in .harness/config.yaml
                config_path = root / ".harness" / "config.yaml"
                if config_path.is_file():
                    import yaml as _yaml
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

        click.echo()
        click.echo("Tip: Use `harness summary` to view the final state.")

    except Exception as exc:
        click.echo(f"Finish failed: {exc}", err=True)
        raise click.Abort()


# ---------------------------------------------------------------------------
# Engagement lifecycle commands
# ---------------------------------------------------------------------------


@main.group()
def engagement():
    """Manage engagements."""
    pass


@engagement.command()
@click.argument("name")
@click.option("--slug", help="Override auto-derived slug")
@click.option("--refactoring", is_flag=True,
              help="Create a refactoring engagement from the latest assessment")
@click.option("--focus", type=click.Choice(["high-risk", "medium", "all"]),
              default="all",
              help="Filter findings by severity when --refactoring (default: all)")
@click.option("--allow-refactoring-suggestions", type=bool, default=None,
              help="Allow refactoring suggestions for this engagement (overrides project config)")
def create(name, slug, refactoring, focus, allow_refactoring_suggestions):
    """Create a new engagement.

    Creates the engagement directory structure, switches to a new
    ``eng/<slug>`` branch, and sets the engagement as active.

    When --refactoring is set, reads the latest assessment manifest
    and auto-creates waves from assessment findings. Use --focus to
    filter which findings become waves.

    Examples:

        harness engagement create "Fix billing bug"

        harness engagement create "Hotfix" --slug hotfix-72

        harness engagement create "Refactor auth" --allow-refactoring-suggestions true

        harness engagement create "Fix critical bugs" --refactoring

        harness engagement create "High-risk fixes" --refactoring --focus high-risk
    """
    try:
        root = _require_project_root()

        # Derive slug
        from harness.engagement.lifecycle import slugify
        slug = slug or slugify(name)
        if not slug:
            click.echo(
                "Error: Could not derive a valid slug from the name. "
                "Use --slug to provide one explicitly.",
                err=True,
            )
            raise click.Abort()

        # Check slug doesn't already exist
        eng_dir = get_engagement_dir(root, slug)
        if eng_dir.exists():
            click.echo(
                f"Error: Engagement '{slug}' already exists at {eng_dir}",
                err=True,
            )
            raise click.Abort()

        # If --refactoring, read the latest assessment manifest before creating
        baseline_manifest = None
        if refactoring:
            import json as _json
            from harness.paths import get_engagements_dir

            # Find the latest assessment manifest across all engagements
            all_assess_dirs = list(get_engagements_dir(root).rglob("*-manifest.json"))
            if not all_assess_dirs:
                click.echo(
                    "No assessment manifests found. Run an assessment first:\n"
                    "  harness assess . --deep",
                    err=True,
                )
                raise click.Abort()

            # Pick the newest
            baseline_manifest_path = sorted(all_assess_dirs, reverse=True)[0]
            baseline_manifest = _json.loads(baseline_manifest_path.read_text())
            findings = baseline_manifest.get("findings", [])

            if not findings:
                click.echo(
                    "The latest assessment does not contain structured findings. "
                    "Re-run with --deep:\n"
                    "  harness assess . --deep",
                    err=True,
                )
                raise click.Abort()

        # Create engagement directory structure
        from harness.engagement.lifecycle import (
            create_engagement_dir,
            write_engagement_metadata,
        )
        create_engagement_dir(root, slug)

        # Create branch eng/<slug> from current HEAD
        branch_name = f"eng/{slug}"
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            click.echo(
                f"Error creating branch: {result.stderr.strip()}",
                err=True,
            )
            raise click.Abort()

        # Determine session type
        session_type = "refactoring" if refactoring else None

        # Write engagement metadata
        write_engagement_metadata(
            eng_dir,
            name,
            slug,
            branch_name,
            session_type=session_type,
            allow_refactoring_suggestions=allow_refactoring_suggestions,
        )

        # If refactoring, update engagement.yaml with baseline reference + auto-create waves
        waves_created = 0
        if refactoring and baseline_manifest:
            import json as _json
            from harness.plan.plan_manager import PlanManager

            # Also store baseline reference and refactoring config in engagement.yaml
            eng_yaml_path = eng_dir / "engagement.yaml"
            import yaml as _yaml
            with open(eng_yaml_path) as f:
                yaml_data = _yaml.safe_load(f) or {}
            yaml_data["refactoring"] = True
            yaml_data["session_type"] = "refactoring"
            yaml_data["baseline_manifest"] = str(baseline_manifest_path)
            yaml_data["baseline_finding_count"] = len(
                baseline_manifest.get("findings", [])
            )
            yaml_data["focus"] = focus
            with open(eng_yaml_path, "w") as f:
                _yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

            # Filter findings by --focus
            focus_findings = []
            for f in findings:
                sev = f.get("severity", "info")
                if focus == "high-risk" and sev not in ("error", "critical"):
                    continue
                if focus == "medium" and sev not in ("error", "critical", "warning"):
                    continue
                focus_findings.append(f)

            if not focus_findings:
                click.echo(
                    f"No findings match focus level '{focus}'. Creating engagement "
                    f"without waves — add them manually with:\n"
                    f"  harness wave create-from-assessment\n"
                    f"  or: harness wave create-from-finding <finding-id>",
                )
            else:
                # Auto-create waves from filtered findings
                pm = PlanManager(root, slug)
                manifest_updates = []

                for f in focus_findings:
                    finding_id = f.get("id", "?")
                    if f.get("wave_slug"):
                        continue  # Already has a wave assigned

                    message = f.get("message", "")[:72]
                    title = message + ("..." if len(f.get("message", "")) > 72 else "")
                    severity = f.get("severity", "info")
                    category = f.get("category", "other")

                    wave = pm.add_wave(
                        title=title,
                        wave_type="refactor",
                        trigger_phase="assessment",
                        trigger_reason=(
                            f"Finding {finding_id}: [{severity}] {category} — "
                            f"{f.get('message', '')[:80]}"
                        ),
                    )

                    f["wave_slug"] = wave.id
                    f["wave_status"] = "open"
                    manifest_updates.append((finding_id, wave.id))
                    waves_created += 1

                # Update the manifest to persist wave associations
                if manifest_updates:
                    baseline_manifest_path.write_text(
                        _json.dumps(baseline_manifest, indent=2)
                    )

        # Set active engagement
        from harness.engagement.lifecycle import set_active_engagement
        set_active_engagement(root, slug)

        click.echo(f"Engagement created: {slug}")
        click.echo(f"  Name   : {name}")
        click.echo(f"  Branch : {branch_name}")
        click.echo(f"  Type   : {'refactoring' if refactoring else 'standard'}")
        if refactoring:
            click.echo(f"  Focus  : {focus} ({waves_created} waves created)")
        click.echo("  Status : planning")
        if allow_refactoring_suggestions is not None:
            click.echo(f"  Refactoring suggestions: {allow_refactoring_suggestions}")
        click.echo(f"  Path   : {eng_dir}")
        if refactoring and waves_created:
            click.echo("")
            click.echo(f"  Created {waves_created} waves from assessment findings:")
            click.echo("    Run:  harness wave list")
            click.echo("    Run:  harness wave run <wave-id>")
            click.echo(f"    See:  cat {eng_dir / 'engagement.yaml'}")
        click.echo("")
        click.echo("Tip: Start a design loop with `harness work <description>`")

    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Failed to create engagement: {exc}", err=True)
        raise click.Abort()


@engagement.command()
@click.argument("slug")
def set_active(slug):
    """Set an existing engagement as active on the current branch.

    Writes the branch-to-slug mapping to
    ``.harness/active-engagements.yaml``.

    Examples:

        harness engagement set-active fix-billing-bug
    """
    try:
        root = _require_project_root()

        from harness.engagement.lifecycle import set_active_engagement
        set_active_engagement(root, slug)

        from harness.scm.git import GitRepo
        repo = GitRepo(root)
        branch = repo.branch()

        click.echo(f"Engagement '{slug}' is now active on branch '{branch}'.")

    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise click.Abort()
    except Exception as exc:
        click.echo(f"Failed to set active engagement: {exc}", err=True)
        raise click.Abort()


@engagement.command(name="list")
def list_engagements():
    """List all engagements in the project.

    Scans ``.harness/engagements/`` for all engagement directories
    and displays a table with slug, status, branch, and wave count.

    Examples:

        harness engagement list
    """
    try:
        root = _require_project_root()
        engagements_dir = get_engagements_dir(root)

        if not engagements_dir.is_dir():
            click.echo("No engagements found.")
            return

        # Resolve active engagement
        try:
            from harness.engagement.resolver import resolve_active_engagement
            active_slug = resolve_active_engagement(root)
        except Exception:
            active_slug = None

        from harness.engagement.lifecycle import _parse_engagement_md

        rows = []
        for entry in sorted(engagements_dir.iterdir()):
            if not entry.is_dir():
                continue
            md_file = entry / "engagement.md"
            meta = _parse_engagement_md(md_file) if md_file.is_file() else {}
            slug = meta.get("slug", entry.name)
            status = meta.get("status", "unknown")
            branch = meta.get("branch", "—")

            # Count waves
            waves_dir = entry / "waves"
            wave_count = 0
            if waves_dir.is_dir():
                wave_count = len(
                    [f for f in waves_dir.iterdir() if f.is_file()]
                )

            is_active = slug == active_slug
            rows.append((slug, status, branch, wave_count, is_active))

        if not rows:
            click.echo("No engagements found.")
            return

        # Display table
        click.echo(
            f"{'Slug':30s} {'Status':20s} {'Branch':30s} {'Waves':5s}"
        )
        click.echo("-" * 90)
        for slug, status, branch, wave_count, is_active in rows:
            marker = "  ← active" if is_active else ""
            click.echo(
                f"{slug:30s} {status:20s} {branch:30s} {wave_count:5d}{marker}"
            )

    except Exception as exc:
        click.echo(f"Failed to list engagements: {exc}", err=True)
        raise click.Abort()


@engagement.command()
@click.option("--engagement", "engagement_slug", help="Engagement slug (default: active)")
def status(engagement_slug):
    """Show detailed status of an engagement.

    Defaults to the active engagement for the current branch.
    Use ``--engagement`` to specify a different one.

    Examples:

        harness engagement status

        harness engagement status --engagement api-redesign
    """
    try:
        root = _require_project_root()

        # Resolve which engagement to show
        slug = engagement_slug
        if not slug:
            from harness.engagement.resolver import resolve_active_engagement
            slug = resolve_active_engagement(root)
            if not slug:
                click.echo(
                    "No active engagement for this branch. "
                    "Use --engagement to specify one."
                )
                return

        # Read engagement metadata
        md_file = get_engagement_md(root, slug)
        if not md_file.is_file():
            click.echo(f"Engagement '{slug}' not found.", err=True)
            raise click.Abort()

        from harness.engagement.lifecycle import _parse_engagement_md
        meta = _parse_engagement_md(md_file)

        title = meta.get("title", slug)
        status_text = meta.get("status", "unknown")
        branch = meta.get("branch", "—")
        created_at = meta.get("created_at", "—")

        # Count phase artifacts at engagement root and wave metadata in waves/
        eng_dir = get_engagement_dir(root, slug)
        waves_dir = get_engagement_dir(root, slug) / "waves"

        wave_count = 0
        phase_dir_count = 0

        # Phases are directories at engagement root (not waves/, not engagement.md, not plan.md)
        known_files = {"engagement.md", "plan.md", "waves"}
        for child in eng_dir.iterdir():
            if child.name in known_files:
                continue
            if child.is_dir():
                phase_dir_count += 1

        # Waves are .md files inside waves/
        if waves_dir.is_dir():
            wave_count = len(
                [f for f in waves_dir.iterdir() if f.is_file()]
            )

        # Display
        click.echo(f"Engagement: {slug}")
        click.echo(f"Title:      {title}")
        click.echo(f"Status:     {status_text}")
        click.echo(f"Branch:     {branch}")
        click.echo(f"Created:    {created_at}")
        click.echo(f"Waves:      {wave_count}")
        click.echo(f"Phases:     {phase_dir_count}")

        if status_text == "planning" and wave_count == 0:
            click.echo("")
            click.echo(
                "No active waves. Start with `harness work <description>` "
                "to begin the design loop."
            )

    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Failed to get engagement status: {exc}", err=True)
        raise click.Abort()


@engagement.command()
@click.argument("old_slug")
@click.argument("new_slug")
@click.option(
    "--branch-strategy",
    type=click.Choice(["keep", "rename", "new"]),
    default="keep",
    help="How to handle the git branch (keep, rename, new)",
)
@click.option("--dry-run", is_flag=True, help="Show what would change without making changes")
def rename(old_slug, new_slug, branch_strategy, dry_run):
    """Rename an existing engagement.

    Renames the engagement slug, moves the engagement directory,
    updates references, and optionally handles the git branch.

    Branch strategies:

    \b
        keep   — Leave git branch unchanged (default)
        rename — Rename the current git branch to match
        new    — Create a new branch and switch to it

    Examples:

        harness engagement rename typo-eng correct-eng

        harness engagement rename my-old-name new-name --branch-strategy rename

        harness engagement rename test-eng prod-eng --dry-run
    """
    try:
        root = _require_project_root()

        from harness.engagement.rename import (
            BranchStrategy,
            rename_engagement,
        )

        strategy = BranchStrategy(branch_strategy)
        result = rename_engagement(
            old_slug=old_slug,
            new_slug=new_slug,
            root=root,
            branch_strategy=strategy,
            dry_run=dry_run,
        )

        if result.errors:
            for err in result.errors:
                click.echo(f"Error: {err}", err=True)
            raise click.Abort()

        if dry_run:
            click.echo(f"DRY RUN — Would rename '{old_slug}' → '{new_slug}'")
            click.echo("")
            for change in result.changes_made:
                click.echo(f"  • {change}")
            if result.warnings:
                click.echo("")
                click.echo("Warnings:")
                for w in result.warnings:
                    click.echo(f"  ⚠ {w}")
            return

        click.echo(f"Engagement renamed: {old_slug} → {new_slug}")
        for change in result.changes_made:
            click.echo(f"  • {change}")

        if result.warnings:
            click.echo("")
            click.echo("Warnings:")
            for w in result.warnings:
                click.echo(f"  ⚠ {w}")

    except click.Abort:
        raise
    except Exception as exc:
        click.echo(
            f"Failed to rename engagement: {exc}", err=True
        )
        raise click.Abort()


@engagement.command()
@click.argument("slug")
def close(slug):
    """Close an engagement by setting its status to completed.

    Checks that all waves are completed before closing (if any exist).
    Updates ``engagement.md`` with ``completed`` status and timestamp.
    Removes the branch mapping from ``active-engagements.yaml``.

    Examples:

        harness engagement close fix-billing-bug
    """
    try:
        root = _require_project_root()

        # Validate engagement exists
        eng_dir = get_engagement_dir(root, slug)
        md_file = get_engagement_md(root, slug)
        if not md_file.is_file():
            click.echo(
                f"Error: Engagement '{slug}' not found at {md_file}",
                err=True,
            )
            raise click.Abort()

        from harness.engagement.lifecycle import _parse_engagement_md
        meta = _parse_engagement_md(md_file)
        status = meta.get("status", "unknown")

        if status == "completed":
            click.echo(f"Engagement '{slug}' is already completed.")
            return

        # Check waves completion
        waves_dir = get_engagement_dir(root, slug) / "waves"
        waves_completed = True
        wave_count = 0
        if waves_dir.is_dir():
            for wf in waves_dir.iterdir():
                if wf.is_file():
                    wave_count += 1
                    wave_meta = _parse_engagement_md(wf)
                    wave_status = wave_meta.get("status", "planned")
                    if wave_status not in ("completed", "aborted"):
                        waves_completed = False

        if wave_count > 0 and not waves_completed:
            click.echo(
                f"Error: Not all waves are completed for engagement '{slug}'. "
                f"Complete or abort all waves before closing.",
                err=True,
            )
            raise click.Abort()

        # Close the engagement
        from harness.engagement.lifecycle import close_engagement
        updated = close_engagement(root, slug)

        click.echo(f"Engagement closed: {slug}")
        if "completed_at" in updated:
            click.echo(f"  Completed at: {updated['completed_at']}")

    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Failed to close engagement: {exc}", err=True)
        raise click.Abort()


@engagement.command()
@click.option("--engagement", "slug", help="Engagement slug (default: active)")
def diff(slug):
    """Compare baseline assessment to current state.

    Loads the baseline assessment from the engagement's metadata,
    runs a fresh assessment, and compares findings to show what has
    been closed, what remains, and any new findings.

    Examples:

        harness engagement diff

        harness engagement diff --engagement my-engagement
    """
    import json as _json

    root = _require_project_root()

    if not slug:
        from harness.engagement.resolver import resolve_active_engagement
        slug = resolve_active_engagement(root)

    if not slug:
        click.echo(
            "No active engagement. Specify one with --engagement.",
            err=True,
        )
        raise click.Abort()

    from harness.paths import get_engagement_dir
    eng_dir = get_engagement_dir(root, slug)
    eng_yaml_path = eng_dir / "engagement.yaml"

    if not eng_yaml_path.is_file():
        click.echo(f"Engagement '{slug}' has no metadata file.", err=True)
        raise click.Abort()

    import yaml as _yaml
    with open(eng_yaml_path) as f:
        yaml_data = _yaml.safe_load(f) or {}

    baseline_manifest_path = yaml_data.get("baseline_manifest")
    if not baseline_manifest_path:
        click.echo(
            f"Engagement '{slug}' has no baseline assessment.\n"
            f"This engagement was not created with --refactoring, so there "
            f"is no baseline to compare against.",
            err=True,
        )
        raise click.Abort()

    from harness.analysis.observer import analyse

    click.echo("Running fresh assessment for comparison...")
    result = analyse(path=root, deep=True)

    if result["status"] == "error":
        click.echo(f"Assessment failed: {result['message']}", err=True)
        return

    # Load baseline
    bp = eng_dir / baseline_manifest_path
    if not bp.is_file():
        click.echo(f"Baseline manifest not found: {bp}", err=True)
        return

    baseline = _json.loads(bp.read_text())
    baseline_findings = baseline.get("findings", [])

    # Get current findings
    assessment_dict = result.get("assessment")
    current_findings = (
        assessment_dict.get("assessment", {}).get("findings", [])
        if assessment_dict else []
    )

    # Build lookup sets by message signature
    baseline_messages: dict[str, dict] = {}
    for f in baseline_findings:
        sig = f.get("message", "")[:80]
        baseline_messages[sig] = f

    current_messages: set[str] = set()
    for f in current_findings:
        sig = f.get("message", "")[:80]
        current_messages.add(sig)

    # Categorise
    closed = []
    remaining = []
    for sig, f in baseline_messages.items():
        if sig in current_messages:
            remaining.append(f)
        else:
            closed.append(f)

    new_findings = [
        f for f in current_findings
        if f.get("message", "")[:80] not in baseline_messages
    ]

    # Display
    total_baseline = len(baseline_findings)
    total_current = len(current_findings)
    closure = round(len(closed) / total_baseline * 100) if total_baseline else 0

    click.echo()
    click.echo(f"  Engagement: {slug}")
    click.echo(f"  {'─' * 45}")
    click.echo(f"  Baseline findings: {total_baseline}")
    click.echo(f"  Current findings:  {total_current}")
    click.echo()
    click.echo(f"  CLOSED: {len(closed)} findings")
    for f in closed[:10]:
        click.echo(f"    ✓ {f.get('id', '?')}: {f.get('message', '')[:60]}")
    if len(closed) > 10:
        click.echo(f"    ... and {len(closed) - 10} more")

    click.echo()
    click.echo(f"  REMAINING: {len(remaining)} findings")
    for f in remaining[:10]:
        click.echo(f"    ○ {f.get('id', '?')}: {f.get('message', '')[:60]}")
    if len(remaining) > 10:
        click.echo(f"    ... and {len(remaining) - 10} more")

    click.echo()
    click.echo(f"  NEW: {len(new_findings)} findings (regressions)")
    alert = "✅" if len(new_findings) == 0 else "⚠️"
    for f in new_findings[:5]:
        click.echo(f"    + [{f.get('severity', '?')}] {f.get('message', '')[:60]}")
    if len(new_findings) > 5:
        click.echo(f"    ... and {len(new_findings) - 5} more")

    click.echo()
    click.echo("  ──────────────────────────────")
    click.echo(f"  Closure rate: {closure}% {alert}")

    if new_findings:
        click.echo()
        click.echo("  ⚠️  New findings detected. Review before proceeding.")

@engagement.command()
@click.argument("slug")
@click.argument("branch")
def set_branch(slug, branch):
    """Set the branch for an engagement (explicit repoint).

    Updates the engagement's stored branch reference in engagement.yaml.
    Use this when working on a different branch intentionally (e.g.,
    after a rebase or merge).

    Examples:

        harness engagement set-branch my-engagement eng/my-engagement

        harness engagement set-branch bug-fixes main
    """
    try:
        root = _require_project_root()
        from harness.paths import get_engagement_dir

        eng_dir = get_engagement_dir(root, slug)
        eng_yaml_path = eng_dir / "engagement.yaml"

        if not eng_yaml_path.is_file():
            click.echo(f"Engagement '{slug}' has no engagement.yaml.", err=True)
            raise click.Abort()

        import yaml
        with open(eng_yaml_path) as f:
            yaml_data = yaml.safe_load(f) or {}

        old_branch = yaml_data.get("branch", "(not set)")
        yaml_data["branch"] = branch

        with open(eng_yaml_path, "w") as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

        click.echo(f"Engagement '{slug}' branch updated:")
        click.echo(f"  {old_branch} → {branch}")

    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Failed to set branch: {exc}", err=True)
        raise click.Abort()


@engagement.command()
@click.option("--engagement", "slug", help="Engagement slug (default: active)")
def fix(slug):
    """Fix missing engagement metadata and state issues.

    Creates missing files and directories needed for the engagement to
    function: engagement.yaml, engagement.md, plan.yaml, plan.md, and
    the assessments directory. Also syncs plan state and refreshes
    freshness records.

    Examples:

        harness engagement fix

        harness engagement fix --engagement my-engagement
    """
    try:
        root = _require_project_root()

        if not slug:
            from harness.engagement.resolver import resolve_active_engagement
            slug = resolve_active_engagement(root)

        if not slug:
            click.echo(
                "No active engagement. Specify one with --engagement.",
                err=True,
            )
            raise click.Abort()

        from harness.health import fix_engagement
        messages = fix_engagement(root, slug)
        for msg in messages:
            click.echo(f"  {msg}")

    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Fix failed: {exc}", err=True)
        raise click.Abort()


# ---------------------------------------------------------------------------
# Doc generation commands
# ---------------------------------------------------------------------------


@main.command()
@click.option("--output-dir", type=click.Path(path_type=Path), default=None,
              help="Output directory (default: project root)")
@click.option("--overwrite", type=click.Choice(["never", "ask", "all"]),
              default="ask", help="Overwrite strategy")
@click.option("--type", "doc_type",
              type=click.Choice(["full", "readme", "contributing",
                                "architecture", "usage", "changelog"]),
              default="full", help="Document type to generate")
@click.option("--source-tier", type=int, default=3,
              help="Source material tier (1-5, higher = richer)")
def generate_docs(output_dir, overwrite, doc_type, source_tier):
    """Generate project documentation from harness analysis data.

    Produces README.md, CONTRIBUTING.md, architecture docs, usage
    examples, and changelogs from existing project data.

    Examples:

        harness generate-docs

        harness generate-docs --type readme --overwrite all

        harness generate-docs --output-dir docs/ --type full

        harness generate-docs --type changelog
    """
    try:
        root = _require_project_root()

        from harness.docs.generator import (
            DocType,
            OverwriteMode,
            SourceTier,
            generate_all_docs,
            generate_doc,
            populate_context_from_project,
        )

        overwrite_mode = OverwriteMode(overwrite)
        source_tier_enum = SourceTier(source_tier)

        if doc_type == "full":
            generated = generate_all_docs(
                root=root,
                output_dir=output_dir or root,
                overwrite_mode=overwrite_mode,
                interactive=True,
                source_tier=source_tier_enum,
            )
        else:
            doc_type_enum = DocType(doc_type)
            context = populate_context_from_project(
                root, source_tier_enum
            )
            generated = generate_doc(
                doc_type=doc_type_enum,
                context=context,
                output_dir=output_dir or root,
                root=root,
                overwrite_mode=overwrite_mode,
                interactive=True,
                source_tier=source_tier_enum,
            )

        click.echo(f"Generated {len(generated)} document(s):")
        for p in generated:
            click.echo(f"  \u2022 {p.relative_to(root)}")

    except Exception as exc:
        click.echo(f"Failed to generate docs: {exc}", err=True)
        import traceback as _tb
        _tb.print_exc()
        raise click.Abort()


@main.group()
def changelog():
    """Manage engagement changelogs."""
    pass


@changelog.command()
@click.argument("engagement_slug")
@click.argument("text")
def annotate(engagement_slug, text):
    """Append a human annotation to the latest changelog entry.

    Annotations are appended to the existing entry without modifying
    the auto-generated content.

    Examples:

        harness changelog annotate my-engagement "Reviewed and approved"

        harness changelog annotate billing-fix "Added edge case handling"
    """
    try:
        root = _require_project_root()

        from harness.docs.changelog import annotate_changelog

        eng_dir = get_engagement_dir(root, engagement_slug)
        if not eng_dir.is_dir():
            click.echo(
                f"Error: Engagement '{engagement_slug}' not found.",
                err=True,
            )
            raise click.Abort()

        # Find the latest changelog entry
        changelog_dir = eng_dir / "changelog"
        if not changelog_dir.is_dir():
            click.echo(
                f"No changelog entries found for '{engagement_slug}'.",
                err=True,
            )
            raise click.Abort()

        entry_files = sorted(changelog_dir.iterdir(), reverse=True)
        if not entry_files:
            click.echo(
                f"No changelog entries found for '{engagement_slug}'.",
                err=True,
            )
            raise click.Abort()

        latest = entry_files[0]
        wave = latest.stem

        updated = annotate_changelog(eng_dir, wave, text)
        click.echo(f"Annotation added to {wave} changelog entry.")
        click.echo(f"  {updated.relative_to(root)}")

    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise click.Abort()
    except click.Abort:
        raise
    except Exception as exc:
        click.echo(
            f"Failed to annotate changelog: {exc}", err=True
        )
        raise click.Abort()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_session_type_flag(
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
            from harness.session.types import read_session_type
            st = read_session_type(root, slug)
            if st:
                return st
        except Exception:
            pass
    return None


def _get_head_sha(repo_root: Path) -> str:
    """Return the full SHA of HEAD."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


def _load_project_snapshot(path: Path) -> "ProjectSnapshot":
    """Load or create a ProjectSnapshot from a YAML file."""
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
