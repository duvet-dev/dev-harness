"""Fast scan — lightweight, auto-triggered analysis.

Runs quickly (<1s typical) and produces summary data about project
structure, file counts, language breakdown, and git diff stats.
Designed to run on every `harness summary` call without noticeable delay.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from harness.analysis.base import Finding, ScanResult
from harness.scm.git import GitRepo

# Common source file extensions by language
LANGUAGE_MAP: dict[str, list[str]] = {
    "python": [".py"],
    "markdown": [".md", ".rst"],
    "yaml": [".yaml", ".yml"],
    "json": [".json"],
    "toml": [".toml"],
    "shell": [".sh", ".bash"],
    "c": [".c", ".h"],
    "cpp": [".cpp", ".hpp", ".cc", ".cxx"],
    "javascript": [".js", ".jsx", ".mjs"],
    "typescript": [".ts", ".tsx"],
    "go": [".go"],
    "rust": [".rs"],
    "java": [".java"],
    "kotlin": [".kt", ".kts"],
    "ruby": [".rb"],
}

# Directories to skip in scans
SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "node_modules", ".tox",
    ".eggs", "*.egg-info", ".pytest_cache", ".mypy_cache",
    ".coverage", ".DS_Store",
}

# File extensions to skip
SKIP_EXTS = {".pyc", ".pyo", ".so", ".dll", ".dylib", ".class", ".o"}


def scan_structure(path: str | Path) -> ScanResult:
    """Scan directory structure: count files, lines, languages.

    Walks the directory tree (respecting SKIP_DIRS) and produces
    metrics on file counts, total lines, and language breakdown.
    """
    root = Path(path)
    if not root.exists():
        return ScanResult(
            scan_name="structure",
            findings=[Finding(
                severity="error",
                category="structure",
                message=f"Path does not exist: {path}",
                file=str(path),
            )],
            summary="Path not found",
        )

    findings: list[Finding] = []
    metrics: dict[str, Any] = {
        "file_count": 0,
        "total_lines": 0,
        "languages": {},
        "dir_count": 0,
    }

    lang_ext_rev: dict[str, str] = {}
    for lang, exts in LANGUAGE_MAP.items():
        for ext in exts:
            lang_ext_rev[ext] = lang

    dirs_scanned = set()

    for root_dir, dirs, files in os.walk(root):
        # Filter skipped directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        dirs_scanned.add(root_dir)

        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in SKIP_EXTS:
                continue

            filepath = os.path.join(root_dir, filename)
            rel_path = os.path.relpath(filepath, root)
            metrics["file_count"] += 1

            # Count lines
            try:
                with open(filepath, errors="replace") as f:
                    line_count = sum(1 for _ in f)
                metrics["total_lines"] += line_count
            except (OSError, UnicodeDecodeError):
                line_count = 0

            # Track by language
            lang = lang_ext_rev.get(ext, "other")
            lang_metrics = metrics["languages"].setdefault(lang, {"files": 0, "lines": 0})
            lang_metrics["files"] += 1
            lang_metrics["lines"] += line_count

    metrics["dir_count"] = len(dirs_scanned)

    # Generate summary
    lang_breakdown = ", ".join(
        f"{lang}: {m['files']} files ({m['lines']} lines)"
        for lang, m in sorted(metrics["languages"].items())
        if m["files"] > 0
    )
    summary = (
        f"{metrics['file_count']} files, {metrics['total_lines']} lines "
        f"across {metrics['dir_count']} dirs"
    )
    if lang_breakdown:
        summary += f" — {lang_breakdown}"

    return ScanResult(
        scan_name="structure",
        findings=findings,
        metrics=metrics,
        summary=summary,
    )


def scan_git_diff(path: str | Path, since: str | None = None) -> ScanResult:
    """Scan git diff stats for the repo at *path*.

    Args:
        path: Repository root.
        since: Git ref to diff against (default: HEAD~1).

    Returns:
        ScanResult with diff metrics and any findings.
    """
    root = Path(path)
    findings: list[Finding] = []
    metrics: dict[str, Any] = {}

    # Check it's a git repo
    try:
        repo = GitRepo(root)
    except Exception:
        return ScanResult(
            scan_name="git-diff",
            findings=[Finding(
                severity="info",
                category="structure",
                message="Not a git repository — diff unavailable",
                file=str(path),
            )],
            summary="Not a git repository",
        )

    # Get diff stats
    diff_base = since or "HEAD~1"
    try:
        diff_result = repo.diff(diff_base)
        metrics["diff_output"] = (
            f"{len(diff_result.files_changed)} files changed, "
            f"+{diff_result.insertions}/-{diff_result.deletions}"
        )
        metrics["insertions"] = diff_result.insertions
        metrics["deletions"] = diff_result.deletions
        metrics["changed_files"] = diff_result.files_changed
        metrics["changed_count"] = len(diff_result.files_changed)

        # Get current branch
        metrics["branch"] = repo.branch()

    except Exception:
        return ScanResult(
            scan_name="git-diff",
            findings=[Finding(
                severity="warning",
                category="structure",
                message="Git diff failed",
            )],
            summary="Git diff failed",
        )

    branch = metrics.get("branch", "unknown")
    ins = metrics.get("insertions", 0)
    del_count = metrics.get("deletions", 0)
    summary = (
        f"Branch '{branch}': {metrics.get('changed_count', 0)} files changed, "
        f"+{ins}/-{del_count} lines"
    )

    return ScanResult(
        scan_name="git-diff",
        findings=findings,
        metrics=metrics,
        summary=summary,
    )


def produce_summary(results: list[ScanResult]) -> str:
    """Combine multiple scan results into a concise one-liner.

    Preserves each scan's summary text and appends total finding counts.
    """
    parts = []
    for r in results:
        counts = []
        if r.error_count:
            counts.append(f"{r.error_count} err")
        if r.warning_count:
            counts.append(f"{r.warning_count} warn")
        if counts:
            parts.append(f"{r.summary} ({', '.join(counts)})")
        else:
            parts.append(r.summary)
    return " | ".join(parts)
