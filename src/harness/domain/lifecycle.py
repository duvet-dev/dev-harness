"""Engagement lifecycle — directory creation, metadata, active tracking.

Replaces ``harness.engagement.lifecycle``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from harness.paths import (
    get_active_engagements_path,
    get_engagement_dir,
    get_engagement_md,
    get_engagement_plan_md,
    get_engagement_plan_yaml,
    get_engagement_waves_dir,
    get_engagement_yaml,
)

ENGAGEMENTS_DIR = ".harness/engagements"
ACTIVE_ENGAGEMENTS_FILE = ".harness/active-engagements.yaml"
ENGAGEMENT_MD = "engagement.md"
ENGAGEMENT_YAML_FILE = "engagement.yaml"
PLAN_MD = "plan.md"
PLAN_YAML = "plan.yaml"
WAVES_DIR = "waves"


def create_engagement_dir(root: Path, slug: str) -> Path:
    """Create the engagement directory structure."""
    eng_dir = get_engagement_dir(root, slug)
    if eng_dir.exists():
        raise FileExistsError(
            f"Engagement '{slug}' already exists at {eng_dir}"
        )
    eng_dir.mkdir(parents=True, exist_ok=True)
    get_engagement_md(root, slug).write_text("")
    get_engagement_plan_md(root, slug).write_text("")
    plan_yaml_path = get_engagement_plan_yaml(root, slug)
    if not plan_yaml_path.is_file():
        plan_yaml_path.write_text("waves: []\n")
    eng_yaml_path = get_engagement_yaml(root, slug)
    if not eng_yaml_path.is_file():
        with open(eng_yaml_path, "w") as f:
            yaml.dump({"slug": slug}, f, default_flow_style=False, sort_keys=False)
    get_engagement_waves_dir(root, slug).mkdir(exist_ok=True)
    return eng_dir


def write_engagement_metadata(
    engagement_dir: Path,
    name: str,
    slug: str,
    branch: str,
    session_type: Optional[str] = None,
    allow_refactoring_suggestions: Optional[bool] = None,
) -> None:
    """Write engagement.md and engagement.yaml metadata."""
    now = datetime.now(timezone.utc).isoformat()
    frontmatter = {
        "title": name,
        "slug": slug,
        "status": "planning",
        "created_at": now,
        "branch": branch,
    }
    content = (
        "---\n"
        + yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        + "---\n"
        + f"\n# {name}\n\n"
    )
    (engagement_dir / "engagement.md").write_text(content)
    eng_yaml_path = engagement_dir / "engagement.yaml"
    if eng_yaml_path.is_file():
        with open(eng_yaml_path) as f:
            yaml_data = yaml.safe_load(f) or {}
    else:
        yaml_data = {"slug": slug}
    yaml_data.setdefault("slug", slug)
    if session_type is not None:
        yaml_data["session_type"] = session_type
    if allow_refactoring_suggestions is not None:
        yaml_data["allow_refactoring_suggestions"] = allow_refactoring_suggestions
    with open(eng_yaml_path, "w") as f:
        yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)


def set_active_engagement(root: Path, slug: str) -> None:
    """Set slug as the active engagement for the current branch."""
    md_file = get_engagement_md(root, slug)
    if not md_file.is_file():
        raise ValueError(f"Engagement '{slug}' not found at {md_file}")
    from harness.scm.git import GitRepo
    repo = GitRepo(root)
    branch = repo.branch()
    mapping = _load_active_mapping(root)
    mapping.setdefault("branches", {})[branch] = slug
    _save_active_mapping(root, mapping)


def close_engagement(root: Path, slug: str) -> dict:
    """Close an engagement (status=completed)."""
    md_file = get_engagement_md(root, slug)
    if not md_file.is_file():
        raise ValueError(f"Engagement '{slug}' not found at {md_file}")
    metadata = _parse_engagement_md(md_file)
    metadata["status"] = "completed"
    metadata["completed_at"] = datetime.now(timezone.utc).isoformat()
    content = (
        "---\n"
        + yaml.dump(metadata, default_flow_style=False, sort_keys=False)
        + "---\n"
        + f"\n# {metadata.get('title', slug)}\n\n"
    )
    md_file.write_text(content)
    mapping = _load_active_mapping(root)
    branches = mapping.get("branches", {})
    to_remove = [b for b, s in branches.items() if s == slug]
    for b in to_remove:
        del branches[b]
    _save_active_mapping(root, mapping)
    return metadata


def _load_active_mapping(root: Path) -> dict:
    path = get_active_engagements_path(root)
    if not path.is_file():
        return {"branches": {}}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    if "branches" not in data:
        data["branches"] = {}
    return data


def _save_active_mapping(root: Path, mapping: dict) -> None:
    path = get_active_engagements_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(mapping, f, default_flow_style=False, sort_keys=False)


def update_active_engagement_mapping(root: Path, old_slug: str, new_slug: str) -> None:
    mapping = _load_active_mapping(root)
    branches = mapping.get("branches", {})
    changed = False
    for branch, slug in list(branches.items()):
        if slug == old_slug:
            branches[branch] = new_slug
            changed = True
    if changed:
        _save_active_mapping(root, mapping)


def read_active_engagement(root: Path) -> Optional[str]:
    """Return active engagement slug for current branch, or None."""
    try:
        from harness.scm.git import GitRepo
        repo = GitRepo(root)
        branch = repo.branch()
    except Exception:
        return None
    mapping = _load_active_mapping(root)
    return mapping.get("branches", {}).get(branch)


def _parse_engagement_md(path: Path) -> dict:
    text = path.read_text()
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def engagement_dir_for(root: Path, slug: str) -> Path:
    return get_engagement_dir(root, slug)


def slugify(name: str) -> str:
    slug = name.lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug
