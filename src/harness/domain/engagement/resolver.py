"""Active engagement resolver.

Determines which engagement is active for the current branch by:
1. Auto-detecting ``eng/<slug>`` from the branch name
2. Falling back to the active engagements mapping file which maps branch → slug
"""

import re
from pathlib import Path
from typing import Optional

import yaml

from harness.paths import get_active_engagements_path

ENG_BRANCH_PATTERN = re.compile(r"^eng/(?P<slug>[a-z0-9-]+)$")
# ACTIVE_ENGAGEMENTS_FILE kept for backward compatibility
ACTIVE_ENGAGEMENTS_FILE = ".harness/active-engagements.yaml"


def resolve_active_engagement(root: Path) -> Optional[str]:
    """Return the active engagement slug for the current branch, or ``None``.

    First checks the current branch name for ``eng/<slug>`` pattern.
    Falls back to reading the active engagements mapping file.
    """
    from harness.scm.git import GitRepo

    repo = GitRepo(root)
    branch = repo.branch()

    # Auto-detect: branch name matches eng/<slug>
    match = ENG_BRANCH_PATTERN.match(branch)
    if match:
        return match.group("slug")

    # Fall back to YAML mapping
    mapping = load_active_engagements(root)
    branch_map = mapping.get("branches", {})
    return branch_map.get(branch)


def load_active_engagements(root: Path) -> dict:
    """Read the active engagements mapping file and return as a dict.

    Returns ``{"branches": {}}`` if the file doesn't exist or is empty.
    """
    path = get_active_engagements_path(root)
    if not path.is_file():
        return {"branches": {}}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    # Ensure 'branches' key exists
    if "branches" not in data:
        data["branches"] = {}
    return data


def save_active_engagements(root: Path, mapping: dict) -> None:
    """Write *mapping* to the active engagements mapping file.

    The *mapping* dict should have a ``branches`` key.
    """
    path = get_active_engagements_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(mapping, f, default_flow_style=False, sort_keys=False)
