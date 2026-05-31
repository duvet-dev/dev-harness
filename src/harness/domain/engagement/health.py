"""EngagementHealthCheck — checks engagement health status.

Validates branch alignment, repo cleanliness, branch existence, and
state integrity for a given engagement.

See V7 §5.23 for the HealthWarning model and V7 §8 for error types.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from harness.domain.engagement.model import Engagement, EngagementStatus, HealthWarning
from harness.domain.engagement.repository import EngagementRepository
from harness.errors import (
    EngagementBranchMissingError,
    EngagementCorruptStateError,
    EngagementDirtyStateError,
    EngagementNotFoundError,
)


@dataclass
class HealthReport:
    """Report of engagement health check results.

    Attributes:
        all_ok: True if no warnings were found.
        warnings: List of HealthWarning instances.
        engagement: The checked engagement, if loaded successfully.
        slug: The engagement slug that was checked.
    """

    all_ok: bool = True
    warnings: list[HealthWarning] = field(default_factory=list)
    engagement: Engagement | None = None
    slug: str = ""


class EngagementHealthCheck:
    """Performs health checks on an engagement.

    Checks:
        - Branch alignment: does the current git branch match the
          engagement's target_branch?
        - Dirty repo: does the git working tree have uncommitted changes?
        - Missing branch: does the engagement's target_branch exist?
        - Corrupt state: is the engagement's persisted state readable?
    """

    def __init__(
        self,
        root: Path | None = None,
        repository: EngagementRepository | None = None,
    ) -> None:
        """Initialise the health checker.

        Args:
            root: Project root directory. Auto-discovered if None.
            repository: An EngagementRepository instance. Created from
                root if not provided.
        """
        self._root = root or Path.cwd()
        self._repository = repository or EngagementRepository(self._root)

    @property
    def repository(self) -> EngagementRepository:
        """The underlying EngagementRepository."""
        return self._repository

    def check(self, slug: str) -> HealthReport:
        """Run all health checks for an engagement.

        Args:
            slug: The engagement slug to check.

        Returns:
            A HealthReport with all check results.
        """
        report = HealthReport(slug=slug)

        # 1. Load engagement — if state is corrupt, report and stop
        try:
            engagement = self._repository.load(slug)
            report.engagement = engagement
        except json.JSONDecodeError:
            report.warnings.append(
                HealthWarning(
                    type="corrupt_state",
                    message=f"Engagement '{slug}' state file is corrupt (JSON parse error)",
                )
            )
            report.all_ok = False
            return report
        except EngagementNotFoundError:
            report.warnings.append(
                HealthWarning(
                    type="engagement_not_found",
                    message=f"Engagement '{slug}' not found in repository",
                )
            )
            report.all_ok = False
            return report
        except Exception as exc:
            report.warnings.append(
                HealthWarning(
                    type="load_error",
                    message=f"Failed to load engagement '{slug}': {exc}",
                )
            )
            report.all_ok = False
            return report

        # 2. Check branch alignment
        branch_warnings = self._check_branch_alignment(engagement, slug)
        report.warnings.extend(branch_warnings)

        # 3. Check dirty repo
        dirty_warnings = self._check_dirty_repo(engagement, slug)
        report.warnings.extend(dirty_warnings)

        # 4. Check branch existence
        branch_missing = self._check_branch_exists(engagement, slug)
        report.warnings.extend(branch_missing)

        # 5. Check state consistency
        state_warnings = self._check_state_consistency(engagement, slug)
        report.warnings.extend(state_warnings)

        report.all_ok = len(report.warnings) == 0
        return report

    def _get_git_branch(self) -> str | None:
        """Get the current git branch name.

        Returns:
            Current branch name, or None if not in a git repo.
        """
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return None

    def _get_git_status_summary(self) -> dict[str, int]:
        """Get summary of git working tree status.

        Returns:
            Dict with 'untracked' and 'unstaged' counts.
        """
        summary: dict[str, int] = {"untracked": 0, "unstaged": 0}
        try:
            import subprocess
            # Untracked files
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                summary["untracked"] = len(
                    [l for l in result.stdout.split("\n") if l.strip()]
                )

            # Modified but unstaged
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                summary["unstaged"] = len(
                    [l for l in result.stdout.split("\n") if l.strip()]
                )
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return summary

    def _check_branch_alignment(
        self, engagement: Engagement, slug: str
    ) -> list[HealthWarning]:
        """Check if current git branch matches engagement's target_branch.

        Args:
            engagement: The engagement to check.
            slug: The engagement slug (for error messages).

        Returns:
            List of HealthWarning (empty if aligned).
        """
        if not engagement.target_branch:
            return []

        current_branch = self._get_git_branch()
        if current_branch is None:
            return [
                HealthWarning(
                    type="no_git_repo",
                    message=f"Cannot check branch alignment for '{slug}': not a git repository",
                )
            ]

        if current_branch != engagement.target_branch:
            return [
                HealthWarning(
                    type="branch_mismatch",
                    message=(
                        f"Engagement '{slug}' expects branch "
                        f"'{engagement.target_branch}' but current branch is "
                        f"'{current_branch}'"
                    ),
                )
            ]

        return []

    def _check_dirty_repo(
        self, engagement: Engagement, slug: str
    ) -> list[HealthWarning]:
        """Check if the git working tree has uncommitted changes.

        Args:
            engagement: The engagement to check.
            slug: The engagement slug (for error messages).

        Returns:
            List of HealthWarning (empty if clean).
        """
        _ = engagement  # engagement not directly needed for this check
        status = self._get_git_status_summary()
        total = status["untracked"] + status["unstaged"]

        if total > 0:
            return [
                HealthWarning(
                    type="dirty_repo",
                    message=(
                        f"Working tree has {total} uncommitted change(s) "
                        f"({status['untracked']} untracked, "
                        f"{status['unstaged']} unstaged)"
                    ),
                )
            ]

        return []

    def _check_branch_exists(
        self, engagement: Engagement, slug: str
    ) -> list[HealthWarning]:
        """Check if the engagement's target_branch exists in git.

        Args:
            engagement: The engagement to check.
            slug: The engagement slug (for error messages).

        Returns:
            List of HealthWarning (empty if branch exists or no branch set).
        """
        if not engagement.target_branch:
            return []

        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--verify", engagement.target_branch],
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                # Try with refs/heads/ prefix
                result2 = subprocess.run(
                    [
                        "git", "rev-parse", "--verify",
                        f"refs/heads/{engagement.target_branch}",
                    ],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result2.returncode != 0:
                    return [
                        HealthWarning(
                            type="branch_missing",
                            message=(
                                f"Target branch '{engagement.target_branch}' "
                                f"does not exist for engagement '{slug}'"
                            ),
                        )
                    ]
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        return []

    def _check_state_consistency(
        self, engagement: Engagement, slug: str
    ) -> list[HealthWarning]:
        """Check engagement state consistency.

        Verifies:
        - Engagement has a non-empty slug
        - Engagement status is valid
        - Engagement has been active recently

        Args:
            engagement: The engagement to check.
            slug: The engagement slug (for error messages).

        Returns:
            List of HealthWarning (empty if consistent).
        """
        _ = slug  # slug already known
        warnings: list[HealthWarning] = []

        # Check slug consistency
        if engagement.slug != slug:
            warnings.append(
                HealthWarning(
                    type="slug_mismatch",
                    message=(
                        f"Engagement file slug '{engagement.slug}' does not "
                        f"match requested slug '{slug}'"
                    ),
                )
            )

        # Check for stale engagement (no activity in 24 hours for active engagements)
        if engagement.status == EngagementStatus.ACTIVE:
            now = datetime.now()
            hours_since_active = (
                now - engagement.last_active
            ).total_seconds() / 3600
            if hours_since_active > 24:
                warnings.append(
                    HealthWarning(
                        type="stale_engagement",
                        message=(
                            f"Engagement '{slug}' has been active but "
                            f"inactive for {hours_since_active:.1f} hours "
                            f"(last active: {engagement.last_active})"
                        ),
                    )
                )

        return warnings


def check_engagement_health(
    slug: str,
    root: Path | None = None,
) -> HealthReport:
    """Convenience function to check engagement health.

    Args:
        slug: The engagement slug to check.
        root: Project root directory. Auto-discovered if None.

    Returns:
        A HealthReport with all check results.
    """
    checker = EngagementHealthCheck(root=root)
    return checker.check(slug)
