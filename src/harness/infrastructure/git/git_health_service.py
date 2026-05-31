"""Git-related health check service.

Provides ``GitHealthChecker`` for checking git state and fixing
common git-related issues.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional, Protocol

import yaml

from harness.domain.health import HealthCheck, _result
from harness.domain.interfaces.git import GitRepo as GitRepoProtocol
from harness.paths import get_engagement_yaml


class EngagementStoreProtocol(Protocol):
    """Minimal engagement store interface needed by GitHealthChecker."""

    def read_active_engagement(self, root: Path) -> Optional[dict[str, Any]]: ...


class FreshnessStoreProtocol(Protocol):
    """Minimal freshness store interface needed by GitHealthChecker."""

    def load(self, root: Path) -> Any: ...
    def save(self, record: Any, root: Path) -> None: ...


class GitHealthChecker:
    """Health checks and fixes for git-related concerns.

    Args:
        git_repo: An object with ``branch()`` and ``status()`` methods
            (e.g. ``GitRepo``).
        engagement_store: An object with ``read_active_engagement(root)``
            that returns the active engagement dict or ``None``.
        freshness_store: An object with ``load(root)`` and ``save(record, root)``
            for freshness state.
    """

    def __init__(
        self,
        git_repo: GitRepoProtocol,
        engagement_store: EngagementStoreProtocol,
        freshness_store: FreshnessStoreProtocol | None = None,
    ) -> None:
        self._git = git_repo
        self._engagements = engagement_store
        self._freshness = freshness_store

    # ── Checks ──────────────────────────────────────────────────────────

    def check_branch_match(self, root: Path) -> HealthCheck:
        """Verify current git branch matches the active engagement's stored branch."""
        try:
            current_branch = self._git.branch()

            active = self._engagements.read_active_engagement(root)
            if active is None:
                return _result(
                    "branch-match", "pass",
                    "No active engagement — skipping branch check.",
                )

            slug = active.get("slug") if isinstance(active, dict) else str(active)

            eng_yaml_path = get_engagement_yaml(root, slug)
            if not eng_yaml_path.is_file():
                return _result(
                    "branch-match", "warn",
                    f"Engagement '{slug}' has no engagement.yaml — cannot verify branch.",
                )

            with open(eng_yaml_path) as f:
                eng_data = yaml.safe_load(f) or {}

            expected_branch = eng_data.get("branch", f"eng/{slug}")

            if current_branch != expected_branch:
                return _result(
                    "branch-match", "warn",
                    f"Current branch '{current_branch}' does not match engagement "
                    f"'{slug}' branch '{expected_branch}'.",
                    severity="BRANCH",
                    fix=f"git checkout {expected_branch}",
                )

            return _result(
                "branch-match", "pass",
                f"On correct branch '{current_branch}' for engagement '{slug}'.",
            )

        except Exception as exc:
            return _result(
                "branch-match", "warn",
                f"Cannot verify branch match: {exc}",
            )

    def check_git_clean(self, root: Path) -> HealthCheck:
        """Verify the git working tree has no uncommitted changes."""
        try:
            status = self._git.status()
            untracked = len(status.untracked) if hasattr(status, 'untracked') else 0
            unstaged = len(status.unstaged) if hasattr(status, 'unstaged') else 0
            total = untracked + unstaged

            if total == 0:
                return _result("git-clean", "pass", "Git working tree is clean.")
            return _result(
                "git-clean", "warn",
                f"Git working tree has {total} uncommitted change(s) "
                f"({untracked} untracked, {unstaged} unstaged).",
                fix="git add -A && git commit",
            )
        except Exception as exc:
            return _result("git-clean", "warn", f"Cannot check git state: {exc}")

    # ── Fixes ───────────────────────────────────────────────────────────

    def fix_branch_match(self, root: Path) -> list[str]:
        """Fix branch mismatch by updating engagement.yaml with the current branch.

        Returns a list of fix messages describing what was changed.
        """
        messages: list[str] = []
        try:
            current_branch = self._git.branch()

            active = self._engagements.read_active_engagement(root)
            if active is None:
                messages.append("No active engagement — cannot fix branch.")
                return messages

            slug = active.get("slug") if isinstance(active, dict) else str(active)
            eng_yaml_path = get_engagement_yaml(root, slug)

            if not eng_yaml_path.is_file():
                messages.append(f"Engagement '{slug}' has no engagement.yaml.")
                return messages

            with open(eng_yaml_path) as f:
                yaml_data = yaml.safe_load(f) or {}

            old_branch = yaml_data.get("branch", "(not set)")
            yaml_data["branch"] = current_branch

            with open(eng_yaml_path, "w") as f:
                yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

            messages.append(f"Branch updated: {old_branch} → {current_branch}")
        except Exception as exc:
            messages.append(f"Branch fix failed: {exc}")

        return messages

    def fix_git_state(self, root: Path) -> list[str]:
        """Fix stale engagement state by refreshing freshness record.

        Returns a list of fix messages describing what was changed.
        """
        messages: list[str] = []
        try:
            current_branch = self._git.branch()

            current_head = self._get_head_sha(root)

            if self._freshness is None:
                messages.append("No freshness store configured — cannot fix git state.")
                return messages

            freshness = self._freshness.load(root)
            if freshness and getattr(freshness, "stale", False):
                new_record = freshness.mark_fresh(current_head)
                self._freshness.save(new_record, root)
                messages.append("Engagement state refreshed (staleness cleared).")
            else:
                messages.append("Engagement state is already fresh.")
        except Exception as exc:
            messages.append(f"Git state fix failed: {exc}")

        return messages

    # ── Private helpers ─────────────────────────────────────────────────

    @staticmethod
    def _get_head_sha(root: Path) -> str:
        """Get the current HEAD SHA via git command."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root, capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"


__all__ = [
    "GitHealthChecker",
    "GitRepoProtocol",
    "EngagementStoreProtocol",
    "FreshnessStoreProtocol",
]
