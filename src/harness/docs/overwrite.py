"""Overwrite manager for generate-docs.

Controls whether existing documentation files are overwritten,
backed up, or skipped.
"""

from __future__ import annotations

import difflib
import shutil
import time
from enum import Enum
from pathlib import Path
from typing import Optional

from harness.paths import get_docs_backups_dir


class OverwriteMode(Enum):
    NEVER = "never"
    ASK = "ask"
    ALL = "all"


# ── Backup ──────────────────────────────────────────────────────────────────


_BACKUP_DIR_NAME = "docs-backups"


def _backup_path(root: Path, file_path: Path) -> Path:
    """Compute the backup path for a given file.

    Creates a timestamped backup directory under
    the docs backup directory and mirrors the relative path.
    """
    timestamp = time.strftime("%Y%m%d%H%M%S")
    backup_root = get_docs_backups_dir(root) / timestamp
    backup_root.mkdir(parents=True, exist_ok=True)

    # Preserve relative path structure
    try:
        rel = file_path.relative_to(root)
    except ValueError:
        rel = Path(file_path.name)
    return backup_root / rel


def _backup_file(file_path: Path, root: Path) -> Path:
    """Copy *file_path* to the backup directory.

    Returns the backup path.
    """
    bp = _backup_path(root, file_path)
    bp.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(file_path), str(bp))
    return bp


# ── Diff preview ────────────────────────────────────────────────────────────


def _diff_preview(existing: str, proposed: str, filename: str) -> str:
    """Generate a unified diff between existing and proposed content."""
    existing_lines = existing.splitlines(keepends=True)
    proposed_lines = proposed.splitlines(keepends=True)
    diff = difflib.unified_diff(
        existing_lines,
        proposed_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    return "".join(diff)


# ── Prompt ──────────────────────────────────────────────────────────────────


def _prompt_user(diff: str, filename: str) -> bool:
    """Prompt the user (via input()) about whether to overwrite.

    Returns True if the user agrees, False otherwise.
    """
    print(f"\n--- Diff for {filename} ---")
    print(diff)
    print("--- End diff ---")
    response = (
        input(f"Overwrite {filename}? [Y/n] ").strip().lower()
    )
    # Default is "yes" when just Enter is pressed
    return response in ("", "y", "yes")


# ── Main API ────────────────────────────────────────────────────────────────


def handle_overwrite(
    file_path: Path,
    proposed_content: str,
    root: Path,
    mode: OverwriteMode = OverwriteMode.ASK,
    interactive: bool = True,
) -> Optional[Path]:
    """Handle potential overwrite of an existing file.

    Args:
        file_path: The target file path.
        proposed_content: The new content to write.
        root: Project root (used to compute backup paths).
        mode: Overwrite strategy.
        interactive: If True, prompt user in ASK mode. If False,
            default to "no" for ASK mode (useful in tests).

    Returns:
        The file path that was written, or None if the file was skipped
        (NEVER mode or user declined).
    """
    if mode == OverwriteMode.NEVER:
        if file_path.exists():
            return None
        # File doesn't exist — safe to write
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(proposed_content)
        return file_path

    if mode == OverwriteMode.ALL:
        if file_path.exists():
            _backup_file(file_path, root)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(proposed_content)
        return file_path

    # ASK mode
    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(proposed_content)
        return file_path

    # File exists — ask
    existing = file_path.read_text()
    if existing == proposed_content:
        # Content is identical — no need to overwrite
        return file_path

    diff = _diff_preview(existing, proposed_content, str(file_path))
    if interactive:
        should_write = _prompt_user(diff, str(file_path))
    else:
        should_write = False

    if should_write:
        _backup_file(file_path, root)
        file_path.write_text(proposed_content)
        return file_path
    else:
        return None


def resolve_overwrite(
    file_path: Path,
    root: Path,
    mode: OverwriteMode = OverwriteMode.ASK,
    existing_suggested: Optional[str] = None,
) -> bool:
    """Decide whether to overwrite *file_path*.

    Returns ``True`` if writing should proceed, ``False`` to skip.

    Behavior per mode:
    - ``NEVER``: always skip, just return False
    - ``ALL``: always overwrite; existing content is backed up first
    - ``ASK``: show a diff prompt to the user (default)
    """
    if not file_path.is_file():
        return True  # No existing file — always write

    if mode == OverwriteMode.NEVER:
        return False

    if mode == OverwriteMode.ALL:
        # Back up first, then overwrite
        _backup_file(file_path, root)
        return True

    # ASK mode: show diff
    return _prompt_with_diff(file_path, root, existing_suggested)


def _prompt_with_diff(
    file_path: Path, root: Path, suggested: Optional[str] = None
) -> bool:
    """Show a diff and ask the user what to do.

    Returns True to overwrite, False to skip.
    """
    try:
        existing = file_path.read_text()
    except Exception:
        existing = ""

    if suggested is not None and existing:
        diff = difflib.unified_diff(
            existing.splitlines(keepends=True),
            suggested.splitlines(keepends=True),
            fromfile=str(file_path),
            tofile=f"{file_path} (suggested)",
        )
        diff_text = "".join(diff)
        print(f"\nDiff for {file_path.relative_to(root)}:")
        print(diff_text if diff_text else "  (no changes)")
    elif not existing:
        print(f"\n{file_path.relative_to(root)}: (new file)")
    else:
        print(f"\n{file_path.relative_to(root)}: (existing file)")

    while True:
        answer = input("Overwrite? [y/N/d/s/b] ").strip().lower()
        if answer == "y":
            if existing:
                _backup_file(file_path, root)
            return True
        elif answer in ("n", ""):
            return False
        elif answer == "d":
            # Show full diff again
            continue
        elif answer == "s":
            print("  Skipping.")
            return False
        elif answer == "b":
            print("  Backup created.")
            _backup_file(file_path, root)
            return True
        else:
            print("  (y = overwrite, N = skip, d = show diff, s = skip, b = backup & write)")
