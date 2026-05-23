"""State freshness tracking for branch management.

Tracks whether the harness state is current relative to the git branch HEAD.
A "stale" state means the branch has new commits (e.g. from a merge) that
the harness hasn't processed yet.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from harness.paths import get_freshness_path


@dataclass
class FreshnessRecord:
    """Record of when the harness last reconciled with its git branch."""

    branch: str
    head_sha: str
    last_reconciled: str  # ISO-8601
    stale: bool = False

    def mark_stale(self) -> "FreshnessRecord":
        return FreshnessRecord(
            branch=self.branch,
            head_sha=self.head_sha,
            last_reconciled=self.last_reconciled,
            stale=True,
        )

    def mark_fresh(self, head_sha: str) -> "FreshnessRecord":
        return FreshnessRecord(
            branch=self.branch,
            head_sha=head_sha,
            last_reconciled=datetime.now(timezone.utc).isoformat(),
            stale=False,
        )


FRESHNESS_FILE = ".harness-freshness.yaml"


def load_freshness(project_root: Path) -> Optional[FreshnessRecord]:
    """Load the freshness record from the project root, or None."""
    path = get_freshness_path(project_root)
    if not path.is_file():
        return None
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return FreshnessRecord(
        branch=raw.get("branch", ""),
        head_sha=raw.get("head_sha", ""),
        last_reconciled=raw.get("last_reconciled", ""),
        stale=raw.get("stale", False),
    )


def save_freshness(record: FreshnessRecord, project_root: Path) -> None:
    """Persist the freshness record."""
    path = get_freshness_path(project_root)
    data = {
        "branch": record.branch,
        "head_sha": record.head_sha,
        "last_reconciled": record.last_reconciled,
        "stale": record.stale,
    }
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
