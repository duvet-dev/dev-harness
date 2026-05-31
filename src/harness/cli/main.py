"""Dev Harness CLI — Click-based command interface.

Port of the legacy monolithic ``cli.py`` (3,908 lines) to a proper
``cli/main.py`` module. All Click commands from the original file are
replicated here verbatim — no behavioural changes, just module relocation.

See V7 §12 Wave 8 and the legacy-replacement-plan for context.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Optional

import click

from harness._version import __version__, __build__, __build_date__, __commit__
from harness.cli.commands import (
    dispatch_cli_command,
    summary_command,
    inspect_command,
    assess_command,
    create_waves_from_assessment_command,
    create_wave_from_finding_command,
    list_waves_command,
    wave_status_command,
    generate_docs_command,
    annotate_changelog_command,
    rename_engagement_command,
    set_branch_command,
    fix_engagement_command,
    refresh_agents_command,
    set_governance_command,
)
from harness.command.setup import create_bus
from harness.command.commands.engagement import (
    AbortEngagementCommand,
    CreateEngagementCommand,
    ResumeEngagementCommand,
)
from harness.command.commands.phase import EnterPhaseCommand, ManagePhaseCommand
from harness.command.commands.project import InitProjectCommand
from harness.command.commands.misc import NextCommand, QueryStatusCommand, QueryWhatsNextCommand
from harness.command.commands.review import FinishEngagementCommand, ReviewEngagementCommand
from harness.command.commands.session import ChatCommand, SessionCommand
from harness.command.commands.wave import CreateWaveCommand, ExecuteStepCommand, RunWaveCommand
from harness.cli.helpers import (
    bold,
    find_project_root,
    get_head_sha,
    init_git,
    initial_commit,
    load_project_snapshot,
    reconcile_before_summary,
    require_project_root,
    resolve_session_type_flag,
    write_assessment_report,
    write_minimal_constitution,
    WORKFLOWS_EPILOG,
)
from harness.constitution.loader import scaffold as scaffold_constitution
from harness.constitution.templates.template_registry import (
    TemplateRegistry,
    refresh_agent_profiles,
    seed_agent_profiles,
)
from harness.paths import (
    get_engagement_dir,
    get_engagement_md,
    get_engagement_yaml,
    get_engagements_dir,
    get_harness_dir,
    get_harness_state_path,
)
from harness.scm.git import GitRepo
from harness.scm.gitignore import write_gitignore
from harness.state.freshness import FreshnessRecord, save_freshness
from harness.state.snapshot import EngagementSnapshot, ProjectSnapshot, SnapshotWriter


# ── Version Callbacks ────────────────────────────────────────────────────


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


# ── Main Click Group ─────────────────────────────────────────────────────


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

    CommandBus-based architecture with 30+ handlers. All operations
    flow through Click -> Command -> Handler -> business component.

    See ``harness workflows`` for workflow guidance.
    """
    pass


