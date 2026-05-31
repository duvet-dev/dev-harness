"""Typed handlers for simple engagement operations.

Covers: RenameEngagementHandler, SetBranchHandler, FixEngagementHandler,
RefreshAgentsHandler, SetGovernanceHandler, AgentListHandler,
FleetListHandler, ConsultHandler.
"""

from __future__ import annotations

from pathlib import Path

from harness.command.types import TypedHandler
from harness.command.commands.mgmt import (
    AgentListCommand,
    ConsultCommand,
    FixEngagementCommand,
    FleetListCommand,
    RefreshAgentsCommand,
    RenameEngagementCommand,
    SetBranchCommand,
    SetGovernanceCommand,
)
from harness.command.results.mgmt import (
    AgentListResult,
    ConsultResult,
    FixEngagementResult,
    FleetListResult,
    RefreshAgentsResult,
    RenameEngagementResult,
    SetBranchResult,
    SetGovernanceResult,
)


class RenameEngagementTypedHandler(
    TypedHandler[RenameEngagementCommand, RenameEngagementResult]
):
    """Rename an existing engagement."""

    def handle(self, command: RenameEngagementCommand) -> RenameEngagementResult:
        try:
            from harness.domain.engagement.rename import BranchStrategy, rename_engagement

            root = command.slug if Path(command.slug).is_absolute() else Path.cwd()
            new_slug = command.new_slug
            branch_strategy = command.branch_strategy
            dry_run = command.dry_run

            strategy = BranchStrategy(branch_strategy)
            result = rename_engagement(
                old_slug=command.slug,
                new_slug=new_slug,
                root=root,
                branch_strategy=strategy,
                dry_run=dry_run,
            )

            if result.errors:
                return RenameEngagementResult(
                    success=False,
                    error="; ".join(result.errors),
                    changes_made=result.changes_made,
                    warnings=result.warnings,
                    errors=result.errors,
                    dry_run=dry_run,
                )

            return RenameEngagementResult(
                success=True,
                message=f"Engagement renamed: {command.slug} -> {new_slug}",
                changes_made=result.changes_made,
                warnings=result.warnings,
                dry_run=dry_run,
            )

        except Exception as exc:
            return RenameEngagementResult(
                success=False,
                error=str(exc),
                message=f"Rename failed: {exc}",
            )


