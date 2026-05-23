"""Requirements Conformance Reviewer — Wave 19 Phase 3b.

Verifies that test coverage maps to acceptance criteria. Prevents
drift: tests should verify what was asked for, not just what was built.

Core pipeline:
1. Parse requirements doc to extract structured acceptance criteria
2. Scan all test files for traces of each AC
3. Build traceability matrix (AC ↔ tests)
4. Flag gaps: untested ACs, tests without AC traces
5. Check test-level fit
6. Produce conformance report
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from harness.agents.detectors import LanguageDetector, LanguagePatterns

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class AcceptanceCriterion:
    """A single acceptance criterion extracted from requirements.

    Attributes:
        id: Criterion identifier (e.g. "AC-001", "REQ-1.3").
        requirement_id: The parent requirement ID this criterion belongs to.
        text: The natural-language description of the criterion.
        line: Line number in the source document.
        source_file: Path to the source document.
    """
    id: str
    requirement_id: str
    text: str
    line: int = 0
    source_file: str = ""


@dataclass
class TestMatch:
    """A test that maps to a specific acceptance criterion.

    Attributes:
        test_path: Relative path to the test file.
        test_name: Name of the test function/method.
        line: Line number where the reference was found.
        match_type: How the test references the AC (e.g. "direct", "marker",
            "description", "none").
    """
    test_path: str
    test_name: str
    line: int = 0
    match_type: str = "direct"


@dataclass
class ACConformanceResult:
    """Conformance result for a single acceptance criterion.

    Attributes:
        criterion: The acceptance criterion.
        tests: List of matching tests.
        conformance: ``"verified"`` if at least one test matches,
            ``"untested"`` otherwise.
    """
    criterion: AcceptanceCriterion
    tests: list[TestMatch] = field(default_factory=list)

    @property
    def conformance(self) -> str:
        return "verified" if self.tests else "untested"


@dataclass
class TestWithoutTracking:
    """A test that has no traceable acceptance criterion.

    Attributes:
        test_path: Relative path to the test file.
        test_name: Name of the test function/method.
        line: Line number.
    """
    test_path: str
    test_name: str
    line: int = 0


@dataclass
class ConformanceReport:
    """The full conformance assessment.

    Attributes:
        results: Per-AC conformance results.
        untracked_tests: Tests with no AC reference (implementation drift).
        total_acs: Total acceptance criteria found.
        verified_acs: ACs with at least one matching test.
        untested_acs: ACs with no matching test.
        drift_tests: Number of untracked tests.
    """
    results: list[ACConformanceResult] = field(default_factory=list)
    untracked_tests: list[TestWithoutTracking] = field(default_factory=list)

    @property
    def total_acs(self) -> int:
        return len(self.results)

    @property
    def verified_acs(self) -> int:
        return sum(1 for r in self.results if r.tests)

    @property
    def untested_acs(self) -> int:
        return sum(1 for r in self.results if not r.tests)

    @property
    def drift_tests(self) -> int:
        return len(self.untracked_tests)


# ---------------------------------------------------------------------------
# AC Parser
# ---------------------------------------------------------------------------


class ACParser:
    """Parse acceptance criteria from a requirements document.

    Supports multiple formats:
    - Markdown heading + bullet list: ``## AC-001: Title`` then bullets
    - Numbered list with AC markers: ``- AC-001: ...``
    - Gherkin-style: ``Scenario: ...``
    - Table format: ``| AC-ID | Description |``
    - Freeform: uses regex to find AC-like patterns
    """

    # Pattern: "AC-NNN", "AC NNN", "AC#NNN", "Req-NNN.AC-NNN"
    _AC_PATTERN = re.compile(
        r'(?:^|\s)((?:AC|CRITERION|REQ)[-#]?\d+(?:\.\d+)*)'
        r'(?:\s*[:-]\s*|[\s])([^\n]+)',
        re.IGNORECASE,
    )

    # Gherkin scenario pattern
    _GHERKIN_PATTERN = re.compile(
        r'^\s*(?:Scenario|Example|Scenario Outline):\s*(.+)$',
        re.IGNORECASE | re.MULTILINE,
    )

    # Markdown heading AC pattern
    _HEADING_PATTERN = re.compile(
        r'^#{2,4}\s+(?:(?:AC|Acceptance Criterion|Requirement|REQ)\s+)?'
        r'([A-Z][A-Z0-9_.-]+)\s*[:-]\s*(.+)$',
        re.IGNORECASE | re.MULTILINE,
    )

    # Structured requirement heading with AC sub-items
    _REQ_HEADING = re.compile(
        r'^#{2,4}\s+(?:Req|Requirement|Feature)[^\n]*(?:\n(?!##).*)*',
        re.IGNORECASE | re.MULTILINE,
    )

    def parse(self, doc_path: Path) -> list[AcceptanceCriterion]:
        """Parse a requirements document and extract acceptance criteria."""
        if not doc_path.exists():
            return []

        text = doc_path.read_text(encoding="utf-8", errors="replace")

        criteria: list[AcceptanceCriterion] = []
        seen_ids: set[str] = set()

        lines = text.split("\n")

        # Strategy 1: Heading-based ACs (most structured)
        for match in self._HEADING_PATTERN.finditer(text):
            ac_id = match.group(1).upper()
            desc = match.group(2).strip()
            if ac_id not in seen_ids:
                seen_ids.add(ac_id)
                line_no = 1 + text[:match.start()].count("\n")
                criteria.append(AcceptanceCriterion(
                    id=ac_id,
                    requirement_id=ac_id.rsplit(".", 1)[0] if "." in ac_id else "",
                    text=desc,
                    line=line_no,
                    source_file=str(doc_path),
                ))

        # Strategy 2: Inline AC markers (AC-NNN: description)
        for match in self._AC_PATTERN.finditer(text):
            ac_id = match.group(1).upper()
            desc = match.group(2).strip()
            if ac_id not in seen_ids:
                seen_ids.add(ac_id)
                line_no = 1 + text[:match.start()].count("\n")
                criteria.append(AcceptanceCriterion(
                    id=ac_id,
                    requirement_id="",
                    text=desc,
                    line=line_no,
                    source_file=str(doc_path),
                ))

        # Strategy 3: Gherkin scenarios (Scenario: title)
        for match in self._GHERKIN_PATTERN.finditer(text):
            title = match.group(1).strip()
            # Only use Gherkin if we have no AC identifiers yet
            if not criteria:
                ac_id = f"GHERKIN-{len(criteria) + 1:03d}"
                line_no = 1 + text[:match.start()].count("\n")
                criteria.append(AcceptanceCriterion(
                    id=ac_id,
                    requirement_id="",
                    text=title,
                    line=line_no,
                    source_file=str(doc_path),
                ))

        return criteria


# ---------------------------------------------------------------------------
# Language-aware Test Scanner
# ---------------------------------------------------------------------------


class TestScanner:
    """Scan test files for references to acceptance criteria.

    Language-agnostic: uses :class:`~harness.agents.detectors.LanguageDetector`
    and :class:`~harness.agents.detectors.LanguagePatterns` to auto-detect
    the project language and apply appropriate test-file globs, test-function
    patterns, and AC-reference patterns.

    Identifies AC references via:
    - Direct markers: ``@ac("AC-001")``, ``# AC-001``, ``// AC-001``
    - Test name conventions: ``test_AC_001_*``, ``testAC001``
    - Comment-based references: ``# AC-001``, ``// AC-001``, ``-- AC-001``

    Falls back to Python-specific patterns when no language is detected.
    """

    def __init__(
        self,
        root_path: Path | None = None,
        language: str | None = None,
    ):
        """Initialise the scanner.

        Args:
            root_path: Project root directory for language auto-detection.
                       If ``None``, uses the parent of ``test_dir`` passed
                       to :meth:`scan`.
            language: Explicit language key (e.g. ``"python"``,
                      ``"javascript"``). Overrides auto-detection.
        """
        self._root_path = root_path
        self._explicit_language = language
        self._detector: LanguageDetector | None = None
        self._patterns: LanguagePatterns | None = None

    def _resolve_patterns(self, test_dir: Path) -> None:
        """Resolve language patterns if not already set."""
        if self._patterns is not None:
            return

        if self._explicit_language:
            self._patterns = LanguageDetector.get_patterns(
                self._explicit_language
            )
            return

        root = self._root_path or test_dir.parent
        self._detector = LanguageDetector(root)
        lang = self._detector.detect()
        self._patterns = LanguageDetector.get_patterns(lang)

    def scan(self, test_dir: Path) -> dict[str, list[TestMatch]]:
        """Scan test files for AC references.

        Uses language-appropriate file detection and test patterns.

        Returns a dict mapping AC IDs (uppercased) to list of
        ``TestMatch`` entries.
        """
        self._resolve_patterns(test_dir)
        ac_to_tests: dict[str, list[TestMatch]] = {}

        if not test_dir.is_dir():
            return ac_to_tests

        test_files = self._find_test_files(test_dir)
        for file_path in test_files:
            if "__pycache__" in str(file_path):
                continue
            rel_path = str(
                file_path.relative_to(test_dir.parent)
                if test_dir.parent
                else file_path
            )
            self._scan_file(file_path, rel_path, ac_to_tests)

        return ac_to_tests

    def _find_test_files(self, test_dir: Path) -> list[Path]:
        """Find test files using language-appropriate glob patterns."""
        patterns = self._patterns or LanguageDetector.get_patterns("python")
        test_files: list[Path] = []

        # Build search directories: use language-specific test dirs
        # relative to the test_dir, or fall back to test_dir itself
        search_dirs: list[Path] = []
        for d in patterns.test_dirs:
            if d:
                candidate = test_dir / d
                if candidate.is_dir():
                    search_dirs.append(candidate)
        if not search_dirs:
            search_dirs = [test_dir]

        for search_dir in search_dirs:
            for glob_pattern in patterns.test_file_globs:
                for f in search_dir.rglob(glob_pattern):
                    if "__pycache__" not in str(f):
                        test_files.append(f)

        # If nothing found in language-specific dirs, try the test_dir
        # directly with generic globs
        if not test_files:
            for glob_pattern in patterns.test_file_globs:
                for f in test_dir.rglob(glob_pattern):
                    if "__pycache__" not in str(f):
                        test_files.append(f)

        # Generic fallback: any file under test_dir
        if not test_files:
            for f in test_dir.rglob("*"):
                if f.is_file() and "__pycache__" not in str(f):
                    test_files.append(f)

        return sorted(set(test_files))

    def _build_test_fn_regex(self, raw: str) -> re.Pattern | None:
        """Build a compiled regex from a test function pattern string.

        Returns ``None`` for empty patterns (generic mode).
        """
        if not raw.strip():
            return None
        flags = getattr(self._patterns, "test_fn_regex_flags", re.MULTILINE)
        return re.compile(raw, flags)

    def _scan_file(
        self,
        file_path: Path,
        rel_path: str,
        ac_to_tests: dict[str, list[TestMatch]],
    ) -> list[TestWithoutTracking]:
        """Scan a single file for AC references and test definitions.

        Uses language-appropriate test function patterns and AC reference
        patterns from the resolved ``LanguagePatterns``.
        """
        patterns = self._patterns or LanguageDetector.get_patterns("python")
        untracked: list[TestWithoutTracking] = []

        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            return untracked

        # Compile language-appropriate test function regex
        fn_re = self._build_test_fn_regex(patterns.test_fn_regex)

        # Generic mode: no function pattern — scan entire file for AC refs
        if fn_re is None:
            self._scan_file_generic(
                text, file_path, rel_path, ac_to_tests, untracked
            )
            return untracked

        # Find all test function definitions using the language pattern
        test_fns = list(fn_re.finditer(text))
        if not test_fns:
            return untracked

        lines = text.split("\n")
        ac_ref_re = self._build_ac_reference_regex(patterns)

        for fn_match in test_fns:
            # Extract test name from the FIRST non-None group
            test_name = next(
                (g for g in fn_match.groups() if g is not None),
                fn_match.group(0).strip(),
            ).strip()
            fn_line = 1 + text[:fn_match.start()].count("\n")
            fn_env_lines = self._get_function_context(lines, fn_line, patterns)

            ac_refs_found: list[str] = []
            for ac_match in ac_ref_re.finditer(fn_env_lines):
                # Extract AC ID from the FIRST non-None group in this match
                ac_id = next(
                    (g for g in ac_match.groups() if g is not None),
                    "UNKNOWN",
                ).upper()
                ac_refs_found.append(ac_id)
                if ac_id not in ac_to_tests:
                    ac_to_tests[ac_id] = []
                ac_to_tests[ac_id].append(TestMatch(
                    test_path=rel_path,
                    test_name=test_name,
                    line=fn_line,
                    match_type="direct",
                ))

            # Check test name for AC pattern
            name_re = re.compile(patterns.ac_name_regex, re.IGNORECASE)
            name_match = name_re.search(test_name)
            if name_match:
                ac_id = f"AC-{name_match.group(1)}"
                if ac_id not in ac_to_tests:
                    ac_to_tests[ac_id] = []
                ac_to_tests[ac_id].append(TestMatch(
                    test_path=rel_path,
                    test_name=test_name,
                    line=fn_line,
                    match_type="naming",
                ))

            # If no AC found, mark as untracked
            if not ac_refs_found and not name_match:
                untracked.append(TestWithoutTracking(
                    test_path=rel_path,
                    test_name=test_name,
                    line=fn_line,
                ))

        return untracked

    def _scan_file_generic(
        self,
        text: str,
        file_path: Path,
        rel_path: str,
        ac_to_tests: dict[str, list[TestMatch]],
        untracked: list[TestWithoutTracking],
    ) -> None:
        """Scan a file in generic mode (no specific function pattern).

        Scans the entire file for any AC reference markers without
        trying to identify specific test functions.
        """
        patterns = self._patterns or LanguageDetector.get_patterns("generic")
        ac_ref_re = self._build_ac_reference_regex(patterns)

        for ac_match in ac_ref_re.finditer(text):
            ac_id = next(
                (g for g in ac_match.groups() if g is not None),
                "UNKNOWN",
            ).upper()
            ref_line = 1 + text[:ac_match.start()].count("\n")
            if ac_id not in ac_to_tests:
                ac_to_tests[ac_id] = []
            ac_to_tests[ac_id].append(TestMatch(
                test_path=rel_path,
                test_name="(generic)",
                line=ref_line,
                match_type="direct",
            ))

    def _build_ac_reference_regex(
        self,
        patterns: LanguagePatterns,
    ) -> re.Pattern:
        """Build a composite regex for AC references.

        Combines decorator-style AC refs (``@ac("AC-001")``) and
        comment-style AC refs (``# AC-001``, ``// AC-001``) into a
        single pattern.
        """
        parts: list[str] = []

        # Decorator pattern
        parts.append(f"(?:{patterns.ac_decorator_regex})")

        # Comment pattern (if not empty)
        if patterns.ac_comment_regex.strip():
            parts.append(f"(?:{patterns.ac_comment_regex})")

        combined = "|".join(parts)
        return re.compile(combined, re.IGNORECASE | re.MULTILINE)

    @staticmethod
    def _get_function_context(
        lines: list[str],
        fn_line: int,
        patterns: LanguagePatterns | None = None,
    ) -> str:
        """Get surrounding context for a function definition line.

        Includes the function definition, preceding decorators, and
        any docstring or body start.
        """
        start = max(0, fn_line - 5)  # include decorators
        end = min(len(lines), fn_line + 15)  # include docstring/body start
        return "\n".join(lines[start:end])


# ---------------------------------------------------------------------------
# Conformance Analyser
# --------------------------------------------------------------------------


class ConformanceAnalyser:
    """Build the conformance report from ACs and test scan results.

    Orchestrates the full analysis pipeline:
    parse ACs → scan tests → build report → assess test-level fit.
    """

    def __init__(
        self,
        ac_parser: ACParser | None = None,
        test_scanner: TestScanner | None = None,
    ):
        self._ac_parser = ac_parser or ACParser()
        self._test_scanner = test_scanner or TestScanner()

    def analyse(
        self,
        requirements_path: Path,
        test_dir: Path,
    ) -> ConformanceReport:
        """Run the full conformance analysis pipeline."""
        # 1. Parse acceptance criteria
        acs = self._ac_parser.parse(requirements_path)

        # 2. Scan tests for AC references
        ac_to_tests = self._test_scanner.scan(test_dir)

        # 3. Build per-AC results
        results: list[ACConformanceResult] = []
        for ac in acs:
            matched_tests = ac_to_tests.get(ac.id, [])
            # Also match by partial ID (e.g. "REQ-001" covers "REQ-001.AC-001")
            for ac_id, tests in ac_to_tests.items():
                if ac.id in ac_id and ac.id != ac_id:
                    matched_tests.extend(tests)

            results.append(ACConformanceResult(
                criterion=ac,
                tests=matched_tests,
            ))

        # 4. Find untracked tests (implementation drift)
        untracked_tests = self._find_untracked_tests(test_dir, ac_to_tests, acs)

        return ConformanceReport(
            results=results,
            untracked_tests=untracked_tests,
        )

    def _find_untracked_tests(
        self,
        test_dir: Path,
        ac_to_tests: dict[str, list[TestMatch]],
        acs: list[AcceptanceCriterion],
    ) -> list[TestWithoutTracking]:
        """Find tests that have no traceable AC reference."""
        # Use the same TestScanner (with same patterns) for untracked detection
        scanner = self._test_scanner
        all_untracked: list[TestWithoutTracking] = []

        if not test_dir.is_dir():
            return all_untracked

        test_files = scanner._find_test_files(test_dir)
        for file_path in test_files:
            if "__pycache__" in str(file_path):
                continue
            rel_path = str(
                file_path.relative_to(test_dir.parent)
                if test_dir.parent
                else file_path
            )
            # Pass an empty dict so nothing gets added to ac_to_tests
            untracked = scanner._scan_file(file_path, rel_path, {})
            all_untracked.extend(untracked)

        return all_untracked


# ---------------------------------------------------------------------------
# Report Builder
# ---------------------------------------------------------------------------


class ConformanceReportBuilder:
    """Format a ConformanceReport as Markdown."""

    def as_markdown(self, report: ConformanceReport) -> str:
        """Render the conformance report as Markdown."""
        lines = [
            "# Requirements Conformance Report",
            "",
            "## Summary",
            "",
            f"- **Total acceptance criteria:** {report.total_acs}",
            f"- **Verified (covered by tests):** {report.verified_acs}",
            f"- **Untested (no matching test):** {report.untested_acs}",
            f"- **Implementation drift (tests without AC):** {report.drift_tests}",
            f"- **Conformance score:** {self._score(report)}%",
            "",
        ]

        if report.total_acs == 0:
            lines.append("*No acceptance criteria found in requirements document.*")
            lines.append("")
            return "\n".join(lines)

        # Per-AC detail
        lines.append("## Criterion-by-Criterion Analysis")
        lines.append("")
        for result in report.results:
            ac = result.criterion
            status = "✅ VERIFIED" if result.tests else "❌ UNTESTED"
            lines.append(f"### {ac.id}: {ac.text}")
            lines.append(f"**Status:** {status}")
            lines.append(f"**Source:** {ac.source_file}:{ac.line}")
            if result.tests:
                lines.append("**Tests:**")
                for t in result.tests:
                    lines.append(f"- `{t.test_path}` :: `{t.test_name}` (line {t.line})")
            lines.append("")

        # Untracked tests
        if report.untracked_tests:
            lines.append("## Implementation Drift — Tests Without Requirements Trace")
            lines.append("")
            lines.append(
                "These tests exercise the code but cannot be traced back to any "
                "acceptance criterion. They may represent scope creep, exploratory "
                "testing, or missing requirements documentation."
            )
            lines.append("")
            for t in report.untracked_tests:
                lines.append(f"- `{t.test_path}` :: `{t.test_name}` (line {t.line})")
            lines.append("")

        # Recommendations
        lines.append("## Recommendations")
        lines.append("")
        recs = self._recommendations(report)
        if recs:
            for r in recs:
                lines.append(f"- {r}")
        else:
            lines.append("- All acceptance criteria have test coverage.")
            lines.append("- Consider adding more tests for edge cases.")

        lines.append("")
        return "\n".join(lines)

    def _score(self, report: ConformanceReport) -> float:
        """Calculate conformance score as a percentage."""
        if report.total_acs == 0:
            return 0.0
        return round((report.verified_acs / report.total_acs) * 100, 1)

    def _recommendations(self, report: ConformanceReport) -> list[str]:
        """Generate recommendations based on the report."""
        recs: list[str] = []

        if report.untested_acs > 0:
            recs.append(
                f"**{report.untested_acs} acceptance criteria have no test "
                f"coverage.** Add tests that verify each criterion before "
                f"proceeding."
            )

        if report.drift_tests > 0:
            recs.append(
                f"**{report.drift_tests} tests have no traceable AC.** "
                f"Either add AC references to these tests, or document "
                f"the implicit requirements they validate."
            )

        if report.total_acs > 0 and report.untested_acs == 0:
            recs.append(
                "All acceptance criteria are covered by tests. Good."
            )

        return recs


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def run_conformance_review(
    requirements_path: Path,
    test_dir: Path,
    report_path: Path | None = None,
    root_path: Path | None = None,
    language: str | None = None,
) -> ConformanceReport:
    """Run the full requirements conformance review pipeline.

    Args:
        requirements_path: Path to the requirements document.
        test_dir: Path to the test directory to scan.
        report_path: Optional path to write the Markdown report.
        root_path: Optional project root for language auto-detection.
                   If ``None``, uses the parent of ``test_dir``.
        language: Optional explicit language key (e.g. ``"python"``).
                  If provided, skips auto-detection.

    Returns:
        The ``ConformanceReport`` with per-AC results.
    """
    scanner = TestScanner(root_path=root_path, language=language)
    analyser = ConformanceAnalyser(test_scanner=scanner)
    report = analyser.analyse(requirements_path, test_dir)

    if report_path:
        builder = ConformanceReportBuilder()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(builder.as_markdown(report))

    return report