# ---------------------------------------------------------------------------
# General commands
# ---------------------------------------------------------------------------


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
        bus = create_bus()
        cmd = QueryWhatsNextCommand(slug=slug)
        result = bus.dispatch(cmd)

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
        bus = create_bus()
        cmd = EnterPhaseCommand(slug=slug, phase=phase)
        result = bus.dispatch(cmd)

        if not result.success:
            click.echo("Enter phase failed: " + (result.error or result.message), err=True)
            raise click.Abort()

        click.echo(result.message)

    except click.Abort:
        raise
    except Exception as exc:
        click.echo("Enter phase error: " + str(exc), err=True)
        raise click.Abort()


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


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

    Without arguments, initialises the current directory (like git init).
    Optionally pass a directory name to create and initialise a new subdirectory.

    If the project is already initialised (.harness/ exists), this command
    will refuse to re-initialise unless --force is passed.

    Examples::

        harness init                         # init current dir
        harness init my-project              # init new subdirectory
        harness init --template backend-service
        harness init --force                 # re-init (overwrites state)
    """
    try:
        bus = create_bus()
        cmd = InitProjectCommand(
            project_dir=project_dir,
            template=template,
            seed=seed,
            no_git=no_git,
            force=force,
        )
        result = bus.dispatch(cmd)

        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            raise click.Abort()

        click.echo(result.message)
        data = getattr(result, 'data', result.__dict__ if hasattr(result, '__dict__') else {})
        if isinstance(data, dict):
            click.echo(f"  Project : {data.get('project', '?')}")
            click.echo(f"  Template: {data.get('template', '(none)')}")
            click.echo(f"  Path    : {data.get('path', '?')}")
            if data.get('git_initted'):
                click.echo("  Git     : initialised")
        elif hasattr(result, 'project'):
            click.echo(f"  Project : {result.project}")
            click.echo(f"  Template: {result.template or '(none)'}")
            click.echo(f"  Path    : {result.path}")
            if result.git_initted:
                click.echo("  Git     : initialised")

    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Init failed: {exc}", err=True)
        raise click.Abort()
@main.command()
@click.argument("project_dir", required=False, default=None)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing agent profile files (not just missing ones).",
)
def refresh_agents(project_dir, force):
    """Refresh agent profiles from the harness's current agent registry."""
    try:
        from harness.cli.commands import dispatch_cli_command, refresh_agents_command
        cmd = refresh_agents_command(
            project_dir=project_dir,
            force=force,
        )
        result = dispatch_cli_command(cmd)
        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            raise click.Abort()
        data = result.data
        click.echo("Agent profiles refreshed.")
        for action, label in [("created", "Created"), ("updated", "Updated"), ("existing", "Already up-to-date")]:
            agents = data.get(action, [])
            if agents:
                click.echo(f"  {label}: {len(agents)}")
                for name in agents:
                    click.echo(f"    - {name}")
    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Refresh agents failed: {exc}", err=True)
        raise click.Abort()
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

    Dispatches a ``CreateEngagement`` command via the CommandBus.
    Delegates to ``StartupResumeFlow.create()`` in the handler.

    Examples:

        harness work "Add search feature" --mode wild

        harness work "Refactor auth" --mode full --max-iterations 3

        harness work "Fix bugs" --mode auto --no-partial-approval
    """
    try:
        root = require_project_root(command_name="work")

        import re
        slug = re.sub(r"[^a-z0-9-]", "-", description.lower().strip())
        slug = re.sub(r"-+", "-", slug).strip("-")

        bus = create_bus()
        cmd = CreateEngagementCommand(
            slug=slug,
            workflow_name="standard",
            session_type="greenfield",
            mode=mode,
        )
        result = bus.dispatch(cmd)

        if not result.success:
            click.echo(f"Failed to start engagement: {result.error}", err=True)
            raise click.Abort()

        click.echo(result.message)
        data = getattr(result, 'data', {})
        if isinstance(data, dict):
            click.echo(f"  ID: {data.get('slug', slug)}")
            click.echo(f"  Branch: {data.get('target_branch', '-')}")
            if data.get('branch_created'):
                click.echo("  Branch created: yes")
            warnings = data.get('warnings', [])
            for w in warnings:
                click.echo(f"  {w.get('type', 'warning')}: {w.get('message', '')}")

    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Failed to start engagement: {exc}", err=True)
        raise click.Abort()


# ---------------------------------------------------------------------------
# Summary command
# ---------------------------------------------------------------------------


@main.command()
@click.option("--engagement", help="Engagement ID (default: current)")
@click.option("--deep", is_flag=True)
@click.option("--assess", "assess_flag", is_flag=True, help="Run LLM-based independent assessment (P1-P5)")
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON")
@click.option("--reconcile", is_flag=True, help="Refresh state before summary")
def summary(deep, assess_flag, engagement, json_flag, reconcile):
    """Show project status summary."""
    try:
        from harness.cli.commands import dispatch_cli_command, summary_command
        from pathlib import Path
        cmd = summary_command(
            deep=deep,
            assess_flag=assess_flag,
            engagement=engagement,
            json_flag=json_flag,
            reconcile=reconcile,
        )
        result = dispatch_cli_command(cmd)
        if not result.success:
            click.echo(f"Summary failed: {result.error}", err=True)
            raise click.Abort()
        report = result.data.get("report", "")
        click.echo(report)
    except Exception as exc:
        click.echo(f"Analysis failed: {exc}", err=True)
        raise click.Abort()
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
    root = find_project_root()
    from harness.agents.agent_registry import (
        AGENTS,
        list_agent_roles,
    )

    roles = list_agent_roles()
    if not roles:
        click.echo("No agents registered.")
        return

    # Build team membership if project root available
    team_map: dict[str, str] = {}
    if root:
        from harness.team.registry import TeamRegistry
        from harness.team.defaults import get_builtin_teams
        registry = TeamRegistry(builtin=get_builtin_teams())
        for role in roles:
            for team_name in registry.list_teams():
                team = registry.resolve(team_name)
                if role in team.agents:
                    team_map[role] = team_name
                    break

    click.echo(f"\n  {'Role':<30} {'Tags':<40} {'Team':<20}")
    click.echo(f"  {'-'*28}  {'-'*38}  {'-'*18}")
    for spec in AGENTS:
        role = spec.role
        tags = ", ".join(getattr(spec, 'tags', []) or [])
        team = team_map.get(role, "-")
        click.echo(f"  {role:<30} {tags:<40} {team:<20}")
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

    # Team membership
    root = find_project_root()
    if root:
        from harness.team.registry import TeamRegistry
        from harness.team.defaults import get_builtin_teams
        registry = TeamRegistry(builtin=get_builtin_teams())
        team_name = None
        for name in registry.list_teams():
            team = registry.resolve(name)
            if spec.role in team.agents:
                team_name = name
                break
        if team_name:
            team = registry.resolve(team_name)
            click.echo(f"  Team: {team_name} (agents: {len(team.agents)})")
        else:
            click.echo("  Team: (none)")

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
    """Manage harness teams (formerly fleets).

    Teams group related agents into domain groups (architecture, coding,
    review, testing). Each team has agents and optional shared guidelines.

    Note: Team management (add/remove agents) is done via
    ``.harness/teams.yaml``.

    See ``harness agent list`` for available agents.
    """
    pass


@fleet.command(name="list")
@click.option("--consults", is_flag=True, help="Show consultation capabilities for each team")
def list_fleets(consults):
    """List all registered teams (formerly fleets) with their agents.

    Shows teams, their agent count, and description.

    Examples::

        harness fleet list

        harness fleet list --consults
    """
    require_project_root(command_name="fleet list")
    from harness.team.registry import TeamRegistry
    from harness.team.defaults import get_builtin_teams

    registry = TeamRegistry(builtin=get_builtin_teams())
    team_names = registry.list_teams()

    if not team_names:
        click.echo("No teams registered.")
        return

    click.echo(
        f"  {'Team':<24} {'Agents':<12}"
    )
    click.echo(f"  {'-'*22}  {'-'*10}")
    for name in team_names:
        team = registry.resolve(name)
        click.echo(
            f"  {team.name:<24} {len(team.agents):<12}"
        )

    if consults:
        click.echo()
        click.echo("  Consultations are managed at the engagement level via")
        click.echo("  ConsultationCapability in .harness/teams.yaml.")

    click.echo()


@fleet.command()
@click.argument("team_name")
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON")
def show(team_name, json_flag):
    """Show details for a specific team (formerly fleet).

    Displays team name, description, agents, and guidelines.

    Examples::

        harness fleet show architecture

        harness fleet show review --json
    """
    require_project_root(command_name="fleet show")
    from harness.team.registry import TeamRegistry
    from harness.team.defaults import get_builtin_teams

    registry = TeamRegistry(builtin=get_builtin_teams())
    try:
        team = registry.resolve(team_name)
    except Exception:
        click.echo(f"Team '{team_name}' not found.", err=True)
        click.echo(f"Available teams: {', '.join(registry.list_teams())}")
        raise click.Abort()

    if json_flag:
        import json
        data = {
            "name": team.name,
            "description": team.description,
            "agents": team.agents,
            "guidelines": team.guidelines,
        }
        click.echo(json.dumps(data, indent=2, sort_keys=True))
        return

    click.echo(f"Team: {team.name}")
    click.echo(f"  Description: {team.description or '-'}")
    click.echo(f"  Agents: {len(team.agents)}")
    for a in team.agents:
        click.echo(f"    - {a}")
    if team.guidelines:
        click.echo("  Guidelines:")
        for line in team.guidelines.strip().split('\n'):
            click.echo(f"    {line}")
    else:
        click.echo("  Guidelines: (none)")


@fleet.command(name="add-agent")
@click.argument("team_name")
@click.argument("agent_role")
def add_agent_to_fleet(team_name, agent_role):
    """Add an agent role to a team.

    Note: Team management is now done via ``.harness/teams.yaml``.

    Examples::

        # Edit .harness/teams.yaml directly:
        #   teams:
        #     architecture:
        #       agents: ["architect", "my-custom-agent"]
    """
    require_project_root(command_name="fleet add-agent")
    from harness.team.registry import TeamRegistry
    from harness.team.defaults import get_builtin_teams

    registry = TeamRegistry(builtin=get_builtin_teams())
    try:
        registry.resolve(team_name)
    except Exception:
        click.echo(f"Team '{team_name}' not found.", err=True)
        click.echo(f"Available teams: {', '.join(registry.list_teams())}")
        raise click.Abort()

    click.echo(
        f"To add '{agent_role}' to team '{team_name}', edit .harness/teams.yaml:\n"
        f"  teams:\n"
        f"    {team_name}:\n"
        f"      agents:\n"
        f"        - {agent_role}"
    )


@fleet.command(name="remove-agent")
@click.argument("team_name")
@click.argument("agent_role")
def remove_agent_from_fleet(team_name, agent_role):
    """Remove an agent role from a team.

    Note: Team management is now done via ``.harness/teams.yaml``.

    Examples::

        # Edit .harness/teams.yaml directly:
        #   teams:
        #     architecture:
        #       agents:
        #         - existing-agent
    """
    require_project_root(command_name="fleet remove-agent")
    from harness.team.registry import TeamRegistry
    from harness.team.defaults import get_builtin_teams

    registry = TeamRegistry(builtin=get_builtin_teams())
    try:
        registry.resolve(team_name)
    except Exception:
        click.echo(f"Team '{team_name}' not found.", err=True)
        click.echo(f"Available teams: {', '.join(registry.list_teams())}")
        raise click.Abort()

    click.echo(
        f"To remove '{agent_role}' from team '{team_name}', edit .harness/teams.yaml."
    )


@fleet.command(name="consult")
@click.argument("team_name")
@click.option("--no-truncate", is_flag=True,
              help="Show full match phrases without truncation")
def fleet_consult(team_name, no_truncate):
    """Show consultation capabilities for a team.

    Examples::

        harness fleet consult architecture

        harness fleet consult coding --no-truncate
    """
    require_project_root(command_name="fleet consult")
    from harness.team.registry import TeamRegistry
    from harness.team.defaults import get_builtin_teams

    registry = TeamRegistry(builtin=get_builtin_teams())
    try:
        team = registry.resolve(team_name)
    except Exception:
        click.echo(f"Team '{team_name}' not found.", err=True)
        click.echo(f"Available teams: {', '.join(registry.list_teams())}")
        raise click.Abort()

    if not team.guidelines:
        click.echo(f"Team '{team_name}' has no registered guidelines.")
        return

    click.echo(f"\n  Team: {team.name}")
    click.echo(f"  Guidelines: {team.guidelines[:200] if team.guidelines else '(none)'}")
    click.echo()
    click.echo("  (Consultation capabilities are managed at the engagement level in .harness/teams.yaml)")


@fleet.command(name="set-governance")
@click.argument("level", type=click.Choice(["exploration", "standard", "strict"]))
@click.option("--engagement", "slug", help="Apply to a specific engagement instead of project")
def set_governance(level, slug):
    """Set the governance level for the project or an engagement."""
    try:
        from harness.cli.commands import dispatch_cli_command, set_governance_command
        cmd = set_governance_command(level=level, slug=slug)
        result = dispatch_cli_command(cmd)
        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            raise click.Abort()
        click.echo(result.message)
    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Failed to set governance: {exc}", err=True)
        raise click.Abort()
@main.command()
@click.argument("question", nargs=-1, required=True)
@click.option("--team", help="Limit consultation to a specific team")
@click.option("--mode", type=click.Choice(["advisory", "blocking"]),
              default="advisory",
              help="Consultation mode (advisory by default)")
@click.option("--engagement", help="Engagement context (optional)")
def consult(question, team, mode, engagement):
    """Ask a cross-team consultation question.

    Routes a question through all registered teams' guidelines.

    Examples::

        harness consult "Is this architecture still sound?"

        harness consult --team architecture "Should we use hex?"
    """
    root = require_project_root(command_name="consult")
    from harness.team.registry import TeamRegistry
    from harness.team.defaults import get_builtin_teams

    registry = TeamRegistry(builtin=get_builtin_teams())
    q = " ".join(question)

    # Check which teams might have relevant guidelines
    matching_teams = []
    for name in registry.list_teams():
        if team is not None and name != team:
            continue

        team_def = registry.resolve(name)
        if team_def.guidelines:
            matching_teams.append(team_def)

    if not matching_teams:
        click.echo(f"\n  No team can answer: \"{q}\"")
        available = registry.list_teams()
        if available:
            click.echo()
            click.echo("  Available teams:")
            for name in available:
                click.echo(f"    [{name}]")
        else:
            click.echo("  No teams registered.")
        return

    # Display matched result
    for team_def in matching_teams:
        click.echo()
        click.echo(f"  Team: {team_def.name}")
        click.echo(f"  Guidelines: {team_def.guidelines[:200] if team_def.guidelines else '(none)'}")
    click.echo()
    click.echo("  (Structured consultation capabilities are managed at the engagement level)")


# ---------------------------------------------------------------------------
# Wave commands
# ---------------------------------------------------------------------------


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
    try:
        from harness.cli.commands import dispatch_cli_command, list_waves_command

        cmd = list_waves_command(slug=slug or "")
        result = dispatch_cli_command(cmd)
        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            raise click.Abort()
        waves = result.data.get("waves", [])
        if not waves:
            click.echo("No waves defined in the plan.")
            return
        click.echo()
        click.echo(f"  {'Wave ID':<12} {'Title':<36} {'Type':<14} {'State':<16}")
        click.echo(f"  {'-'*11}  {'-'*34}  {'-'*12}  {'-'*14}")
        for s in waves:
            marker = "*" if s.get("is_modifiable") and not s.get("is_committed") else " "
            click.echo(
                f"  {marker} {s.get('id', '?') :<10} {s.get('title', ''):<34} "
                f"{s.get('type', ''):<12} {s.get('state', ''):<14}"
            )
        click.echo()
        click.echo("Legend: * = active (modifiable, not yet committed)")
    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"List waves failed: {exc}", err=True)
        raise click.Abort()
@wave.command()
@click.argument("wave_id")
@click.option("--no-test", is_flag=True, help="Skip automated test suite execution")
@click.option("--backend", help="Agent backend name")
@click.option("--engagement", "slug", help="Engagement slug (default: active)")
def run_wave(wave_id, no_test, backend, slug):
    """Run a wave through the implement-test-verify-commit cycle.

    Usage:
        harness wave run wave-01
        harness wave run wave-01 --no-test
        harness wave run wave-01 --backend claude
    """
    try:
        from harness.cli.commands import dispatch_cli_command, run_wave_command

        if not slug:
            from harness.domain.engagement.resolver import resolve_active_engagement
            from pathlib import Path
            slug = resolve_active_engagement(Path.cwd())

        if not slug:
            click.echo(
                "No active engagement. Create one with:\n"
                "  harness engagement create \"your task\"",
                err=True,
            )
            raise click.Abort()

        bus = create_bus()
        cmd = RunWaveCommand(slug=slug, wave_id=wave_id, no_test=no_test, backend=backend)
        result = bus.dispatch(cmd)

        if not result.success:
            click.echo(f"Error running wave cycle: {result.error}", err=True)
            raise click.Abort()

        click.echo()
        click.echo(f"  Wave {wave_id} completed successfully!")
        click.echo(f"     Iterations: {result.data.get('iteration_count', '?')}")
        click.echo()
        click.echo("  Ready to commit and raise a PR.")

    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Error running wave cycle: {exc}", err=True)
        raise click.Abort()
@wave.command()
@click.option("--engagement", "slug", help="Engagement slug (default: active)")
def wave_status(slug):
    """Show detailed wave status from the engagement plan."""
    try:
        from harness.cli.commands import dispatch_cli_command, wave_status_command

        cmd = wave_status_command(slug=slug or "")
        result = dispatch_cli_command(cmd)
        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            raise click.Abort()
        summary = result.data.get("summary", "")
        click.echo()
        click.echo(summary)
    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Wave status failed: {exc}", err=True)
        raise click.Abort()
@wave.command(name="create-from-finding")
@click.argument("finding_id")
@click.option("--engagement", "slug", help="Engagement slug (default: active)")
def create_wave_from_finding(finding_id, slug):
    """Create a wave from an assessment finding."""
    try:
        from harness.cli.commands import dispatch_cli_command, create_wave_from_finding_command

        cmd = create_wave_from_finding_command(finding_id=finding_id, slug=slug or "")
        result = dispatch_cli_command(cmd)
        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            raise click.Abort()
        data = result.data
        click.echo()
        wave_id = data.get("wave_id", "?")
        click.echo(f"  Created wave '{wave_id}' from finding '{finding_id}'")
        title_val = data.get("title", "")
        click.echo(f"  Title: {title_val}")
        sev = data.get("severity", "?")
        cat = data.get("category", "?")
        click.echo(f"  Severity: {sev}, Category: {cat}")
        click.echo()
        click.echo(f"  Run it with:  harness wave run {wave_id}")
        click.echo("  See plan:     harness wave list")
    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Failed to create wave from finding: {exc}", err=True)
        raise click.Abort()
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
    """Create waves from all matching assessment findings."""
    try:
        from harness.cli.commands import dispatch_cli_command, create_waves_from_assessment_command

        cmd = create_waves_from_assessment_command(
            focus=focus, limit=limit, slug=slug or "", refactoring=refactoring,
        )
        result = dispatch_cli_command(cmd)
        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            raise click.Abort()
        click.echo()
        click.echo(result.message)
        click.echo()
        click.echo("  Run:  harness wave list")
        click.echo("  Run:  harness wave run <wave-id>")
    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Failed to create waves from assessment: {exc}", err=True)
        raise click.Abort()
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
    """Interactive LLM chat session within an engagement."""
    try:
        from harness.cli.commands import dispatch_cli_command, chat_command
        from harness.domain.engagement.resolver import resolve_active_engagement
        from harness.paths import get_engagement_dir
        from pathlib import Path

        root = Path.cwd()
        slug = engagement_slug
        if not slug:
            slug = resolve_active_engagement(root)

        if not slug:
            click.echo(
                "No active engagement. Create one with:\n"
                "  harness engagement create \"your task\"",
                err=True,
            )
            raise click.Abort()

        eng_dir = get_engagement_dir(root, slug)
        if not eng_dir.is_dir():
            click.echo(f"Engagement '{slug}' not found.", err=True)
            raise click.Abort()

        bus = create_bus()
        cmd = ChatCommand(slug=slug, prompt=prompt_text, phase=phase, context_tier=context_tier)
        result = bus.dispatch(cmd)
        if not result.success:
            click.echo(f"Chat error: {result.error}", err=True)
            raise click.Abort()
        click.echo(f"Opening chat session for engagement '{slug}'...")
        raise click.Abort()
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
    """Run a full phase-by-phase session."""
    try:
        from harness.cli.commands import dispatch_cli_command, session_command
        from harness.domain.engagement.resolver import resolve_active_engagement
        from harness.paths import get_engagement_dir
        from harness.cli.helpers import resolve_session_type_flag
        from pathlib import Path

        root = Path.cwd()
        slug = engagement_slug
        if not slug:
            slug = resolve_active_engagement(root)

        if not slug:
            click.echo(
                "No active engagement. Create one with:\n"
                "  harness engagement create \"your task\"",
                err=True,
            )
            raise click.Abort()

        eng_dir = get_engagement_dir(root, slug)
        if not eng_dir.is_dir():
            click.echo(f"Engagement '{slug}' not found.", err=True)
            raise click.Abort()

        resolved_type = resolve_session_type_flag(session_type, root, slug)

        effective_phase = phase
        if get_well and effective_phase == "requirements":
            effective_phase = "assessment-triage"

        bus = create_bus()
        cmd = SessionCommand(
            slug=slug,
            phase=effective_phase,
            session_type=resolved_type,
            context_tier=context_tier,
            get_well=get_well,
        )
        result = bus.dispatch(cmd)
        if not result.success:
            click.echo(f"Session error: {result.error}", err=True)
            raise click.Abort()

        click.echo(f"Session started for engagement '{slug}'")
        click.echo(f"  Phase: {effective_phase}")
        click.echo("  (Full phase-by-phase orchestration is a WIP in the new architecture)")
        raise click.Abort()
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

    Dispatches a ``ReviewEngagement`` command via the CommandBus.
    Handler manages Temporal gate review and local snapshot update.

    Examples:

        harness review eng-main-abc123 --approve

        harness review eng-main-def456 --reject

        harness review eng-main-abc123 --request-changes \
            --finding "Missing error handling" --severity blocker --artifact-ref auth.py \
            --finding "Rename variable x" --severity minor --artifact-ref utils.py \
            --notes "Surface-level issues only; logic is solid"
    """
    # Determine decision
    if finding:
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

    try:
        root = require_project_root(command_name="review")
        bus = create_bus()
        cmd = ReviewEngagementCommand(
            slug=engagement_id,
            decision=decision,
            root=root,
        )
        result = bus.dispatch(cmd)

        if not result.success:
            click.echo(f"Review failed: {result.error}", err=True)
        else:
            gateway = "temporal" if result.data.get("temporal_ok") else "local state"
            click.echo(f"Gate {decision} for engagement {engagement_id} ({gateway}).")

    except Exception:
        click.echo(f"Gate {decision} (local state only).")