class SetBranchTypedHandler(TypedHandler[SetBranchCommand, SetBranchResult]):
    """Set the branch for an engagement."""

    def handle(self, command: SetBranchCommand) -> SetBranchResult:
        try:
            from harness.paths import get_engagement_dir

            root = Path.cwd()
            slug = command.slug
            branch = command.branch

            eng_dir = get_engagement_dir(root, slug)
            eng_yaml_path = eng_dir / "engagement.yaml"

            if not eng_yaml_path.is_file():
                return SetBranchResult(
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

            return SetBranchResult(
                success=True,
                message=f"Branch updated: {old_branch} -> {branch}",
                slug=slug,
                old_branch=old_branch,
                new_branch=branch,
            )

        except Exception as exc:
            return SetBranchResult(
                success=False,
                error=str(exc),
                message=f"Set branch failed: {exc}",
            )


class FixEngagementTypedHandler(TypedHandler[FixEngagementCommand, FixEngagementResult]):
    """Fix engagement metadata and state issues."""

    def handle(self, command: FixEngagementCommand) -> FixEngagementResult:
        try:
            from pathlib import Path

            root = Path.cwd()
            slug = command.slug

            if not slug:
                from harness.domain.engagement.resolver import resolve_active_engagement
                slug = resolve_active_engagement(root)

            if not slug:
                return FixEngagementResult(
                    success=False,
                    error="No active engagement to fix",
                )

            from harness.health import fix_engagement
            messages = fix_engagement(root, slug)

            return FixEngagementResult(
                success=True,
                message=f"Fixed {len(messages)} issue(s) for '{slug}'",
                slug=slug,
                messages=messages,
            )

        except Exception as exc:
            return FixEngagementResult(
                success=False,
                error=str(exc),
                message=f"Fix engagement failed: {exc}",
            )


class RefreshAgentsTypedHandler(TypedHandler[RefreshAgentsCommand, RefreshAgentsResult]):
    """Refresh agent profiles from agent registry."""

    def handle(self, command: RefreshAgentsCommand) -> RefreshAgentsResult:
        try:
            from harness.cli.helpers import require_project_root
            from harness.constitution.templates.template_registry import (
                refresh_agent_profiles,
            )

            project_dir = command.project_dir
            force = command.force

            explicit_path = None
            if project_dir:
                explicit_path = Path.cwd() / project_dir
            root = require_project_root(
                explicit_path=explicit_path,
                command_name="refresh-agents",
            )

            result = refresh_agent_profiles(root, force=force)

            return RefreshAgentsResult(
                success=True,
                message="Agent profiles refreshed",
                created=result.get("created", []),
                updated=result.get("updated", []),
                existing=result.get("existing", []),
            )

        except Exception as exc:
            return RefreshAgentsResult(
                success=False,
                error=str(exc),
                message=f"Refresh agents failed: {exc}",
            )


class SetGovernanceTypedHandler(TypedHandler[SetGovernanceCommand, SetGovernanceResult]):
    """Set governance level for project or engagement."""

    def handle(self, command: SetGovernanceCommand) -> SetGovernanceResult:
        try:
            from harness.agents.governance import (
                GovernanceLevel,
                get_project_governance,
                set_project_governance,
                set_engagement_governance,
            )
            from harness.cli.helpers import require_project_root

            root = require_project_root(command_name="set-governance")
            level = command.level
            slug = command.slug

            gov = GovernanceLevel(level)

            if slug:
                set_engagement_governance(root, slug, gov)
                return SetGovernanceResult(
                    success=True,
                    message=f"Engagement '{slug}' governance set to '{level}'",
                    level=level,
                    scope="engagement",
                )
            else:
                set_project_governance(root, gov)
                return SetGovernanceResult(
                    success=True,
                    message=f"Project governance set to '{level}'",
                    level=level,
                    scope="project",
                )

        except Exception as exc:
            return SetGovernanceResult(
                success=False,
                error=str(exc),
                message=f"Set governance failed: {exc}",
            )


class AgentListTypedHandler(TypedHandler[AgentListCommand, AgentListResult]):
    """List all registered agent roles."""

    def handle(self, command: AgentListCommand) -> AgentListResult:
        try:
            from harness.agents.agent_registry import AGENTS, list_agent_roles

            roles = list_agent_roles()
            agents_data = []
            for spec in AGENTS:
                agents_data.append({
                    "role": spec.role,
                    "tags": list(getattr(spec, "tags", []) or []),
                })

            return AgentListResult(
                success=True,
                message=f"{len(agents_data)} agent(s) registered.",
                agents=agents_data,
                count=len(agents_data),
            )

        except Exception as exc:
            return AgentListResult(
                success=False,
                error=str(exc),
                message=f"Agent list failed: {exc}",
            )


class FleetListTypedHandler(TypedHandler[FleetListCommand, FleetListResult]):
    """List all registered teams."""

    def handle(self, command: FleetListCommand) -> FleetListResult:
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

            return FleetListResult(
                success=True,
                message=f"{len(teams_data)} team(s) registered.",
                teams=teams_data,
                count=len(teams_data),
            )

        except Exception as exc:
            return FleetListResult(
                success=False,
                error=str(exc),
                message=f"Fleet list failed: {exc}",
            )


class ConsultTypedHandler(TypedHandler[ConsultCommand, ConsultResult]):
    """Route a consultation question to matching teams."""

    def handle(self, command: ConsultCommand) -> ConsultResult:
        try:
            from harness.team.registry import TeamRegistry
            from harness.team.defaults import get_builtin_teams
            from harness.agents.consultation import ConsultationOrchestrator

            question = command.question
            team_filter = command.team_filter
            mode = command.mode

            registry = TeamRegistry(builtin=get_builtin_teams())
            orch = ConsultationOrchestrator(registry)
            result = orch.route(question, mode=mode, team_filter=team_filter)

            return ConsultResult(
                success=result.status == "matched",
                message=result.summary,
                status=result.status,
                capability=result.capability,
                team_name=result.team_name,
                mode=result.mode,
                response=result.response,
            )

        except Exception as exc:
            return ConsultResult(
                success=False,
                error=str(exc),
                message=f"Consultation failed: {exc}",
            )
