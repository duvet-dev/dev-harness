"""Pattern injection system — loads, sorts, and injects patterns into agent context.

Supports project-specific patterns stored in ``.harness/patterns/`` and
built-in language patterns bundled with the harness. Patterns are loaded,
sorted by priority, and injected into agent system prompts between fleet
guidelines and the task prompt.

Wave 17 — Phase 3 (Pattern Injection System).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from harness.paths import get_cache_dir, get_config_path, get_engagement_dir, get_harness_dir, get_patterns_dir


# ---------------------------------------------------------------------------
# Pattern Model
# ---------------------------------------------------------------------------


@dataclass
class Pattern:
    """A single injectable pattern file.

    Attributes:
        path: Relative path within the pattern directory (``.harness/patterns/``)
            or absolute path.
        url: External URL reference (optional). Not fetched at inject time.
        fleet: Target fleet (e.g. ``"coding"``, ``"architecture"``). ``None``
            means all fleets.
        language: Target programming language (e.g. ``"python"``, ``"go"``).
            ``None`` means language-agnostic.
        priority: Injection order (``"high"`` > ``"medium"`` > ``"low"``).
        content: The pattern file content (injected into agent prompts).
            Loaded lazily from disk.
        builtin: Whether this is a built-in harness pattern.
        source_path: The resolved filesystem path (set during loading).
    """

    path: str = ""
    url: str = ""
    fleet: str = ""
    language: str = ""
    priority: str = "medium"
    content: str = ""
    builtin: bool = False
    source_path: str = ""


# ---------------------------------------------------------------------------
# Priority sorting
# ---------------------------------------------------------------------------


_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def sort_patterns(patterns: list[Pattern]) -> list[Pattern]:
    """Sort patterns by priority (high → medium → low).

    Within the same priority, built-in patterns come last so that
    project-specific patterns take precedence.
    """
    return sorted(
        patterns,
        key=lambda p: (_PRIORITY_ORDER.get(p.priority, 1), p.builtin),
    )


# ---------------------------------------------------------------------------
# Pattern Loader
# ---------------------------------------------------------------------------


class PatternLoader:
    """Loads and caches pattern files from the project and built-in sources.

    Usage::

        loader = PatternLoader(root)
        patterns = loader.load_all()
        # patterns is sorted by priority: high → medium → low
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._custom_patterns_dir = get_patterns_dir(root)
        self._config_path = get_config_path(root)
        self._cache_path = get_cache_dir(root) / "pattern_manifest.json"
        self._cache: Optional[dict] = None

    def load_all(self) -> list[Pattern]:
        """Load all patterns: custom project patterns + built-in language patterns.

        Returns patterns sorted by priority (high → medium → low).
        """
        patterns: list[Pattern] = []

        # 1. Built-in language patterns (harness/patterns/)
        patterns.extend(self._load_builtin_patterns())

        # 2. Project-level patterns from .harness/patterns/
        patterns.extend(self._load_project_patterns())

        # 3. Engagement-level patterns from .harness/engagements/<slug>/patterns/
        # (handled by callers that know the engagement slug)

        return sort_patterns(patterns)

    def load_for_fleet(
        self,
        fleet_name: str,
        language: Optional[str] = None,
    ) -> list[Pattern]:
        """Load patterns targeting a specific fleet.

        Args:
            fleet_name: Target fleet (e.g. ``"coding"``).
            language: Optional language filter (e.g. ``"python"``).

        Returns:
            Sorted list of matching patterns.
        """
        all_patterns = self.load_all()
        matching = []
        for p in all_patterns:
            if p.fleet and p.fleet != fleet_name:
                continue
            if language and p.language and p.language != language:
                continue
            matching.append(p)
        return matching

    def load_for_engagement(
        self,
        slug: str,
        fleet_name: Optional[str] = None,
        language: Optional[str] = None,
    ) -> list[Pattern]:
        """Load patterns including engagement-level overrides.

        Engagement-level files in ``.harness/engagements/<slug>/patterns/``
        take highest priority.
        """
        patterns = self.load_for_fleet(fleet_name or "", language=language)

        # Engagement-level patterns
        eng_patterns_dir = get_engagement_dir(self._root, slug) / "patterns"
        if eng_patterns_dir.is_dir():
            for pf in sorted(eng_patterns_dir.iterdir()):
                if pf.suffix in (".md", ".txt", ".yaml") and pf.is_file():
                    content = pf.read_text(encoding="utf-8")
                    meta = _parse_frontmatter(content)
                    p = self._load_pattern_from_file(
                        pf,
                        fleet=fleet_name or meta.get("fleet", ""),
                        language=language or meta.get("language", ""),
                    )
                    if p:
                        p.priority = "high"  # engagement patterns override everything
                        patterns.append(p)

        return sort_patterns(patterns)

    def format_patterns_section(self, patterns: list[Pattern]) -> str:
        """Format a list of patterns as a markdown block for injection."""
        if not patterns:
            return ""

        parts = []
        for p in patterns:
            label = p.path.split("/")[-1] if p.path else p.url
            if p.language:
                label = f"{label} [{p.language}]"
            parts.append(f"[Patterns: {label}]")
            parts.append(p.content)

        return "\n\n".join(parts)

    # ── Built-in patterns ─────────────────────────────────────────────

    def _load_builtin_patterns(self) -> list[Pattern]:
        """Load built-in language patterns from the harness package.

        Looks for pattern files in ``harness/patterns/`` relative to the
        harness package directory.
        """
        patterns: list[Pattern] = []
        harness_pkg = Path(__file__).resolve().parent
        builtin_dir = harness_pkg / "patterns"
        if not builtin_dir.is_dir():
            return patterns

        for pf in sorted(builtin_dir.iterdir()):
            if pf.suffix in (".md",) and pf.is_file():
                content = pf.read_text(encoding="utf-8")
                meta = _parse_frontmatter(content)
                lang = pf.stem  # filename = language name
                p = Pattern(
                    path=f"builtin:{lang}",
                    fleet=meta.get("fleet", "coding"),
                    language=lang,
                    priority=meta.get("priority", "low"),
                    content=_strip_frontmatter(content),
                    builtin=True,
                )
                patterns.append(p)

        return patterns

    # ── Project patterns ──────────────────────────────────────────────

    def _load_project_patterns(self) -> list[Pattern]:
        """Load patterns from the project's ``.harness/patterns/`` directory.

        Also loads patterns referenced in ``.harness/config.yaml`` under
        the ``patterns`` key.
        """
        patterns: list[Pattern] = []

        # 1. From config.yaml patterns section
        config_patterns = self._load_config_patterns()
        patterns.extend(config_patterns)

        # 2. From .harness/patterns/ directory
        if self._custom_patterns_dir.is_dir():
            for pf in sorted(self._custom_patterns_dir.iterdir()):
                if pf.suffix in (".md", ".txt", ".yaml") and pf.is_file():
                    content = pf.read_text(encoding="utf-8")
                    meta = _parse_frontmatter(content)
                    p = Pattern(
                        path=str(pf.relative_to(self._root)),
                        fleet=meta.get("fleet", ""),
                        language=meta.get("language", ""),
                        priority=meta.get("priority", "medium"),
                        content=_strip_frontmatter(content),
                        builtin=False,
                    )
                    patterns.append(p)

        return patterns

    def _load_config_patterns(self) -> list[Pattern]:
        """Load patterns referenced in ``.harness/config.yaml``."""
        patterns: list[Pattern] = []

        if not self._config_path.is_file():
            return patterns

        with open(self._config_path) as f:
            config = yaml.safe_load(f) or {}

        patterns_config = config.get("patterns", {}) or {}
        for fleet_name, fleet_patterns in patterns_config.items():
            if not isinstance(fleet_patterns, list):
                continue
            for entry in fleet_patterns:
                path_str = entry.get("path", "")
                url_str = entry.get("url", "")
                if path_str:
                    pf = self._root / path_str
                    if pf.is_file():
                        content = pf.read_text(encoding="utf-8")
                        meta = _parse_frontmatter(content)
                        p = Pattern(
                            path=path_str,
                            fleet=fleet_name,
                            language=meta.get("language", ""),
                            priority=meta.get("priority", "medium"),
                            content=_strip_frontmatter(content),
                            builtin=False,
                        )
                        patterns.append(p)
                if url_str:
                    p = Pattern(
                        path="",
                        url=url_str,
                        fleet=fleet_name,
                        priority="medium",
                        content=f"[External resource: {url_str}]",
                        builtin=False,
                    )
                    patterns.append(p)

        return patterns

    @staticmethod
    def _load_pattern_from_file(
        pf: Path,
        fleet: str = "",
        language: str = "",
    ) -> Optional[Pattern]:
        """Load a single pattern from a file path."""
        if not pf.is_file():
            return None
        content = pf.read_text(encoding="utf-8")
        meta = _parse_frontmatter(content)
        return Pattern(
            path=str(pf),
            fleet=fleet or meta.get("fleet", ""),
            language=language or meta.get("language", ""),
            priority=meta.get("priority", "medium"),
            content=_strip_frontmatter(content),
            builtin=False,
        )

    # ── Cache ─────────────────────────────────────────────────────────

    def _load_cache(self) -> dict:
        if self._cache is not None:
            return self._cache
        if self._cache_path.is_file():
            with open(self._cache_path) as f:
                self._cache = json.load(f)
        else:
            self._cache = {}
        return self._cache

    def _save_cache(self, manifest: dict) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._cache_path, "w") as f:
            json.dump(manifest, f, indent=2)
        self._cache = manifest


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from markdown content.

    Expects content starting with ``---``:
    ```markdown
    ---
    fleet: coding
    language: python
    priority: high
    ---
    Pattern content...
    ```
    Returns empty dict if no frontmatter is found.
    """
    content = content.strip()
    if not content.startswith("---"):
        return {}

    # Find the closing ---
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return {}

    front_section = content[3:end_idx].strip()
    try:
        return yaml.safe_load(front_section) or {}
    except Exception:
        return {}


def _strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from markdown content.

    Returns the content after the closing ``---``, or the original
    content if no frontmatter is detected.
    """
    content = content.strip()
    if not content.startswith("---"):
        return content

    end_idx = content.find("---", 3)
    if end_idx == -1:
        return content

    return content[end_idx + 3:].strip()


# ---------------------------------------------------------------------------
# Pattern file creation helpers
# ---------------------------------------------------------------------------


def scaffold_pattern_file(
    target_path: Path,
    fleet: str,
    language: str = "",
    priority: str = "medium",
    content: str = "",
) -> Path:
    """Create a scaffolded pattern file with frontmatter.

    Creates any necessary parent directories.

    Args:
        target_path: Where to write the pattern file.
        fleet: Target fleet (e.g. ``"coding"``).
        language: Target language (e.g. ``"python"``).
        priority: ``"high"``, ``"medium"``, or ``"low"``.
        content: Pattern body content (markdown).

    Returns:
        The path to the created file.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)

    frontmatter = []
    frontmatter.append("---")
    frontmatter.append(f"type: pattern")
    frontmatter.append(f"fleet: {fleet}")
    if language:
        frontmatter.append(f"language: {language}")
    frontmatter.append(f"priority: {priority}")
    frontmatter.append("---")

    full_content = "\n".join(frontmatter) + "\n\n" + content
    target_path.write_text(full_content)

    return target_path
