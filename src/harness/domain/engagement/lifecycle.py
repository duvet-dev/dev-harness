"""Engagement lifecycle operations.

Functions for creating, activating, and closing engagements
within the ``.harness/engagements/<slug>/`` directory structure.
"""

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

# ── Deprecated constants — re-exported from harness.paths ──────────────────
# These are kept for backward compatibility only.
# All new code should use the path resolver functions from harness.paths.

from harness.paths import (  # noqa: F401
    ENGAGEMENTS_DIR,
    ACTIVE_ENGAGEMENTS_FILE,
    ENGAGEMENT_MD,
    ENGAGEMENT_YAML_FILE,
    PLAN_MD,
    PLAN_YAML,
    WAVES_DIR,
)


# ── Directory / metadata creation ─────────────────────────────────────────


def create_engagement_dir(root: Path, slug: str) -> Path:
    """Create the engagement directory structure under ``.harness/engagements/<slug>/``.

    Creates::

        .harness/engagements/<slug>/
            engagement.md       (empty placeholder — use write_engagement_metadata)
            engagement.yaml     (structured metadata, including session type)
            plan.md             (empty placeholder)
            plan.yaml           (initial plan)
            waves/              (empty dir)

    Phase artifacts are lazily created on first write by the session loop.

    Raises ``FileExistsError`` if the slug directory already exists.

    Returns the engagement directory ``Path``.
    """
    eng_dir = get_engagement_dir(root, slug)
    if eng_dir.exists():
        raise FileExistsError(
            f"Engagement '{slug}' already exists at {eng_dir}"
        )

    eng_dir.mkdir(parents=True, exist_ok=True)

    # Create the engagement.md and plan.md placeholders
    get_engagement_md(root, slug).write_text("")
    get_engagement_plan_md(root, slug).write_text("")

    # Create initial plan.yaml (structured wave metadata)
    plan_yaml_path = get_engagement_plan_yaml(root, slug)
    if not plan_yaml_path.is_file():
        plan_yaml_path.write_text("waves: []\n")

    # Create initial engagement.yaml (structured metadata)
    eng_yaml_path = get_engagement_yaml(root, slug)
    if not eng_yaml_path.is_file():
        import yaml as _yaml
        with open(eng_yaml_path, "w") as f:
            _yaml.dump({"slug": slug}, f, default_flow_style=False, sort_keys=False)

    # Create the waves subdirectory (phase artifacts created on demand)
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
    """Write ``engagement.md`` with YAML frontmatter and ``engagement.yaml``.

    Frontmatter includes: title, slug, status (planning), created_at,
    and branch.

    Also writes/updates ``engagement.yaml`` with structured metadata
    including optional session_type and allow_refactoring_suggestions.
    """
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
    (engagement_dir / ENGAGEMENT_MD).write_text(content)

    # Also write/update structured engagement.yaml
    eng_yaml_path = engagement_dir / ENGAGEMENT_YAML_FILE
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


# ── Active engagement management ──────────────────────────────────────────


def set_active_engagement(root: Path, slug: str) -> None:
    """Set *slug* as the active engagement for the current branch.

    Validates that the engagement directory exists.
    Gets the current branch name via ``GitRepo`` and writes to
    the active engagements mapping file.

    Raises ``ValueError`` if the engagement doesn't exist.
    """
    md_file = get_engagement_md(root, slug)
    if not md_file.is_file():
        raise ValueError(
            f"Engagement '{slug}' not found at {md_file}"
        )

    from harness.scm.git import GitRepo

    repo = GitRepo(root)
    branch = repo.branch()

    mapping = _load_active_mapping(root)
    mapping.setdefault("branches", {})[branch] = slug
    _save_active_mapping(root, mapping)


# ── Engagement closing ────────────────────────────────────────────────────


def close_engagement(root: Path, slug: str) -> dict:
    """Close an engagement by setting its status to ``completed``.

    Validates that the engagement exists, reads its current metadata,
    updates ``status`` to ``completed`` with a ``completed_at`` timestamp,
    and writes the updated ``engagement.md``.

    Then removes the branch mapping from the active engagements mapping file.

    Returns the updated metadata dict.
    """
    md_file = get_engagement_md(root, slug)
    if not md_file.is_file():
        raise ValueError(
            f"Engagement '{slug}' not found at {md_file}"
        )

    # Parse existing frontmatter
    metadata = _parse_engagement_md(md_file)
    metadata["status"] = "completed"
    metadata["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Write back
    content = (
        "---\n"
        + yaml.dump(metadata, default_flow_style=False, sort_keys=False)
        + "---\n"
        + f"\n# {metadata.get('title', slug)}\n\n"
    )
    md_file.write_text(content)

    # Remove from active-engagements.yaml
    mapping = _load_active_mapping(root)
    branches = mapping.get("branches", {})
    # Remove any branch pointing to this slug
    to_remove = [b for b, s in branches.items() if s == slug]
    for b in to_remove:
        del branches[b]
    _save_active_mapping(root, mapping)

    return metadata


# ── Helpers ────────────────────────────────────────────────────────────────


def _load_active_mapping(root: Path) -> dict:
    """Load the active engagements mapping file.

    Returns ``{"branches": {}}`` if file doesn't exist.
    """
    path = get_active_engagements_path(root)
    if not path.is_file():
        return {"branches": {}}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    if "branches" not in data:
        data["branches"] = {}
    return data


def _save_active_mapping(root: Path, mapping: dict) -> None:
    """Write mapping to the active engagements file."""
    path = get_active_engagements_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(mapping, f, default_flow_style=False, sort_keys=False)


def update_active_engagement_mapping(
    root: Path, old_slug: str, new_slug: str
) -> None:
    """Update the active engagements mapping after a rename.

    Finds all branches mapped to *old_slug* and maps them to *new_slug*
    instead. Does nothing if the mapping file doesn't exist or if
    *old_slug* isn't referenced.
    """
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
    """Return the active engagement slug for the current branch, or None.

    Reads from the active engagements mapping file and matches against
    the current git branch. Returns None if no engagement is set or if
    the file doesn't exist.
    """
    try:
        from harness.scm.git import GitRepo
        repo = GitRepo(root)
        branch = repo.branch()
    except Exception:
        return None

    mapping = _load_active_mapping(root)
    return mapping.get("branches", {}).get(branch)


def _parse_engagement_md(path: Path) -> dict:
    """Parse YAML frontmatter from an engagement.md file.

    Returns the frontmatter dict, or empty dict if parsing fails.
    """
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
    """Return the engagement directory for a slug, regardless of whether it exists."""
    return get_engagement_dir(root, slug)


import re


def slugify(name: str) -> str:
    """Convert *name* to a kebab-case slug.

    Lowercases, replaces spaces with hyphens, removes all characters
    except lowercase letters, digits, and hyphens.
    """
    slug = name.lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug
