"""Branch reconciliation — detect and record changes since last known state.

Produces a ReconciliationReport summarising what changed between the last
harness snapshot and the current git state. Supports the "catch-up" mode
described in R9.2 and R12 (side-channel coding).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from harness.paths import get_harness_dir, get_harness_state_path
from harness.scm.git import GitRepo, LogEntry


@dataclass
class DeltaEntry:
    """A single change detected during reconciliation."""

    path: str
    change_type: str  # added | modified | deleted
    old_sha: Optional[str] = None
    new_sha: Optional[str] = None


@dataclass
class ReconciliationReport:
    """Summary of all changes since the last known harness state."""

    engagement_id: str
    stale_commits: List[LogEntry] = field(default_factory=list)
    delta: List[DeltaEntry] = field(default_factory=list)
    merge_detected: bool = False
    external_changes: int = 0
    harness_managed_changes: int = 0


class BranchReconciler:
    """Reconcile git state against the last-known harness state."""

    def __init__(self, repo: GitRepo, project_root: Path) -> None:
        self._repo = repo
        self._project_root = project_root

    def reconcile(
        self,
        last_known_sha: str,
        engagement_id: str,
        watched_branch: str = "main",
    ) -> ReconciliationReport:
        """Produce a reconciliation report from *last_known_sha* to HEAD.

        Args:
            last_known_sha: The SHA of the last reconciliation point.
            engagement_id: The engagement being reconciled.
            watched_branch: Branch to monitor for external merges.
        """
        # Get commits since last known state
        stale_commits = self._repo.log(
            since=last_known_sha,
            max_count=100,
        )
        # Filter out empty results from edge cases
        stale_commits = [c for c in stale_commits if c.commit_hash != last_known_sha]

        # Check for merge on watched branch
        merge_detected = self._repo.merge_detected(watched_branch)

        # Build delta from git diff
        delta = []
        harness_files_prefix = f".harness{Path('/')}"
        try:
            diff = self._repo.diff(ref_a=last_known_sha, ref_b="HEAD")
            for f in diff.files_changed:
                change_type = "modified"
                if f.endswith((".new", ".added")):
                    change_type = "added"
                delta.append(DeltaEntry(
                    path=f,
                    change_type=change_type,
                ))
        except Exception:
            # diff against unknown SHA — skip file-level delta
            pass

        # Classify changes as external vs harness-managed
        external = sum(
            1 for d in delta
            if not d.path.startswith(str(get_harness_dir(self._project_root)))
            and not d.path.startswith(str(get_harness_state_path(self._project_root)))
        )
        harness_managed = len(delta) - external

        return ReconciliationReport(
            engagement_id=engagement_id,
            stale_commits=stale_commits,
            delta=delta,
            merge_detected=merge_detected,
            external_changes=external,
            harness_managed_changes=harness_managed,
        )
