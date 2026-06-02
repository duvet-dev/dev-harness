"""Active engagement resolver.

Replaces ``harness.engagement.resolver``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

from harness.paths import get_active_engagements_path

ENG_BRANCH_PATTERN = re.compile(r"^eng/(?P<slug>[a-z0-9-]+)$")
ACTIVE_ENGAGEMENTS_FILE = ".harness/active-engagements.yaml"


def resolve_active_engagement(root: Path) -> Optional[str]:
    from harness.scm.git import GitRepo
    repo = GitRepo(root)
    branch = repo.branch()
    match = ENG_BRANCH_PATTERN.match(branch)
    if match:
        return match.group("slug")
    mapping = load_active_engagements(root)
    branch_map = mapping.get("branches", {})
    return branch_map.get(branch)


def load_active_engagements(root: Path) -> dict:
    path = get_active_engagements_path(root)
    if not path.is_file():
        return {"branches": {}}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    if "branches" not in data:
        data["branches"] = {}
    return data


def save_active_engagements(root: Path, mapping: dict) -> None:
    path = get_active_engagements_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(mapping, f, default_flow_style=False, sort_keys=False)
