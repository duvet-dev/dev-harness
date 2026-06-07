"""StartupResumeFlow — engagement creation, resumption, and loading.

The top-level entry point for the engagement lifecycle, called by
CommandBus handlers (CreateEngagementHandler).

Coordinates:
- WorkflowOrchestrator → PhaseOrchestrator → StepExecutor chain
- Engagement lifecycle (create → active → ... → completed)
- Branch creation and health checks
- Auto mode step execution

See V7 §5.24, §6.1, and §12 (Wave 10) for the design.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from harness.domain.engagement.health import EngagementHealthCheck, HealthReport
from harness.domain.engagement.model import Engagement, EngagementStatus, HealthWarning
from harness.domain.engagement.repository import EngagementRepository
from harness.scm.git import GitRepo
from harness.scm.git_types import GitOperationError, GitCheckoutError
from harness.errors import (
    EngagementNotFoundError,
    EngagementBranchMissingError,
    UnknownWorkflowError,
)
from harness.paths import find_project_root
from harness.tracing import TraceLogger
from harness.workflow.model import Workflow
from harness.workflow.orchestrator import (
    DEFAULT_WORKFLOWS,
    SESSION_TYPE_MAP,
    WorkflowOrchestrator,
)

logger = TraceLogger("harness.engagement.startup")


@dataclass
class StartupResult:
    """Result of a startup or resume operation.

    Attributes:
        success: True if the operation succeeded.
        engagement: The Engagement instance, if loaded/created.
        report: Health report from proactive health check.
        branch_created: True if a new branch was created.
        phase_entered: Name of the phase entered, if applicable.
        warnings: Aggregated warnings from health check and
            branch operations.
        error: Error message if the operation failed.
    """

    success: bool = True
    engagement: Engagement | None = None
    report: HealthReport | None = None
    branch_created: bool = False
    phase_entered: str | None = None
    warnings: list[HealthWarning] = field(default_factory=list)
    error: str | None = None


class StartupResumeFlow:
    """Coordinates engagement creation, resumption, and loading.

    This is the top-level entry point called by CommandBus handlers.
    It orchestrates the full engagement lifecycle:

    - ``create()`` — Creates a new engagement with branch, health
      check, and first-phase entry.
    - ``resume()`` — Loads an existing engagement, runs health
      check, and re-enters the current phase.
    - ``load()`` — Loads engagement state from the repository.

    Phase entry (the ``enter_first_phase_async`` and ``resume_async``
    methods) involves async dispatch through WorkflowOrchestrator →
    PhaseOrchestrator → StepExecutor. The synchronous ``create()``
    and ``resume()`` methods handle the synchronous lifecycle
    (model creation, persistence, health checks) and record the
    phase to enter; call the ``_async`` variants for full phase
    execution.
    """

    def __init__(
        self,
        root: Path | None = None,
        repository: EngagementRepository | None = None,
        health_check: EngagementHealthCheck | None = None,
        workflow_orchestrator: WorkflowOrchestrator | None = None,
        git_repo: GitRepo | None = None,
    ) -> None:
        """Initialise the StartupResumeFlow.

        Args:
            root: Project root directory. Auto-discovered if None.
            repository: An EngagementRepository instance. Created
                from root if not provided.
            health_check: An EngagementHealthCheck instance.
                Created from repository if not provided.
            workflow_orchestrator: A WorkflowOrchestrator instance.
                Created with default workflows if not provided.
            git_repo: A GitRepo instance. Created from root if not provided.
        """
        self._root = root or find_project_root() or Path.cwd()
        self._repository = repository or EngagementRepository(self._root)
        self._health_check = health_check or EngagementHealthCheck(
            root=self._root,
            repository=self._repository,
        )
        self._workflow_orchestrator = (
            workflow_orchestrator or self._create_default_orchestrator()
        )
        self._git = git_repo

    # ── Public API ───────────────────────────────────────────────────

    def create(
        self,
        slug: str,
        workflow_name: str | None = None,
        session_type: str = "greenfield",
        mode: str = "auto",
        description: str = "",
    ) -> StartupResult:
        """Create a new engagement synchronously.

        Performs:
        1. Validate the slug is available
        2. Determine workflow (from session_type or explicit)
        3. Create Engagement model
        4. Create target branch
        5. Run health check proactively
        6. Save engagement state
        7. Record first phase for entry

        For full phase execution, call ``enter_first_phase_async()``
        after this completes successfully.

        Args:
            slug: Unique human-readable identifier for the engagement.
            workflow_name: Explicit workflow name. If None, derived
                from session_type using SESSION_TYPE_MAP.
            session_type: Type of session (greenfield, refactoring,
                get-well, etc.).
            mode: Execution mode ("auto" or "manual"). Defaults to
                "auto".
            description: Human-readable description of the engagement.

        Returns:
            StartupResult with engagement and health check data.

        Raises:
            ValueError: If slug is empty or engagement already exists.
            UnknownWorkflowError: If workflow_name is specified but
                not registered.
        """
        if not slug:
            return StartupResult(
                success=False,
                error="Engagement slug cannot be empty",
            )

        # 1. Check if engagement already exists
        if self._repository.exists(slug):
            return StartupResult(
                success=False,
                error=f"Engagement '{slug}' already exists — use resume() or a different slug",
            )

        # 2. Determine workflow
        resolved_workflow = workflow_name or SESSION_TYPE_MAP.get(
            session_type, "standard"
        )
        if not self._workflow_orchestrator.get_workflow(resolved_workflow):
            raise UnknownWorkflowError(
                f"Workflow '{resolved_workflow}' is not registered "
                f"(session_type={session_type})"
            )

        workflow = self._workflow_orchestrator.get_workflow(resolved_workflow)
        first_phase = workflow.phases[0] if workflow and workflow.phases else None

        # 3. Create Engagement model
        target_branch = f"eng/{slug}"
        engagement = Engagement(
            slug=slug,
            workflow_name=resolved_workflow,
            session_type=session_type,
            current_phase=first_phase,
            status=EngagementStatus.CREATED,
            created_at=datetime.now(),
            last_active=datetime.now(),
            target_branch=target_branch,
            warnings=[],
        )

        logger.info(
            "StartupResumeFlow — creating engagement",
            extra={
                "slug": slug,
                "workflow": resolved_workflow,
                "session_type": session_type,
                "first_phase": first_phase,
                "mode": mode,
            },
        )

        # 4. Create target branch
        branch_result = self._create_branch(target_branch)
        if branch_result:
            engagement.warnings.append(branch_result)

        # 5. Run health check
        report = self._run_proactive_health_check(
            slug=slug,
            engagement=engagement,
        )
        engagement.warnings.extend(report.warnings)

        # 6. Save engagement state
        self._repository.save(engagement)

        # Update status to active
        engagement.status = EngagementStatus.ACTIVE
        engagement.last_active = datetime.now()
        self._repository.save(engagement)

        logger.info(
            "StartupResumeFlow — engagement created",
            extra={
                "slug": slug,
                "branch": target_branch,
                "health_warnings": len(report.warnings),
            },
        )

        return StartupResult(
            success=True,
            engagement=engagement,
            report=report,
            branch_created=True,
            phase_entered=first_phase,
            warnings=engagement.warnings,
        )

    async def enter_first_phase_async(
        self,
        slug: str,
        mode: str = "auto",
    ) -> StartupResult:
        """Enter the first phase of an engagement's workflow (async).

        Dispatches through WorkflowOrchestrator → PhaseOrchestrator
        → StepExecutor chain to execute the first phase.

        Call this after ``create()`` for full auto mode or manual
        phase entry.

        Args:
            slug: Engagement slug.
            mode: Execution mode ("auto" or "manual").

        Returns:
            StartupResult with phase entry status.
        """
        engagement = self._repository.load(slug)
        workflow_name = engagement.workflow_name

        logger.info(
            "StartupResumeFlow — entering first phase (async)",
            extra={
                "slug": slug,
                "workflow": workflow_name,
                "mode": mode,
            },
        )

        try:
            wf_result = await self._workflow_orchestrator.enter_workflow(
                slug=slug,
                workflow_name=workflow_name,
                mode=mode,
            )

            if not wf_result.success:
                return StartupResult(
                    success=False,
                    engagement=engagement,
                    error=f"Failed to enter workflow: {wf_result.error}",
                    warnings=engagement.warnings,
                )

            # Update engagement state
            engagement.status = EngagementStatus.ACTIVE
            engagement.current_phase = wf_result.current_phase
            engagement.last_active = datetime.now()
            self._repository.save(engagement)

            return StartupResult(
                success=True,
                engagement=engagement,
                phase_entered=wf_result.current_phase,
            )

        except Exception as exc:
            logger.error(
                "StartupResumeFlow — async phase entry failed",
                extra={"slug": slug, "error": str(exc)},
            )
            return StartupResult(
                success=False,
                engagement=engagement,
                error=f"Async phase entry failed: {exc}",
            )

    def resume(
        self,
        slug: str,
        mode: str = "auto",
    ) -> StartupResult:
        """Resume an existing engagement synchronously.

        Performs:
        1. Load engagement from repository
        2. Run health check
        3. Re-enter current phase
        4. Validate engagement state

        For full phase re-entry, call ``resume_async()`` after this.

        Args:
            slug: Engagement slug to resume.
            mode: Execution mode ("auto" or "manual").

        Returns:
            StartupResult with engagement and health data.
        """
        # 1. Load engagement
        try:
            engagement = self._repository.load(slug)
        except EngagementNotFoundError:
            return StartupResult(
                success=False,
                error=f"Engagement '{slug}' not found — create() it first",
            )

        # 2. Run health check
        report = self._run_proactive_health_check(
            slug=slug,
            engagement=engagement,
        )
        engagement.warnings.extend(report.warnings)

        # Check for terminal engagement states
        if engagement.status in (
            EngagementStatus.COMPLETED,
            EngagementStatus.ABORTED,
        ):
            return StartupResult(
                success=False,
                engagement=engagement,
                report=report,
                error=(
                    f"Engagement '{slug}' is already "
                    f"{engagement.status.value} — cannot resume"
                ),
                warnings=engagement.warnings,
            )

        # 3. Re-enter active state
        engagement.status = EngagementStatus.ACTIVE
        engagement.last_active = datetime.now()

        # 4. Check branch
        branch_warning = self._check_branch_for_resume(engagement)
        if branch_warning:
            engagement.warnings.append(branch_warning)

        # Save updated engagement
        self._repository.save(engagement)

        logger.info(
            "StartupResumeFlow — engagement resumed",
            extra={
                "slug": slug,
                "current_phase": engagement.current_phase,
                "health_warnings": len(report.warnings),
                "mode": mode,
            },
        )

        return StartupResult(
            success=True,
            engagement=engagement,
            report=report,
            phase_entered=engagement.current_phase,
            warnings=engagement.warnings,
        )

    async def resume_async(
        self,
        slug: str,
        mode: str = "auto",
    ) -> StartupResult:
        """Re-enter the current phase of an engagement (async).

        Dispatches through WorkflowOrchestrator → PhaseOrchestrator
        → StepExecutor to re-enter the phase where the engagement
        left off.

        Call this after ``resume()`` for full phase re-entry.

        Args:
            slug: Engagement slug.
            mode: Execution mode ("auto" or "manual").

        Returns:
            StartupResult with re-entry status.
        """
        engagement = self._repository.load(slug)

        if not engagement.current_phase:
            # No current phase — start at beginning of workflow
            return await self.enter_first_phase_async(slug, mode)

        logger.info(
            "StartupResumeFlow — re-entering phase (async)",
            extra={
                "slug": slug,
                "phase": engagement.current_phase,
                "mode": mode,
            },
        )

        try:
            phase_result = await self._phase_orchestrator.enter_phase(
                slug=slug,
                phase_name=engagement.current_phase,
                mode=mode,
            )

            if not phase_result.success:
                return StartupResult(
                    success=False,
                    engagement=engagement,
                    error=f"Failed to re-enter phase: {phase_result.error}",
                    warnings=engagement.warnings,
                )

            engagement.last_active = datetime.now()
            self._repository.save(engagement)

            return StartupResult(
                success=True,
                engagement=engagement,
                phase_entered=engagement.current_phase,
            )

        except Exception as exc:
            logger.error(
                "StartupResumeFlow — async phase re-entry failed",
                extra={"slug": slug, "error": str(exc)},
            )
            return StartupResult(
                success=False,
                engagement=engagement,
                error=f"Async phase re-entry failed: {exc}",
            )

    async def run_auto_async(
        self,
        slug: str,
    ) -> StartupResult:
        """Run an engagement to completion in full auto mode.

        Dispatches the entire workflow without user prompting.
        When agents need input, automated decisions or defined
        defaults are used. When aggregation fails, escalates to
        user.

        Args:
            slug: Engagement slug.

        Returns:
            StartupResult with completion or escalation status.
        """
        self._validate_engagement(slug)

        logger.info(
            "StartupResumeFlow — running auto mode",
            extra={"slug": slug},
        )

        # Enter workflow in auto mode
        result = await self.enter_first_phase_async(slug, mode="auto")
        if not result.success:
            return result

        # Continue advancing through phases until complete or blocked
        while True:
            wf_result = await self._workflow_orchestrator.advance_workflow(slug)

            if not wf_result.success:
                # Escalation needed
                engagement = self._repository.load(slug)
                return StartupResult(
                    success=False,
                    engagement=engagement,
                    error=(
                        f"Aggregation failure in phase "
                        f"'{wf_result.current_phase}': {wf_result.error}"
                    ),
                    warnings=engagement.warnings,
                )

            if wf_result.status.value == "completed":
                # Mark engagement as completed
                engagement = self._repository.load(slug)
                engagement.status = EngagementStatus.COMPLETED
                engagement.last_active = datetime.now()
                self._repository.save(engagement)

                logger.info(
                    "StartupResumeFlow — auto mode completed",
                    extra={"slug": slug},
                )

                return StartupResult(
                    success=True,
                    engagement=engagement,
                    phase_entered="__completed__",
                )

    def load(self, slug: str) -> StartupResult:
        """Load an engagement from the repository.

        Runs a health check automatically. Does not change
        engagement state (status remains as stored).

        Args:
            slug: Engagement slug to load.

        Returns:
            StartupResult with loaded engagement and health data.
        """
        try:
            engagement = self._repository.load(slug)
        except EngagementNotFoundError:
            return StartupResult(
                success=False,
                error=f"Engagement '{slug}' not found",
            )

        report = self._run_proactive_health_check(
            slug=slug,
            engagement=engagement,
        )

        logger.info(
            "StartupResumeFlow — engagement loaded",
            extra={
                "slug": slug,
                "status": engagement.status.value,
                "health_warnings": len(report.warnings),
            },
        )

        # Combine warnings without duplicates (by type + message)
        seen = {(w.type, w.message) for w in engagement.warnings}
        combined: list[HealthWarning] = list(engagement.warnings)
        for w in report.warnings:
            if (w.type, w.message) not in seen:
                combined.append(w)
                seen.add((w.type, w.message))

        return StartupResult(
            success=True,
            engagement=engagement,
            report=report,
            warnings=combined,
        )

    def list_engagements(self) -> list[Engagement]:
        """List all stored engagements.

        Returns:
            List of all Engagement instances from the repository.
        """
        return self._repository.list_all()

    # ── Properties ───────────────────────────────────────────────────

    @property
    def repository(self) -> EngagementRepository:
        """The underlying EngagementRepository."""
        return self._repository

    @property
    def health_check(self) -> EngagementHealthCheck:
        """The underlying EngagementHealthCheck."""
        return self._health_check

    @property
    def workflow_orchestrator(self) -> WorkflowOrchestrator:
        """The underlying WorkflowOrchestrator."""
        return self._workflow_orchestrator

    # ── Internal Methods ─────────────────────────────────────────────

    def _create_default_orchestrator(self) -> WorkflowOrchestrator:
        """Create a WorkflowOrchestrator with bootstrapped phases
        and default workflows.

        Constructs the full orchestration chain:
           TeamRegistry → StepTemplateRegistry
           → StepDispatcher → SequentialPhaseStrategy → StrategyRunner
           → PhaseOrchestrator (with bootstrapped phases)
           → WorkflowOrchestrator (with default workflows)

        Returns:
            A configured WorkflowOrchestrator instance.
        """
        from harness.phase.orchestrator import PhaseOrchestrator
        from harness.phase.strategy.runner import StrategyRunner
        from harness.phase.strategy.sequential import (
            SequentialPhaseStrategy,
        )
        from harness.phase.dispatcher import StepDispatcher
        from harness.phase.bootstrap import bootstrap_and_register
        from harness.phase.template_registry import (
            StepTemplateRegistry,
        )
        from harness.team.registry import TeamRegistry
        from harness.team.defaults import get_builtin_teams

        # 1. Team registry (built-in teams)
        team_registry = TeamRegistry(builtin=get_builtin_teams())

        # 2. Step template registry
        template_registry = StepTemplateRegistry(
            team_registry=team_registry,
        )

        # 3. Minimal StepDispatcher (stub dispatch — real dispatch
        #    requires full async agent infrastructure)
        dispatcher = StepDispatcher(
            team_registry=team_registry,
        )

        # 4. Phase execution strategy
        sequential = SequentialPhaseStrategy(dispatcher=dispatcher)
        strategy_runner = StrategyRunner(sequential=sequential)

        # 5. PhaseOrchestrator
        phase_orchestrator = PhaseOrchestrator(
            strategy_runner=strategy_runner,
        )

        # 6. Bootstrap phase definitions from config and register
        bootstrap_and_register(
            orchestrator=phase_orchestrator,
            template_registry=template_registry,
            phases_path=self._root / ".harness" / "phases.yaml"
            if self._root else None,
            templates_path=self._root / ".harness" / "step_templates.yaml"
            if self._root else None,
        )

        # 7. Create WorkflowOrchestrator
        orchestrator = WorkflowOrchestrator(
            phase_orchestrator=phase_orchestrator,
        )
        orchestrator.register_workflows(DEFAULT_WORKFLOWS)

        return orchestrator

    def _get_git(self) -> GitRepo | None:
        """Lazy-create and return a GitRepo instance."""
        if self._git is None:
            try:
                self._git = GitRepo(self._root)
            except Exception:
                self._git = None
        return self._git

    def _create_branch(self, branch_name: str) -> HealthWarning | None:
        """Create a git branch for the engagement.

        Creates the branch only if it doesn't already exist.
        Base it on the current branch.

        Args:
            branch_name: Name of the branch to create (e.g. "eng/slug").

        Returns:
            HealthWarning if branch creation failed, or None on success.
        """
        git = self._get_git()
        if git is None:
            return HealthWarning(
                type="no_git_repo",
                message=(
                    f"Cannot create branch '{branch_name}': "
                    f"not a git repository"
                ),
            )

        try:
            # Check if branch already exists
            try:
                git.rev_parse(f"refs/heads/{branch_name}")
                # Branch already exists — not an error
                return None
            except GitOperationError:
                pass

            # Create the branch from current HEAD
            git.checkout(branch_name, create=True)

            logger.info(
                "StartupResumeFlow — branch created",
                extra={"branch": branch_name},
            )
            return None

        except Exception as exc:
            return HealthWarning(
                type="branch_create_error",
                message=f"Error creating branch '{branch_name}': {exc}",
            )

    def _run_proactive_health_check(
        self,
        slug: str,
        engagement: Engagement | None = None,
    ) -> HealthReport:
        """Run a proactive health check before entering a phase.

        Checks:
        - Branch alignment
        - Dirty repo state
        - Missing branch
        - Corrupt state

        Args:
            slug: Engagement slug to check.
            engagement: Pre-loaded engagement (optional). If
                provided, branch alignment uses the engagement's
                target_branch.

        Returns:
            HealthReport with check results.
        """
        try:
            report = self._health_check.check(slug)

            # If engagement was provided, add it to the report
            if engagement is not None:
                report.engagement = engagement

            # Log health status
            if report.warnings:
                logger.info(
                    "StartupResumeFlow — health check warnings",
                    extra={
                        "slug": slug,
                        "warnings": [
                            w.type for w in report.warnings
                        ],
                    },
                )
            else:
                logger.debug(
                    "StartupResumeFlow — health check OK",
                    extra={"slug": slug},
                )

            return report

        except Exception as exc:
            logger.error(
                "StartupResumeFlow — health check failed",
                extra={"slug": slug, "error": str(exc)},
            )
            return HealthReport(
                all_ok=False,
                slug=slug,
                warnings=[
                    HealthWarning(
                        type="health_check_error",
                        message=f"Health check failed: {exc}",
                    )
                ],
            )

    def _check_branch_for_resume(
        self,
        engagement: Engagement,
    ) -> HealthWarning | None:
        """Check branch state when resuming an engagement.

        Checks if the target branch exists and if the current
        branch matches.

        Args:
            engagement: The engagement being resumed.

        Returns:
            HealthWarning if there's a branch issue, or None.
        """
        if not engagement.target_branch:
            return None

        git = self._get_git()
        if git is None:
            return None  # Not a git repo — can't check

        try:
            current_branch = git.branch()
        except GitOperationError:
            return None  # Not a git repo

        if current_branch != engagement.target_branch:
            # Try to switch to the engagement's branch
            try:
                git.checkout(engagement.target_branch)
            except GitCheckoutError:
                # Check if branch exists
                try:
                    git.rev_parse(f"refs/heads/{engagement.target_branch}")
                    # Branch exists but checkout failed (dirty repo)
                    return HealthWarning(
                        type="branch_switch_failed",
                        message=(
                            f"Cannot switch to target branch "
                            f"'{engagement.target_branch}' — "
                            f"working tree has uncommitted changes"
                        ),
                    )
                except GitOperationError:
                    return HealthWarning(
                        type="branch_missing",
                        message=(
                            f"Target branch '{engagement.target_branch}' "
                            f"does not exist — create it with "
                            f"git checkout -b {engagement.target_branch}"
                        ),
                    )

        return None

    def _validate_engagement(self, slug: str) -> Engagement:
        """Validate that an engagement exists and is active.

        Args:
            slug: Engagement slug.

        Returns:
            The loaded Engagement.

        Raises:
            EngagementNotFoundError: If engagement doesn't exist.
            ValueError: If engagement is in a terminal state.
        """
        engagement = self._repository.load(slug)

        if engagement.status in (
            EngagementStatus.COMPLETED,
            EngagementStatus.ABORTED,
        ):
            raise ValueError(
                f"Engagement '{slug}' is {engagement.status.value} "
                f"— cannot execute steps"
            )

        return engagement


# ── Convenience Functions ───────────────────────────────────────────


def create_engagement(
    slug: str,
    workflow_name: str | None = None,
    session_type: str = "greenfield",
    mode: str = "auto",
    root: Path | None = None,
) -> StartupResult:
    """Convenience function to create a new engagement.

    Args:
        slug: Engagement slug.
        workflow_name: Explicit workflow name (derived from
            session_type if None).
        session_type: Session type (greenfield, refactoring, etc.).
        mode: Execution mode ("auto" or "manual").
        root: Project root directory.

    Returns:
        StartupResult with engagement and health data.
    """
    flow = StartupResumeFlow(root=root)
    return flow.create(
        slug=slug,
        workflow_name=workflow_name,
        session_type=session_type,
        mode=mode,
    )


def resume_engagement(
    slug: str,
    mode: str = "auto",
    root: Path | None = None,
) -> StartupResult:
    """Convenience function to resume an engagement.

    Args:
        slug: Engagement slug to resume.
        mode: Execution mode ("auto" or "manual").
        root: Project root directory.

    Returns:
        StartupResult with engagement and health data.
    """
    flow = StartupResumeFlow(root=root)
    return flow.resume(slug=slug, mode=mode)


def load_engagement(
    slug: str,
    root: Path | None = None,
) -> StartupResult:
    """Convenience function to load an engagement.

    Args:
        slug: Engagement slug to load.
        root: Project root directory.

    Returns:
        StartupResult with loaded engagement and health data.
    """
    flow = StartupResumeFlow(root=root)
    return flow.load(slug)
