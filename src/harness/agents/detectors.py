"""Language detection and test patterns for language-agnostic agent tools.

Provides a shared ``LanguageDetector`` that identifies the primary
project language from project root markers, and ``LanguagePatterns``
with language-specific test file globs, test function patterns, and
AC reference patterns.

Supported languages:
    Python, JavaScript/TypeScript, Java, Go, Rust, Scala, SQL (Liquibase)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Constants: build/project file markers ──────────────────────────────

BUILD_PYPROJECT_TOML = "pyproject.toml"
BUILD_PYTEST_INI = "pytest.ini"
BUILD_SETUP_PY = "setup.py"
BUILD_SETUP_CFG = "setup.cfg"
BUILD_TOX_INI = "tox.ini"


# ---------------------------------------------------------------------------
# Per-language patterns
# ---------------------------------------------------------------------------


@dataclass
class LanguagePatterns:
    """Test detection patterns for one programming language.

    Attributes:
        name: Language name (e.g. ``"python"``, ``"javascript"``).
        markers: Project root filenames that signal this language.
        test_dirs: Common test directory names.
        test_file_globs: Glob patterns for test files.
        test_fn_regex: Regex to detect test function/method definitions.
        test_fn_regex_flags: Flags for the regex (e.g. ``re.MULTILINE``).
        ac_decorator_regex: Regex for AC-reference annotations/decorators.
        ac_comment_regex: Regex for AC-reference in comments.
        ac_name_regex: Regex for AC-reference in test naming conventions.
        comment_line: Line-comment prefix (``#``, ``//``, ``--``).
        comment_block_start: Block-comment start (``/*``, ``\"\"\"``).
        comment_block_end: Block-comment end (``*/``, ``\"\"\"``).
    """
    name: str
    markers: list[str] = field(default_factory=list)
    test_dirs: list[str] = field(default_factory=list)
    test_file_globs: list[str] = field(default_factory=list)
    test_fn_regex: str = ""
    test_fn_regex_flags: int = re.MULTILINE
    ac_decorator_regex: str = (
        r'@?(?:ac|requirement|criterion|req)\s*[({]\s*["\']?'
        r'([A-Z][A-Z0-9_.-]+)'
        r'["\']?\s*[)}\]]?'
    )
    ac_comment_regex: str = (
        r'(?:#|//|--|;)\s*'
        r'((?:AC|REQ|CRITERION)[-_\s]\d[A-Z0-9_.-]+)'
    )
    ac_name_regex: str = (
        r'(?:AC|REQ)[_\s-]*'
        r'(\d+(?:[._-]\d+)*)'
    )
    comment_line: str = "#"
    comment_block_start: str = ""
    comment_block_end: str = ""


# ---------------------------------------------------------------------------
# Language definitions
# ---------------------------------------------------------------------------

_LANGUAGES: dict[str, LanguagePatterns] = {
    "python": LanguagePatterns(
        name="python",
        markers=[BUILD_PYTEST_INI, BUILD_SETUP_PY, BUILD_SETUP_CFG, BUILD_TOX_INI, BUILD_PYPROJECT_TOML],
        test_dirs=["tests", "test"],
        test_file_globs=["test_*.py", "*_test.py", "test_*.pyx"],
        test_fn_regex=r'def\s+(test_\w+)\s*\(',
        comment_line="#",
        comment_block_start='"""',
        comment_block_end='"""',
    ),
    "javascript": LanguagePatterns(
        name="javascript",
        markers=["package.json"],
        test_dirs=["__tests__", "tests", "spec", "test"],
        test_file_globs=["*.test.js", "*.spec.js", "*.test.mjs"],
        test_fn_regex=(
            r'(?:'
            r'(?:test|it|describe)\s*[(`\s][\'"`]([^\'"]+)[\'"`]'  # test('name', ...), it('name', ...)
            r'|'
            r'(?:test|it|describe)\s*[(`\s]`([^`]+)`'  # test(`name`, ...) with backtick
            r')'
        ),
        comment_line="//",
        comment_block_start="/*",
        comment_block_end="*/",
    ),
    "typescript": LanguagePatterns(
        name="typescript",
        markers=["tsconfig.json"],
        test_dirs=["__tests__", "tests", "spec", "test"],
        test_file_globs=["*.test.ts", "*.spec.ts", "*.test.tsx", "*.spec.tsx"],
        test_fn_regex=(
            r'(?:'
            r'(?:test|it|describe)\s*[(`\s][\'"`]([^\'"]+)[\'"`]'  # test('name'), it("name"), describe(`name`)
            r'|'
            r'(?:test|it|describe)\s*[(`\s]`([^`]+)`'  # template literal
            r')'
        ),
        comment_line="//",
        comment_block_start="/*",
        comment_block_end="*/",
    ),
    "java": LanguagePatterns(
        name="java",
        markers=["pom.xml", "build.gradle", "build.gradle.kts"],
        test_dirs=["src/test/java", "src/test"],
        test_file_globs=["*Test.java", "*Spec.java"],
        test_fn_regex=r'@(?:Test|ParameterizedTest|RepeatedTest)\s*\n\s*(?:public\s+)?void\s+(\w+)',
        comment_line="//",
        comment_block_start="/*",
        comment_block_end="*/",
    ),
    "go": LanguagePatterns(
        name="go",
        markers=["go.mod"],
        test_dirs=[""],
        test_file_globs=["*_test.go"],
        test_fn_regex=r'func\s+(Test\w+)\s*\(\s*t\s*\*testing\.T\b',
        comment_line="//",
        comment_block_start="/*",
        comment_block_end="*/",
    ),
    "rust": LanguagePatterns(
        name="rust",
        markers=["Cargo.toml"],
        test_dirs=["tests"],
        test_file_globs=["*.rs"],
        test_fn_regex=r'#\[(?:test|tokio::test)]\s*\n\s*fn\s+(\w+)',
        comment_line="//",
        comment_block_start="/*",
        comment_block_end="*/",
    ),
    "scala": LanguagePatterns(
        name="scala",
        markers=["build.sbt"],
        test_dirs=["src/test/scala", "src/test"],
        test_file_globs=["*Test.scala", "*Spec.scala", "*Suite.scala"],
        test_fn_regex=(
            r'(?:'
            r'test\s*\(\s*["\']([^\'"]+)["\']'  # test("description")
            r'|'
            r'["\']\s*(?:should|must|can|will)\s+["\']([^\'"]+)["\']'  # "should..." or "must..."
            r'|'
            r'["\']\s*in\s*[{]([^}]+)[}]'  # "description" in {
            r')'
        ),
        comment_line="//",
        comment_block_start="/*",
        comment_block_end="*/",
    ),
    "sql": LanguagePatterns(
        name="sql",
        markers=["liquibase.properties", "changelog"],
        test_dirs=[""],
        test_file_globs=["*.sql", "*.xml"],
        test_fn_regex=r'(?:changeSet|changeset)\s+[\'"]?([\w.-]+)',
        comment_line="--",
        comment_block_start="/*",
        comment_block_end="*/",
    ),
    "generic": LanguagePatterns(
        name="generic",
        markers=[],
        test_dirs=["tests", "test", "spec", "__tests__"],
        test_file_globs=["*"],
        test_fn_regex=r'',  # no function detection in generic mode
        comment_line="",
        comment_block_start="",
        comment_block_end="",
    ),
}


