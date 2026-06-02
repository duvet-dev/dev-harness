"""Typed handlers for project initialisation.

Covers: InitProjectHandler.
"""

from __future__ import annotations

from pathlib import Path

from harness.command.types import TypedHandler
from harness.command.commands.project import InitProjectCommand
from harness.command.results.project import InitProjectResult


class InitProjectTypedHandler(TypedHandler[InitProjectCommand, InitProjectResult]):
    """Initialise a new harness project."""

    def handle(self, command: InitProjectCommand) -> InitProjectResult:
        try:
            from harness.cli.helpers import (
                init_git,
                initial_commit,
                write_minimal_constitution,
            )
            from harness.constitution.loader import scaffold as scaffold_constitution
            from harness.constitution.templates.template_registry import (
                TemplateRegistry,
                seed_agent_profiles,
            )
            from harness.paths import (
                get_engagements_dir,
                get_harness_dir,
                get_harness_state_path,
            )
            from harness.scm.gitignore import write_gitignore as _write_gitignore
            from harness.state.snapshot import ProjectSnapshot, SnapshotWriter

            root = command.root
            project_dir = command.project_dir
            template = command.template
            no_git = command.no_git
            force = command.force

            if project_dir:
                project_path = root / project_dir
                if project_path.exists():
                    if project_path.is_file():
                        return InitProjectResult(
                            success=False,
                            error=f"{project_path} is a file, not a directory",
                        )
                else:
                    project_path.mkdir(parents=True, exist_ok=True)
            else:
                project_path = root

            already_initted = get_harness_dir(project_path).is_dir()
            if already_initted and not force:
                return InitProjectResult(
                    success=False,
                    error=(
                        f"{project_path} is already a harness project. "
                        "Use --force to re-initialise."
                    ),
                )

            project_name = project_path.name

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

            return InitProjectResult(
                success=True,
                message=(
                    f"Project '{project_name}' initialised "
                    f"(template: {template or 'none'}, "
                    f"git: {'yes' if git_ok else 'no'})"
                ),
                project=project_name,
                template=template or "(none)",
                path=str(project_path),
                git_initted=git_ok,
            )

        except Exception as exc:
            return InitProjectResult(
                success=False,
                error=str(exc),
                message=f"Init failed: {exc}",
            )
