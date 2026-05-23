"""Engagement context bundle generation and caching.

The ContextLoader generates a structured "context bundle" — a compact
preamble injected into the agent's system prompt at session start so
the agent knows what files exist in the engagement space before it
begins working.

Three tiers of detail are available:

- **Tier 1** (minimal): File path tree only (~1–2 KB)
- **Tier 2** (normal): Inventory + file summaries with size, mtime,
  and key section headings (~5–10 KB)
- **Tier 3** (full): Full context with first-200-char content snippets
  per file (~10–25 KB)

Caching is handled via a ``manifest.json`` in
``.harness/engagements/<slug>/context/`` — the cache is regenerated
when file mtimes change or new files appear.

Wave 14 — R23: Engagement File Context Loading.
"""

from __future__ import annotations

import json
import os
import re
import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# ── Constants ──────────────────────────────────────────────────────────────

# Cache file names for context bundle tiers
CACHE_MANIFEST = "manifest.json"
CACHE_TIER_1 = "inventory.txt"
CACHE_TIER_2 = "context.txt"
CACHE_TIER_3 = "full_context.txt"


# Exceptions
# ---------------------------------------------------------------------------


class ContextError(Exception):
    """Base exception for context loading failures."""


class ContextSecurityError(ContextError):
    """Raised when a path escapes the engagement or repo root."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Binary file extensions to skip
BINARY_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".mp3", ".mp4", ".wav", ".ogg", ".mov", ".avi",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pyc", ".pyo", ".pyd",
    ".o", ".a", ".lib",
}

# File extensions that are "text-like" — safe to read and summarise
TEXT_EXTENSIONS: set[str] = {
    ".md", ".txt", ".rst", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".rb", ".go", ".rs",
    ".java", ".kt", ".scala", ".clj",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".hh", ".cxx",
    ".css", ".scss", ".less", ".html", ".htm", ".xhtml",
    ".json", ".xml", ".csv", ".tsv",
    ".sh", ".bash", ".zsh", ".fish",
    ".sql", ".graphql", ".proto",
    ".env", ".envrc",
    ".gitignore", ".dockerignore",
    ".conf", ".cnf",
    ".patch", ".diff",
    ".lock", ".sum",
    ".toml", ".ini",
    ".gradle", ".properties",
}

# Hard limit on bundle size injection
MAX_BUNDLE_BYTES = 50_000

# Default max paths in inventory
MAX_INVENTORY_PATHS = 500


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FileEntry:
    """Metadata for a single file in the engagement context."""

    path: str  # relative to engagement root
    size: int
    mtime: float
    summary: str = ""
    snippet: str = ""

    def is_file_like(self) -> bool:
        """True if the path has a file extension."""
        return "." in self.path.rsplit("/", 1)[-1]

    @property
    def size_fmt(self) -> str:
        """Human-readable file size."""
        return entry_size(self.size)


# ---------------------------------------------------------------------------
# ContextBundleBuilder
# ---------------------------------------------------------------------------


class ContextBundleBuilder:
    """Builds a context bundle string from engagement files.

    Usage::

        builder = ContextBundleBuilder(
            engagement_root=Path(".harness/engagements/my-slug"),
            repo_root=Path("/path/to/repo"),
        )
        builder.add_inventory()
        builder.add_summaries()
        bundle = builder.build()  # returns str
    """

    def __init__(
        self,
        engagement_root: Path,
        repo_root: Path,
        max_inventory_paths: int = MAX_INVENTORY_PATHS,
    ):
        self._engagement_root = engagement_root.resolve()
        self._repo_root = repo_root.resolve()
        self._max_inventory_paths = max_inventory_paths
        self._parts: list[str] = []
        self._files: list[FileEntry] = []

        # Validate engagement is within repo
        if not str(self._engagement_root).startswith(
            str(self._repo_root) + os.sep
        ) and self._engagement_root != self._repo_root:
            raise ContextSecurityError(
                f"Engagement root {self._engagement_root} is not within "
                f"repo root {self._repo_root}"
            )

    # ------------------------------------------------------------------
    # Tier 1: Inventory index
    # ------------------------------------------------------------------

    def add_inventory(self) -> ContextBundleBuilder:
        """Scan engagement directory and build a file tree inventory."""
        self._scan_files()
        tree = self._build_tree()
        self._parts.append(
            "--- Engagement File Inventory ---\n"
        )
        self._parts.append(tree)
        self._parts.append("\n")
        return self

    # ------------------------------------------------------------------
    # Tier 2: File summaries
    # ------------------------------------------------------------------

    def add_summaries(self) -> ContextBundleBuilder:
        """Add file summaries (size, mtime, key headings/docstrings)."""
        if not self._files:
            self._scan_files()

        lines = ["File Summaries:\n"]
        for entry in self._files:
            summary = self._extract_summary(entry)
            lines.append(f"  {entry.path:<40} {entry_size(entry.size):>6}  {summary}")

        self._parts.append("--- File Summaries ---\n")
        self._parts.append("\n".join(lines))
        self._parts.append("\n")
        return self

    # ------------------------------------------------------------------
    # Tier 3: Content snippets
    # ------------------------------------------------------------------

    def add_snippets(self) -> ContextBundleBuilder:
        """Add first ~200 characters of each file as content snippets."""
        if not self._files:
            self._scan_files()

        lines = ["Content Snippets:\n"]
        for entry in self._files:
            snippet = self._extract_snippet(entry)
            truncated = "..." if len(entry.snippet) >= 200 else ""
            lines.append(f"  {entry.path}: {snippet}{truncated}")

        self._parts.append("--- Content Snippets ---\n")
        self._parts.append("\n".join(lines))
        self._parts.append("\n")
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> str:
        """Assemble all added sections into a single string."""
        result = "\n".join(self._parts).strip()
        if len(result.encode("utf-8")) > MAX_BUNDLE_BYTES:
            # Truncate to the last complete block under limit
            truncated = ""
            for part in self._parts:
                candidate = truncated + "\n" + part if truncated else part
                if len(candidate.encode("utf-8")) > MAX_BUNDLE_BYTES:
                    break
                truncated = candidate
            return truncated.strip()
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan_files(self) -> None:
        """Recursively scan the engagement root and populate _files."""
        self._files = []
        if not self._engagement_root.is_dir():
            return

        for dirpath_str, dirnames, filenames in os.walk(
            str(self._engagement_root)
        ):
            dirpath = Path(dirpath_str)

            # Skip the context cache directory itself
            if dirpath.name == "context" and dirpath.parent == self._engagement_root:
                dirnames[:] = []  # Don't descend into cache
                continue

            for filename in sorted(filenames):
                filepath = dirpath / filename
                ext = filepath.suffix.lower()

                # Skip binary files
                if ext in BINARY_EXTENSIONS:
                    continue

                # Skip hidden files (except .md docs)
                if filename.startswith(".") and ext not in (".md", ".txt", ".yaml", ".yml"):
                    continue

                try:
                    stat = filepath.stat()
                    size = stat.st_size
                    mtime = stat.st_mtime
                except (OSError, PermissionError):
                    continue

                # Build relative path
                try:
                    rel = str(filepath.relative_to(self._engagement_root))
                except ValueError:
                    continue

                self._files.append(FileEntry(
                    path=rel,
                    size=size,
                    mtime=mtime,
                ))

                if len(self._files) >= self._max_inventory_paths:
                    return

    def _build_tree(self) -> str:
        """Build a bulleted tree representation of the file inventory."""
        if not self._files:
            return "  (no files)\n"

        lines = []
        for entry in self._files:
            parts = entry.path.split("/")
            depth = len(parts) - 1
            indent = "  " * depth
            icon = "📄" if entry.is_file_like() else "📁"
            lines.append(f"{indent}{icon} {parts[-1]}")

        return "\n".join(lines) + "\n"

    def _extract_summary(self, entry: FileEntry) -> str:
        """Extract a compact summary from a file.

        For markdown files: extract first heading.
        For code files: extract docstrings/header comments.
        Fallback: first 3 non-blank, non-import lines.
        """
        if entry.summary:
            return entry.summary

        filepath = self._engagement_root / entry.path
        if not filepath.is_file():
            entry.summary = "(missing)"
            return entry.summary

        try:
            content = self._safe_read(filepath)
        except (OSError, UnicodeDecodeError):
            entry.summary = "(unreadable)"
            return entry.summary

        summary = self._summarise_content(content, filepath.suffix)
        entry.summary = summary
        return summary

    def _extract_snippet(self, entry: FileEntry) -> str:
        """Extract the first ~200 characters of content."""
        if entry.snippet:
            return entry.snippet

        filepath = self._engagement_root / entry.path
        if not filepath.is_file():
            entry.snippet = "(missing)"
            return entry.snippet

        try:
            content = self._safe_read(filepath)
        except (OSError, UnicodeDecodeError):
            entry.snippet = "(unreadable)"
            return entry.snippet

        snippet = content[:200].replace("\n", " ").strip()
        entry.snippet = snippet
        return snippet

    @staticmethod
    def _safe_read(filepath: Path, max_bytes: int = 100_000) -> str:
        """Read a text file safely, bounded by max_bytes."""
        with open(str(filepath), "r", encoding="utf-8", errors="replace") as f:
            return f.read(max_bytes)

    @staticmethod
    def _summarise_content(content: str, suffix: str) -> str:
        """Generate a one-line summary from file content.

        Strategy:
        1. For markdown (.md, .rst): return the first heading (line starting with #) or doc title
        2. For code files: extract docstrings/header comments
        3. Fallback: first 3 non-blank, non-import lines
        """
        if suffix in (".md", ".rst", ".txt"):
            return _extract_markdown_summary(content)

        if suffix == ".py":
            return _extract_python_summary(content)

        # Generic code file: look for block comments, docstrings, or header comments
        summary = _extract_generic_code_summary(content, suffix)
        if summary:
            return summary

        # Fallback: first 3 non-blank, non-import lines
        return _fallback_summary(content)

    @staticmethod
    def entry_size(size: int) -> str:
        """Format bytes as human-readable string."""
        return entry_size(size)


# ---------------------------------------------------------------------------
# ContextLoader
# ---------------------------------------------------------------------------


class ContextLoader:
    """Generates and caches engagement context bundles.

    The loader generates bundles at the requested detail tier and caches
    them in ``.harness/engagements/<slug>/context/``. The cache is
    validated against file mtimes at session start, so changes to
    engagement files trigger automatic regeneration.
    """

    def __init__(
        self,
        engagement_root: Path,
        repo_root: Path,
        cache_timeout_seconds: int = 300,
    ):
        self._engagement_root = engagement_root.resolve()
        self._repo_root = repo_root.resolve()
        self._cache_dir = self._engagement_root / "context"
        self._cache_timeout = cache_timeout_seconds

    def load_bundle(self, tier: int = 2) -> str:
        """Load or generate a context bundle at the requested tier.

        Args:
            tier: 1 = inventory only, 2 = inventory + summaries,
                  3 = full context with snippets

        Returns:
            Structured context string for prompt injection.

        Raises:
            ContextError: If the engagement root cannot be accessed.
        """
        cached = self._check_cache(tier)
        if cached is not None:
            return cached

        bundle = self._generate_bundle(tier)
        self._write_cache(tier, bundle)
        self._write_manifest()
        return bundle

    def invalidate_cache(self) -> None:
        """Force cache regeneration on next load."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self._cache_dir / CACHE_MANIFEST
        if manifest_path.exists():
            manifest_path.unlink()

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def _cache_path(self, tier: int) -> Path:
        """Return the cache file path for a given tier."""
        names = {1: CACHE_TIER_1, 2: CACHE_TIER_2, 3: CACHE_TIER_3}
        return self._cache_dir / names.get(tier, CACHE_TIER_2)

    def _check_cache(self, tier: int) -> str | None:
        """Return cached bundle if valid, None otherwise."""
        if not self._cache_dir.is_dir():
            return None

        manifest = self._load_manifest()
        if manifest is None:
            return None

        # Check cache freshness against manifest
        if not self._manifest_is_fresh(manifest):
            return None

        # Read cached bundle
        cache_file = self._cache_path(tier)
        if not cache_file.is_file():
            return None

        # Check file mtime — manifest tracks the newer of file changes
        cache_mtime = cache_file.stat().st_mtime
        if time.time() - cache_mtime > self._cache_timeout:
            return None

        return cache_file.read_text(encoding="utf-8")

    def _generate_bundle(self, tier: int) -> str:
        """Generate a fresh context bundle."""
        builder = ContextBundleBuilder(
            self._engagement_root, self._repo_root
        )
        if tier >= 1:
            builder.add_inventory()
        if tier >= 2:
            builder.add_summaries()
        if tier >= 3:
            builder.add_snippets()
        return builder.build()

    def _write_cache(self, tier: int, bundle: str) -> None:
        """Write the bundle to the cache directory."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self._cache_path(tier)
        cache_file.write_text(bundle, encoding="utf-8")

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def _load_manifest(self) -> dict[str, Any] | None:
        """Load the manifest JSON, or None if missing/invalid."""
        manifest_path = self._cache_dir / CACHE_MANIFEST
        if not manifest_path.is_file():
            return None
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _manifest_is_fresh(self, manifest: dict[str, Any]) -> bool:
        """Check whether the manifest matches the current filesystem."""
        tracked = manifest.get("files", {})
        if not isinstance(tracked, dict):
            return False

        # Walk engagement files and verify mtime hashes match
        seen: set[str] = set()
        if not self._engagement_root.is_dir():
            return len(tracked) == 0

        for dirpath_str, dirnames, filenames in os.walk(
            str(self._engagement_root)
        ):
            dirpath = Path(dirpath_str)

            if dirpath.name == "context" and dirpath.parent == self._engagement_root:
                dirnames[:] = []
                continue

            for filename in filenames:
                filepath = dirpath / filename
                rel = str(filepath.relative_to(self._engagement_root))
                seen.add(rel)

                if rel not in tracked:
                    return False  # New file appeared

                # Compare mtime hash
                try:
                    stat = filepath.stat()
                    current_hash = _mtime_hash(stat.st_mtime, stat.st_size)
                except OSError:
                    return False

                if tracked[rel] != current_hash:
                    return False  # File changed

        # Check for deleted files
        if set(tracked.keys()) - seen:
            return False  # A file was deleted

        return True

    def _write_manifest(self) -> None:
        """Write the manifest based on current files."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        tracked: dict[str, str] = {}

        if self._engagement_root.is_dir():
            for dirpath_str, dirnames, filenames in os.walk(
                str(self._engagement_root)
            ):
                dirpath = Path(dirpath_str)

                if dirpath.name == "context" and dirpath.parent == self._engagement_root:
                    dirnames[:] = []
                    continue

                for filename in filenames:
                    filepath = dirpath / filename
                    try:
                        stat = filepath.stat()
                        tracked[str(filepath.relative_to(self._engagement_root))] = (
                            _mtime_hash(stat.st_mtime, stat.st_size)
                        )
                    except (OSError, ValueError):
                        continue

        manifest = {"files": tracked, "updated_at": time.time()}
        manifest_path = self._cache_dir / CACHE_MANIFEST
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------


def _mtime_hash(mtime: float, size: int) -> str:
    """Create a short hash from mtime + size for change detection."""
    raw = f"{mtime}:{size}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()[:12]


def entry_size(size: int) -> str:
    """Format bytes as human-readable string."""
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f}K"
    else:
        return f"{size / (1024 * 1024):.1f}M"