# ---------------------------------------------------------------------------
# Language Detector
# ---------------------------------------------------------------------------


class LanguageDetector:
    """Detect the primary project language from root directory markers.

    Scans the project root for well-known filenames and patterns to
    determine which language(s) the project uses. Returns the first
    matching language, defaulting to ``"generic"`` if nothing matches.
    """

    def __init__(self, root: Path):
        self._root = root

    def detect(self) -> str:
        """Detect the primary project language.

        Returns a language key (``"python"``, ``"javascript"``, etc.)
        or ``"generic"`` if no markers are found.
        """
        root = self._root
        if not root.is_dir():
            return "generic"

        markers = set()
        try:
            for p in root.iterdir():
                if p.is_file():
                    markers.add(p.name.lower())
        except PermissionError:
            return "generic"

        # Priority order: more specific first
        for lang_key, patterns in _LANGUAGES.items():
            if lang_key == "generic":
                continue
            for marker in patterns.markers:
                if marker.lower() in markers:
                    return lang_key

        return "generic"

    @staticmethod
    def get_patterns(language: str) -> LanguagePatterns:
        """Get test patterns for a language.

        Returns the patterns for the given language key, or generic
        patterns if the language is unknown.
        """
        return _LANGUAGES.get(language, _LANGUAGES["generic"])

    @staticmethod
    def supported_languages() -> list[str]:
        """List all supported language keys (excluding 'generic')."""
        return [k for k in _LANGUAGES if k != "generic"]

    def find_test_files(self, root: Path) -> list[Path]:
        """Find test files in the project using language-appropriate patterns."""
        language = self.detect()
        patterns = self.get_patterns(language)
        test_files: list[Path] = []

        if not root.is_dir():
            return test_files

        # Walk through test directories
        search_dirs = [root / d for d in patterns.test_dirs if d] or [root]
        for search_dir in search_dirs:
            if not search_dir.is_dir():
                continue
            for glob_pattern in patterns.test_file_globs:
                for f in search_dir.rglob(glob_pattern):
                    if "__pycache__" not in str(f):
                        test_files.append(f)

        # Also scan root for test files if nothing found in dirs
        if not test_files:
            for glob_pattern in patterns.test_file_globs:
                for f in root.glob(glob_pattern):
                    test_files.append(f)

        return sorted(set(test_files))