# ---------------------------------------------------------------------------
# Status command
# ---------------------------------------------------------------------------


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
        bus = create_bus()
        cmd = QueryStatusCommand(slug=slug or "")
        result = bus.dispatch(cmd)
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
    root = require_project_root(command_name="status")
    try:
        snapshot_path = get_harness_state_path(root)
        snapshot = load_project_snapshot(snapshot_path)

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


# ---------------------------------------------------------------------------
# Phase management command
# ---------------------------------------------------------------------------


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

    Dispatches a ManagePhase command via the CommandBus.
    Handler delegates to PhaseStateManager, CheckpointManager,
    and FeedbackManager.

    Examples::

        harness phase --list

        harness phase --navigate design

        harness phase --feedback-target design --feedback-reason "OAuth not covered"

        harness phase --resume

        harness phase --status

        harness phase --feedback-list
    """
    try:
        # Determine action from flags
        action = None
        target = None
        if list_flag:
            action = 'list'
        elif nav_target:
            action = 'navigate'
            target = nav_target
        elif fb_target:
            action = 'feedback'
            target = fb_target
        elif resume_flag:
            action = 'resume'
        elif status_flag:
            action = 'status'
        elif fb_list_flag:
            action = 'feedback_list'
        elif advance:
            action = 'advance'

        if not action:
            click.echo('No action specified. Use --list, --navigate, --status, etc.')
            click.echo('See harness phase --help for options.')
            return

        root = require_project_root(command_name='phase')
        bus = create_bus()
        cmd = ManagePhaseCommand(
            slug=engagement_id or '',
            action=action,
            target=target or None,
            feedback_reason=fb_reason,
            force=force_flag,
            root=str(root),
        )
        result = bus.dispatch(cmd)

        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            raise click.Abort()

        data = result.data

        if action == 'list':
            phases = data.get('phases', [])
            if not phases:
                click.echo('No phases recorded for this engagement.')
                return
            click.echo(f"Phases for {engagement_id}:")
            for p in phases:
                icon = {'completed': '✔', 'active': '▶',
                        'paused': '⏸'}.get(p['state'], '○')
                click.echo(f"  {icon} {p['name']} ({p['state']})")

        elif action == 'navigate':
            click.echo(f"Navigated to phase '{target}'.")
            if data.get('checkpoint'):
                click.echo(f"  Checkpoint: {data['checkpoint']}")

        elif action == 'feedback':
            click.echo(f"Feedback sent to '{target}'.")
            click.echo(f"  Path: {data.get('feedback_path', '-')}")

        elif action == 'resume':
            if data.get('resumed'):
                click.echo(f"Resumed from checkpoint: {data.get('checkpoint', '-')}")
                click.echo(f"  Phase: {data.get('phase', '-')}")
            else:
                click.echo('No checkpoints found.')

        elif action == 'status':
            phases = data.get('phases', {})
            if not phases:
                click.echo('No phase state recorded yet.')
                return
            click.echo(f"Phase states for {engagement_id}:")
            for name, record in sorted(phases.items()):
                state = record.get('state', 'unknown')
                ckpt = record.get('checkpoint_ref', '') or '-'
                fb_tgt = record.get('feedback_target', '') or '-'
                icon = {'completed': '✔', 'active': '▶',
                        'paused': '⏸'}.get(state, '○')
                click.echo(f"  {icon} {name}: {state} (ck: {ckpt}, fb: {fb_tgt})")

        elif action == 'feedback_list':
            entries = data.get('feedback', [])
            if not entries:
                click.echo('No feedback history.')
                return
            click.echo("Feedback history:")
            for fb in entries:
                click.echo(f"  [{fb.get('status', '?')}] {fb.get('from', '?')} -> {fb.get('to', '?')}: {fb.get('title', '')}")

    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Phase command failed: {exc}", err=True)
        raise click.Abort()
def inspect(repo_path, report_file, deep, verbose, project_type):
    """Analyse a codebase as an external observer."""
    try:
        from harness.cli.commands import dispatch_cli_command, inspect_command
        from harness.cli.helpers import write_assessment_report

        cmd = inspect_command(root=repo_path)
        result = dispatch_cli_command(cmd)
        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            raise click.Abort()

        findings = result.data.get("findings_count", "?")
        score = result.data.get("score", "?")
        if verbose:
            click.echo(result.data.get("report", ""))
        else:
            click.echo(f"Assessment complete: {findings} findings, score: {score}")

        written = write_assessment_report(
            result.data.get("report", ""), repo_path, report_file,
            assessment_dict=None,
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
    """Run the full assessment on the current project."""
    try:
        from harness.cli.commands import dispatch_cli_command, assess_command
        from harness.cli.helpers import write_assessment_report

        cmd = assess_command(root=repo_path, deep_flag=True)
        result = dispatch_cli_command(cmd)
        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            raise click.Abort()

        findings = result.data.get("findings_count", "?")
        score = result.data.get("score", "?")
        if verbose:
            click.echo(result.data.get("report", ""))
        else:
            click.echo(f"Assessment complete: {findings} findings, score: {score}")

        written = write_assessment_report(
            result.data.get("report", ""), repo_path, report_file,
            assessment_dict=None,
        )
        if written:
            click.echo(f"Report written to: {written}")
    except Exception as exc:
        click.echo(f"Assessment failed: {exc}", err=True)
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
    root = require_project_root(command_name="shell")
    from harness.shell import shell as run_shell
    run_shell(root=root)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


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
        root = require_project_root(command_name="health")

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


# ---------------------------------------------------------------------------
# Finish command
# ---------------------------------------------------------------------------


@main.command()
@click.option("--re-assess", is_flag=True,
              help="Re-run assessment and compare to baseline on finish")
def finish(re_assess):
    """Complete the current engagement with a commit.

    Dispatches a ``FinishEngagement`` command via the CommandBus.
    Handler manages git stage/commit, snapshot update, and optional
    observer re-assessment.

    Examples:
        harness finish
        harness finish --re-assess
    """
    try:
        root = require_project_root(command_name="finish")

        bus = create_bus()
        cmd = FinishEngagementCommand(slug="", root=str(root), re_assess=re_assess)
        result = bus.dispatch(cmd)

        if not result.success:
            click.echo(f"Failed: {result.error}", err=True)
            raise click.Abort()

        data = result.data
        click.echo(f"Engagement finished @ {data.get('head_sha', '')[:8]} on {data.get('branch', '-')}.")

        re_assessment = data.get("re_assessment")
        if re_assessment:
            if "error" in re_assessment:
                click.echo(f"  Re-assessment failed: {re_assessment['error']}")
            else:
                click.echo()
                click.echo(
                    "  \u250c\u2500 Re-Assessment Results "
                    "\u2500\u2500\u2500\u2500\u2500\u2500"
                    "\u2500\u2500\u2500\u2500\u2500\u2500"
                    "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                )
                click.echo(
                    "  \u2502 Baseline findings:  "
                    f"{re_assessment.get('baseline_count', '?')}"
                )
                click.echo(
                    "  \u2502 Current findings:   "
                    f"{re_assessment.get('current_findings', '?')}"
                )
                closed = re_assessment.get("closed_count", "?")
                if isinstance(closed, int):
                    click.echo(f"  \u2502 Findings closed:    {closed}")
                click.echo(
                    "  \u2502 Report:            "
                    f"{re_assessment.get('report', '-')}"
                )
                click.echo(
                    "  \u2514\u2500\u2500\u2500\u2500"
                    "\u2500\u2500\u2500\u2500\u2500\u2500"
                    "\u2500\u2500\u2500\u2500\u2500\u2500"
                    "\u2500\u2500\u2500\u2500\u2500\u2500"
                    "\u2500\u2500\u2500\u2500\u2500\u2500"
                    "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                )

        click.echo()
        click.echo("Tip: Use `harness summary` to view the final state.")

    except click.Abort:
        raise
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
        root = require_project_root(command_name="engagement create")

        # Derive slug
        from harness.domain.engagement.lifecycle import slugify
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
        from harness.domain.engagement.lifecycle import (
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
            eng_yaml_path = get_engagement_yaml(root, slug)
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
                    f"without waves \u2014 add them manually with:\n"
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

                    wave_obj = pm.add_wave(
                        title=title,
                        wave_type="refactor",
                        trigger_phase="assessment",
                        trigger_reason=(
                            f"Finding {finding_id}: [{severity}] {category} \u2014 "
                            f"{f.get('message', '')[:80]}"
                        ),
                    )

                    f["wave_slug"] = wave_obj.id
                    f["wave_status"] = "open"
                    manifest_updates.append((finding_id, wave_obj.id))
                    waves_created += 1

                # Update the manifest to persist wave associations
                if manifest_updates:
                    baseline_manifest_path.write_text(
                        _json.dumps(baseline_manifest, indent=2)
                    )

        # Set active engagement
        from harness.domain.engagement.lifecycle import set_active_engagement
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
            click.echo(f"    See:  cat {get_engagement_yaml(root, slug)}")
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
        root = require_project_root(command_name="engagement set-active")

        from harness.domain.engagement.lifecycle import set_active_engagement
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
        root = require_project_root(command_name="engagement list")
        engagements_dir = get_engagements_dir(root)

        if not engagements_dir.is_dir():
            click.echo("No engagements found.")
            return

        # Resolve active engagement
        try:
            from harness.domain.engagement.resolver import resolve_active_engagement
            active_slug = resolve_active_engagement(root)
        except Exception:
            active_slug = None

        from harness.domain.engagement.lifecycle import _parse_engagement_md

        rows = []
        for entry in sorted(engagements_dir.iterdir()):
            if not entry.is_dir():
                continue
            md_file = entry / "engagement.md"
            meta = _parse_engagement_md(md_file) if md_file.is_file() else {}
            slug = meta.get("slug", entry.name)
            status = meta.get("status", "unknown")
            branch = meta.get("branch", "\u2014")

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
            marker = "  \u2190 active" if is_active else ""
            click.echo(
                f"{slug:30s} {status:20s} {branch:30s} {wave_count:5d}{marker}"
            )

    except Exception as exc:
        click.echo(f"Failed to list engagements: {exc}", err=True)
        raise click.Abort()


@engagement.command()
@click.option("--engagement", "engagement_slug", help="Engagement slug (default: active)")
def engagement_status(engagement_slug):
    """Show detailed status of an engagement.

    Defaults to the active engagement for the current branch.
    Use ``--engagement`` to specify a different one.

    Examples:

        harness engagement status

        harness engagement status --engagement api-redesign
    """
    try:
        root = require_project_root(command_name="engagement status")

        # Resolve which engagement to show
        slug = engagement_slug
        if not slug:
            from harness.domain.engagement.resolver import resolve_active_engagement
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

        from harness.domain.engagement.lifecycle import _parse_engagement_md
        meta = _parse_engagement_md(md_file)

        title = meta.get("title", slug)
        status_text = meta.get("status", "unknown")
        branch = meta.get("branch", "\u2014")
        created_at = meta.get("created_at", "\u2014")

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
    """Rename an existing engagement."""
    try:
        from harness.cli.commands import dispatch_cli_command, rename_engagement_command

        cmd = rename_engagement_command(
            old_slug=old_slug,
            new_slug=new_slug,
            branch_strategy=branch_strategy,
            dry_run=dry_run,
        )
        result = dispatch_cli_command(cmd)
        if not result.success:
            for err in result.data.get("errors", [result.error]):
                click.echo(f"Error: {err}", err=True)
            raise click.Abort()

        if dry_run:
            click.echo(f"DRY RUN - Would rename '{old_slug}' -> '{new_slug}'")
            for change in result.data.get("changes_made", []):
                click.echo(f"  * {change}")
            for w in result.data.get("warnings", []):
                click.echo(f"  Warning: {w}")
            return

        click.echo(f"Engagement renamed: {old_slug} -> {new_slug}")
        for change in result.data.get("changes_made", []):
            click.echo(f"  * {change}")
        for w in result.data.get("warnings", []):
            click.echo(f"  Warning: {w}")
    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Failed to rename engagement: {exc}", err=True)
        raise click.Abort()
@engagement.command()
@click.argument("slug")
def close(slug):
    """Close an engagement by setting its status to completed.

    Dispatches an ``AbortEngagement`` command via the CommandBus.
    Delegates to ``AbortHandler.graceful_stop()`` in the handler.

    CLI guard: validates engagement exists and checks all waves are
    completed before closing.

    Examples:

        harness engagement close fix-billing-bug
    """
    try:
        root = require_project_root(command_name="engagement close")

        # Validate engagement exists (CLI guard)
        md_file = get_engagement_md(root, slug)
        if not md_file.is_file():
            click.echo(
                f"Error: Engagement '{slug}' not found at {md_file}",
                err=True,
            )
            raise click.Abort()

        from harness.domain.engagement.lifecycle import _parse_engagement_md
        meta = _parse_engagement_md(md_file)
        status = meta.get("status", "unknown")

        if status == "completed":
            click.echo(f"Engagement '{slug}' is already completed.")
            return

        # Check waves completion (CLI guard)
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

        # Dispatch through CommandBus
        bus = create_bus()
        cmd = AbortEngagementCommand(slug=slug, mode="graceful")
        result = bus.dispatch(cmd)

        if not result.success:
            click.echo(f"Failed to close engagement: {result.error}", err=True)
            raise click.Abort()

        click.echo(result.message)
        data = result.data
        if data.get("current_phase"):
            click.echo(f"  Current phase: {data['current_phase']}")
        if data.get("completed_phases"):
            click.echo(f"  Completed phases: {', '.join(data['completed_phases'])}")
        if data.get("previous_status"):
            click.echo(f"  Previous status: {data['previous_status']}")

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

    root = require_project_root(command_name="engagement diff")

    if not slug:
        from harness.domain.engagement.resolver import resolve_active_engagement
        slug = resolve_active_engagement(root)

    if not slug:
        click.echo(
            "No active engagement. Specify one with --engagement.",
            err=True,
        )
        raise click.Abort()

    eng_dir = get_engagement_dir(root, slug)
    eng_yaml_path = get_engagement_yaml(root, slug)

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
    bar = "\u2500"
    click.echo(f"  {bar * 45}")
    click.echo(f"  Baseline findings: {total_baseline}")
    click.echo(f"  Current findings:  {total_current}")
    click.echo()
    click.echo(f"  CLOSED: {len(closed)} findings")
    for f in closed[:10]:
        click.echo(f"    \u2713 {f.get('id', '?')}: {f.get('message', '')[:60]}")
    if len(closed) > 10:
        click.echo(f"    ... and {len(closed) - 10} more")

    click.echo()
    click.echo(f"  REMAINING: {len(remaining)} findings")
    for f in remaining[:10]:
        click.echo(f"    \u25cb {f.get('id', '?')}: {f.get('message', '')[:60]}")
    if len(remaining) > 10:
        click.echo(f"    ... and {len(remaining) - 10} more")

    click.echo()
    click.echo(f"  NEW: {len(new_findings)} findings (regressions)")
    alert = "\u2705" if len(new_findings) == 0 else "\u26a0\ufe0f"
    for f in new_findings[:5]:
        click.echo(f"    + [{f.get('severity', '?')}] {f.get('message', '')[:60]}")
    if len(new_findings) > 5:
        click.echo(f"    ... and {len(new_findings) - 5} more")

    click.echo()
    click.echo("  \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    click.echo(f"  Closure rate: {closure}% {alert}")

    if new_findings:
        click.echo()
        click.echo("  \u26a0\ufe0f  New findings detected. Review before proceeding.")


@engagement.command()
@click.argument("slug")
@click.argument("branch")
def set_branch(slug, branch):
    """Set the branch for an engagement (explicit repoint)."""
    try:
        from harness.cli.commands import dispatch_cli_command, set_branch_command

        cmd = set_branch_command(slug=slug, branch=branch)
        result = dispatch_cli_command(cmd)
        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            raise click.Abort()
        data = result.data
        click.echo(f"Engagement '{slug}' branch updated:")
        old_branch = data.get("old_branch", "(not set)")
        new_branch = data.get("new_branch", branch)
        click.echo(f"  {old_branch} -> {new_branch}")
    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Failed to set branch: {exc}", err=True)
        raise click.Abort()
@engagement.command()
@click.option("--engagement", "slug", help="Engagement slug (default: active)")
def fix(slug):
    """Fix missing engagement metadata and state issues."""
    try:
        from harness.cli.commands import dispatch_cli_command, fix_engagement_command

        cmd = fix_engagement_command(slug=slug or "")
        result = dispatch_cli_command(cmd)
        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            raise click.Abort()
        for msg in result.data.get("messages", []):
            click.echo(f"  {msg}")
    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Fix failed: {exc}", err=True)
        raise click.Abort()
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
    """Generate project documentation from harness analysis data."""
    try:
        from harness.cli.commands import dispatch_cli_command, generate_docs_command
        from pathlib import Path

        cmd = generate_docs_command(root=str(Path.cwd()))
        result = dispatch_cli_command(cmd)
        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            raise click.Abort()
        generated = result.data.get("generated", [])
        click.echo(f"Generated {len(generated)} document(s):")
        for p in generated:
            click.echo(f"  * {p}")
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
    """Append a human annotation to the latest changelog entry."""
    try:
        from harness.cli.commands import dispatch_cli_command, annotate_changelog_command

        cmd = annotate_changelog_command(slug=engagement_slug, wave="", text=text)
        result = dispatch_cli_command(cmd)
        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            raise click.Abort()
        click.echo("Annotation added to changelog entry.")
        click.echo(f"  {result.data.get('path', '')}")
    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Failed to annotate changelog: {exc}", err=True)
        raise click.Abort()