def _extract_markdown_summary(content: str) -> str:
    """Extract the first meaningful heading from markdown content.

    Returns the first heading line if it exists, otherwise the first
    line under max length.
    """
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        if stripped and len(stripped) < 120:
            return stripped[:100]
    return "(no content)"


def _extract_python_summary(content: str) -> str:
    """Extract the module-level docstring or first class/function summary."""
    # Check for docstring at start of file
    match = re.match(
        r'(?:\s*(?:"""|\'\'\')\s*\n?)(.*?)(?:\n?\s*(?:"""|\'\'\'))',
        content,
        re.DOTALL,
    )
    if match:
        docstring = match.group(1).strip()
        # Take first line or up to 100 chars
        first_line = docstring.split("\n")[0].strip()
        return first_line[:100] if first_line else "(docstring)"

    # Look for class/function definition with docstring
    match = re.search(
        r'(?:class|def)\s+\w+.*?:\s*\n\s*(?:"""|\'\'\')\s*(.*?)\s*(?:"""|\'\'\')',
        content,
        re.DOTALL,
    )
    if match:
        return match.group(1).split("\n")[0].strip()[:100]

    return _fallback_summary(content)


def _extract_generic_code_summary(content: str, suffix: str) -> str:
    """Extract header comments or docstrings from generic code files.

    Supports:
    - ``//`` comments at top of file (Go, Rust, C, C++, JS, TS)
    - ``/* ... */`` block comments at top of file (C, C++, Java, JS, TS)
    - ``///`` doc comments (Rust)
    - ``--`` comments (Lua, SQL, Haskell)
    - ``#`` header comments for non-Python (Ruby, shell, config)
    """
    lines = content.split("\n")

    # Check for opening ````` block comment (C-style)
    if suffix in (".c", ".h", ".cpp", ".hpp", ".cc", ".hh", ".java",
                  ".js", ".ts", ".tsx", ".jsx", ".kt", ".scala"):
        block_match = re.match(r"\s*/\*+\s*(.*?)\s*\*/", content, re.DOTALL)
        if block_match:
            inner = block_match.group(1).strip()
            # Filter out license boilerplate
            if "copyright" in inner.lower() or "license" in inner.lower():
                return inner.split("\n")[0].strip()[:100]
            return inner.split("\n")[0].strip()[:100]

    # Check for /// doc comments (Rust)
    if suffix == ".rs":
        doc_lines = [
            l.lstrip().lstrip("/") for l in lines
            if l.strip().startswith("///")
        ]
        if doc_lines:
            return doc_lines[0].strip()[:100]

    # Check for top // comments (Go, Rust, generic)
    comment_lines = []
    for line in lines[:15]:  # first 15 lines
        stripped = line.strip()
        if stripped.startswith("//"):
            comment_lines.append(stripped.lstrip("/").strip())
        elif not stripped:
            continue
        else:
            break

    if comment_lines:
        return comment_lines[0][:100]

    return ""


def _fallback_summary(content: str) -> str:
    """Fallback: first 3 non-blank, non-import lines."""
    lines = []
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("import ", "from ", "package ", "use ",
                                "require ", "#include", "using ")):
            continue
        lines.append(stripped[:80])
        if len(lines) >= 3:
            break
    return "; ".join(lines) if lines else "(no content)"



