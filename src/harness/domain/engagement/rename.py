"""Engagement rename — rename an existing engagement with branch strategy.

Usage::

    from harness.domain.engagement.rename import rename_engagement

    result = rename_engagement(
        old_slug="typo-eng",
        new_slug="correct-eng",
        root=project_root,
        branch_strategy=BranchStrategy.KEEP,
    )

The rename preserves all engagement state (plan, waves, checkpoints,
feedback packets). The old directory is archived for a 24h rollback
window.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from harness.domain.engagement.lifecycle import (
    _parse_engagement_md,
    update_active_engagement_mapping,
)
from harness.paths import (
    ENGAGEMENT_MD,
    ENGAGEMENT_YAML_FILE,
    PLAN_YAML,
    get_active_engagements_path,
    get_engagement_dir,
    get_engagements_dir,
)

# ── Branch strategy ────────────────────────────────────────────────────────


from harness.command.values import BranchStrategy


# ── Result ─────────────────────────────────────────────────────────────────


@dataclass
class RenameResult:
    """Result of a rename operation.

    Attributes:
        success: True if the rename completed.
        old_slug: The original engagement slug.
        new_slug: The new engagement slug.
        old_dir: Path to the original engagement directory.
        new_dir: Path to the new engagement directory.
        archive_dir: Path to the archive backup (if created).
        errors: List of error messages (empty on success).
        warnings: List of warning messages.
        changes_made: Description of what was changed.
    """

    success: bool = False
    old_slug: str = ""
    new_slug: str = ""
    old_dir: Optional[Path] = None
    new_dir: Optional[Path] = None
    archive_dir: Optional[Path] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    changes_made: list[str] = field(default_factory=list)


# ── Slug validation ────────────────────────────────────────────────────────


def validate_slug(slug: str) -> Optional[str]:
    """Validate an engagement slug format.

    Returns an error message string, or None if valid.
    """
    if not slug:
        return "Slug must not be empty."
    if not slug[0].isalnum():
        return "Slug must start with an alphanumeric character."
    if not slug[-1].isalnum():
        return "Slug must end with an alphanumeric character."
    if not all(c.isalnum() or c == "-" for c in slug):
        return "Slug may only contain letters, digits, and hyphens."
    return None


# ── Archive ────────────────────────────────────────────────────────────────


_ARCHIVE_DIR_NAME = "_archive"


def _archive_engagement(eng_dir: Path, engagements_dir: Path) -> Path:
    """Move the old engagement directory to ``_archive/<slug>-<timestamp>/``.

    Returns the archive directory path.
    """
    archive_root = engagements_dir / _ARCHIVE_DIR_NAME
    archive_root.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d%H%M%S")
    archive_path = archive_root / f"{eng_dir.name}-{timestamp}"

    shutil.copytree(str(eng_dir), str(archive_path))
    return archive_path


# ── Core rename logic ──────────────────────────────────────────────────────


def _update_engagement_yaml(eng_dir: Path, new_slug: str, old_slug: str) -> list[str]:
    """Update slug references inside an engagement directory.

    Modifies:
    - ``engagement.yaml`` — updates the slug field
    - ``engagement.md`` (frontmatter) — updates the slug field
    - ``plan.yaml`` — updates any internal slug references

    Returns a list of change descriptions.
    """
    changes: list[str] = []

    # 1. Update engagement.yaml
    eng_yaml = eng_dir / ENGAGEMENT_YAML_FILE
    if eng_yaml.is_file():
        with open(eng_yaml) as f:
            data = yaml.safe_load(f) or {}
        if data.get("slug") != new_slug:
            old = data.get("slug")
            data["slug"] = new_slug
            with open(eng_yaml, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            changes.append(f"Updated slug in engagement.yaml ({old} → {new_slug})")

    # 2. Update engagement.md frontmatter
    md_file = eng_dir / ENGAGEMENT_MD
    if md_file.is_file():
        metadata = _parse_engagement_md(md_file)
        if metadata.get("slug") != new_slug:
            old = metadata.get("slug")
            metadata["slug"] = new_slug
            content = (
                "---\n"
                + yaml.dump(metadata, default_flow_style=False, sort_keys=False)
                + "---\n"
                + f"\n# {metadata.get('title', new_slug)}\n\n"
            )
            md_file.write_text(content)
            changes.append(f"Updated slug in engagement.md ({old} → {new_slug})")

    # 3. Update plan.yaml references
    plan_yaml = eng_dir / PLAN_YAML
    if plan_yaml.is_file():
        with open(plan_yaml) as f:
            plan_data = yaml.safe_load(f) or {}
        # Look for slug fields or engagement references within plan data
        modified = False
        if isinstance(plan_data, dict):
            for key, value in list(plan_data.items()):
                if isinstance(value, str) and value == old_slug:
                    plan_data[key] = new_slug
                    modified = True
                    changes.append(
                        f"Updated reference in plan.yaml ({key})"
                    )
        if modified:
            with open(plan_yaml, "w") as f:
                yaml.dump(
                    plan_data, f, default_flow_style=False, sort_keys=False
                )

    return changes


def rename_engagement(
    old_slug: str,
    new_slug: str,
    root: Path,
    branch_strategy: BranchStrategy = BranchStrategy.KEEP,
    dry_run: bool = False,
) -> RenameResult:
    """Rename an engagement from *old_slug* to *new_slug*.

    Args:
        old_slug: The current engagement slug.
        new_slug: The desired new engagement slug.
        root: Project root directory.
        branch_strategy: How to handle the git branch.
        dry_run: If True, validate and report without making changes.

    Returns:
        A ``RenameResult`` describing what happened.
    """
    result = RenameResult(
        old_slug=old_slug,
        new_slug=new_slug,
    )

    engagements_dir = get_engagements_dir(root)
    old_dir = get_engagement_dir(root, old_slug)
    new_dir = get_engagement_dir(root, new_slug)

    result.old_dir = old_dir
    result.new_dir = new_dir

    # ── Validation ────────────────────────────────────────────────────
    slug_error = validate_slug(new_slug)
    if slug_error:
        result.errors.append(f"Invalid new slug '{new_slug}': {slug_error}")
        return result

    if not old_dir.is_dir():
        result.errors.append(
            f"Engagement '{old_slug}' not found at {old_dir}"
        )
        return result

    if new_dir.exists():
        result.errors.append(
            f"Engagement '{new_slug}' already exists at {new_dir}"
        )
        return result

    # ── Check for in-progress sessions (basic check) ──────────────────
    # Look for any session metadata files referencing old_slug
    _check_active_sessions(root, old_slug, result)

    # ── Dry-run: report without changes ───────────────────────────────
    if dry_run:
        result.changes_made.append(
            f"Rename engagement '{old_slug}' → '{new_slug}'"
        )
        result.changes_made.append(
            f"Move: {old_dir} → {new_dir}"
        )
        result.changes_made.append(
            f"Branch strategy: {branch_strategy.value}"
        )
        if not result.errors:
            result.success = True
        return result

    # ── Archive old directory ─────────────────────────────────────────
    archive_path = _archive_engagement(old_dir, engagements_dir)
    result.archive_dir = archive_path
    result.changes_made.append(
        f"Archived old directory to {archive_path}"
    )

    # ── Rename directory ──────────────────────────────────────────────
    old_dir.rename(new_dir)
    result.changes_made.append(
        f"Moved directory: {old_dir} → {new_dir}"
    )

    # ── Update slug references inside the directory ───────────────────
    yaml_changes = _update_engagement_yaml(new_dir, new_slug, old_slug)
    result.changes_made.extend(yaml_changes)

    # ── Update active engagements mapping ─────────────────────────────
    update_active_engagement_mapping(root, old_slug, new_slug)
    result.changes_made.append(
        f"Updated active-engagements.yaml mapping ({old_slug} → {new_slug})"
    )

    # ── Handle branch strategy ────────────────────────────────────────
    if branch_strategy in (BranchStrategy.RENAME, BranchStrategy.NEW):
        try:
            from harness.scm.git import GitRepo

            repo = GitRepo(root)

            if branch_strategy == BranchStrategy.RENAME:
                current_branch = repo.branch()
                repo.rename_branch(current_branch, new_slug)
                result.changes_made.append(
                    f"Renamed git branch '{current_branch}' → '{new_slug}'"
                )
            elif branch_strategy == BranchStrategy.NEW:
                # Create new branch at current HEAD and switch to it
                repo.checkout(new_slug, create=True)
                result.changes_made.append(
                    f"Created and switched to new branch '{new_slug}'"
                )
        except Exception as exc:
            result.warnings.append(
                f"Branch operation failed: {exc}. "
                "The engagement rename completed but the branch was "
                "not modified. Use `git branch -m` or `git checkout -b` "
                "manually."
            )

    result.success = len(result.errors) == 0
    return result


# ── Session check ──────────────────────────────────────────────────────────


def _check_active_sessions(
    root: Path, old_slug: str, result: RenameResult
) -> None:
    """Check for any active session files referencing the old slug."""
    # Check active-engagements.yaml
    mapping_path = get_active_engagements_path(root)
    if mapping_path.is_file():
        with open(mapping_path) as f:
            mapping = yaml.safe_load(f) or {}
        branches = mapping.get("branches", {})
        for branch, slug in branches.items():
            if slug == old_slug:
                result.warnings.append(
                    f"Branch '{branch}' is mapped to engagement "
                    f"'{old_slug}'. It will be remapped to "
                    f"'{result.new_slug}' automatically."
                )

    # Check for any session .yaml files in the engagement directory
    old_dir = get_engagement_dir(root, old_slug)
    if old_dir.is_dir():
        for f in old_dir.iterdir():
            if f.suffix == ".yaml" and f.stem != "engagement":
                result.warnings.append(
                    f"Session file '{f.name}' references old slug. "
                    "Please verify it still works after rename."
                )
