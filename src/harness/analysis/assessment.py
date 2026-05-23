"""Assessment — independent codebase assessment via LLM analysis agents.

Gathers repo context, dispatches P1-P5 analysis agents in parallel
via AgentRunner, parses JSON responses, and aggregates into an
AssessmentReport with scoring and formatting.

R22 — Independent Repository Assessment
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.agents.runner import AgentRunner
from harness.analysis.agents import AnalysisAgent, AnalysisAgentRegistry

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

DEFAULT_README = "README.md"
MAX_README_LINES = 200
MAX_SOURCE_FILE_LINES = 200

PYPROJECT_TOML = "pyproject.toml"

BUILD_FILE_MARKERS: list[str] = [
    PYPROJECT_TOML,
    "Cargo.toml", "package.json", "pom.xml",
    "build.gradle", "build.gradle.kts", "CMakeLists.txt",
    "setup.cfg", "requirements.txt", "Pipfile",
    "composer.json", "project.clj", "mix.exs",
    "pubspec.yaml", "Podfile", "Cartfile",
    "gradle.properties", "gradle/libs.versions.toml",
]


# Directories to skip when gathering context
SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "node_modules", ".tox",
    ".eggs", "*.egg-info", ".pytest_cache", ".mypy_cache",
    ".coverage", ".DS_Store", "dist", "build", ".harness",
}

# Max context size per analysis agent (chars to avoid blowing LLM context)
MAX_CONTEXT_CHARS = 80_000


@dataclass
class AssessmentReport:
    """Aggregated result of a full independent assessment."""

    path: str = ""
    """Absolute path to the analysed directory."""

    projects: list[dict[str, Any]] = field(default_factory=list)
    """Detected projects and their profiles."""

    findings: list[dict[str, Any]] = field(default_factory=list)
    """Aggregated findings across all dimensions."""

    score: str = "unknown"
    """Overall score: excellent, good, fair, poor, unknown."""

    recommendations: list[str] = field(default_factory=list)
    """Cross-cutting recommendations."""

    agent_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Raw output from each analysis agent by name."""

    agent_status: dict[str, str] = field(default_factory=dict)
    """Status per agent: success, failure, degraded, skipped."""

    metrics: dict[str, Any] = field(default_factory=dict)
    """Execution metrics: duration, agent counts, etc."""

    report_text: str = ""
    """Human-readable formatted report."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to a serialisable dict."""
        return {
            "assessment": {
                "path": self.path,
                "projects": self.projects,
                "findings": self.findings,
                "score": self.score,
                "recommendations": self.recommendations,
                "agent_results": self.agent_results,
                "agent_status": self.agent_status,
                "metrics": self.metrics,
            },
            "report": self.report_text,
        }


def gather_context(root: Path) -> dict[str, Any]:
    """Gather filesystem context for analysis agents.

    Collects directory tree overview, README content, key config files,
    and code structure. Returns a dict suitable for inclusion in LLM
    prompts.

    Args:
        root: Directory to analyse.

    Returns:
        Dict with context data for analysis agents.
    """
    context: dict[str, Any] = {
        "root": str(root),
        "directory_tree": _build_tree(root, max_depth=4),
        "readme_content": _read_first_n_lines(
            root / DEFAULT_README, max_lines=MAX_README_LINES
        ),
        "config_files": _collect_config_files(root),
        "key_source_files": _collect_key_files(root),
        "entry_points": _detect_entry_points(root),
        "source_content": _collect_source_samples(root),
        "has_dockerfile": (root / "Dockerfile").exists()
        or any(
            p.name == "Dockerfile"
            for p in root.iterdir()
            if p.is_file()
        ),
        "has_makefile": (root / "Makefile").exists(),
        "test_directory": (root / "tests").exists()
        or (root / "test").exists(),
        "is_git_repo": _is_git_repo(root),
    }

    return context


async def assess(
    path: str | Path,
    deep: bool = True,
    agent_names: list[str] | None = None,
    runner_config: dict[str, Any] | None = None,
) -> AssessmentReport:
    """Run a full independent assessment of a codebase.

    This is the main entry point. Gathers context, dispatches all
    selected analysis agents in parallel via AgentRunner, parses
    JSON responses, and aggregates into an AssessmentReport.

    Args:
        path: Directory to analyse.
        deep: If True, run all P1-P5 agents. If False, run only
            P1 (Project Profiler) and P2 (Responsibility Decoder).
        agent_names: Specific agents to run (overrides deep flag).
        runner_config: Optional config for AgentRunner.

    Returns:
        AssessmentReport with all findings.
    """
    import time
    start_time = time.monotonic()

    root = Path(path).resolve()
    report = AssessmentReport(path=str(root))

    # 1. Validate path before gathering context
    if not root.exists():
        report.score = "unknown"
        report.report_text = f"Error: Path does not exist: {path}"
        report.metrics["duration_ms"] = 0
        return report

    # 2. Gather context
    logger.info("Gathering context from %s", root)
    context = gather_context(root)

    # 3. Select agents
    if agent_names:
        agents = [
            a for a in AnalysisAgentRegistry.get_all()
            if a.name in agent_names
        ]
    elif deep:
        agents = AnalysisAgentRegistry.get_all()
    else:
        agents = [
            AnalysisAgentRegistry.get("project-profiler"),
            AnalysisAgentRegistry.get("responsibility-decoder"),
        ]
        agents = [a for a in agents if a is not None]

    if not agents:
        report.score = "unknown"
        report.report_text = "No analysis agents selected."
        report.metrics["duration_ms"] = 0
        return report

    # 3. Dispatch all agents in parallel
    runner = AgentRunner(runner_config or {})
    context_json = _format_context_for_llm(context)

    async def run_agent(agent: AnalysisAgent) -> tuple[str, dict[str, Any], str]:
        """Run a single analysis agent and return (name, parsed_output, status)."""
        try:
            # Build the prompt with system prompt + context + output schema
            spec = _build_agent_prompt(agent, context_json)

            result = await runner.run_simple(
                spec_content=spec,
                backend_name="api",
                model=agent.model,
                project_dir=root,
                agent_role=agent.agent_role,
            )

            if result.startswith("Error:"):
                logger.warning("Agent '%s' failed: %s", agent.name, result)
                return agent.name, {}, "failure"

            # Try to parse JSON from the result
            parsed = _extract_json(result)
            if parsed is None:
                logger.warning(
                    "Agent '%s' returned non-JSON output. "
                    "Falling back to text.",
                    agent.name,
                )
                return agent.name, {"_raw_text": result[:2000]}, "degraded"

            return agent.name, parsed, "success"

        except Exception as exc:
            logger.error(
                "Agent '%s' raised exception: %s", agent.name, exc
            )
            return agent.name, {}, "failure"

    # Run agents sequentially to respect rate limits
    agent_tasks = [run_agent(a) for a in agents]
    results = await asyncio.gather(*agent_tasks, return_exceptions=True)

    # 4. Process results
    for result in results:
        if isinstance(result, BaseException):
            logger.error("Agent task raised: %s", result)
            continue

        agent_name, data, status = result
        report.agent_results[agent_name] = data
        report.agent_status[agent_name] = status

        if status == "success":
            _merge_agent_output(report, agent_name, data)

    # 5. Derive overall score
    report.score = _compute_overall_score(report)
    report.metrics["duration_ms"] = int(
        (time.monotonic() - start_time) * 1000
    )
    report.metrics["agents_run"] = len(agents)
    report.metrics["agents_succeeded"] = sum(
        1 for s in report.agent_status.values() if s == "success"
    )
    report.metrics["agents_degraded"] = sum(
        1 for s in report.agent_status.values() if s == "degraded"
    )
    report.metrics["agents_failed"] = sum(
        1 for s in report.agent_status.values() if s == "failure"
    )

    # 6. Deduplicate findings
    report.findings = _deduplicate_findings(report.findings)

    # 7. Format report
    report.report_text = format_assessment_report(report)
    report.findings.sort(
        key=lambda f: {"critical": 0, "error": 1, "warning": 2, "info": 3}.get(
            f.get("severity", "info"), 4
        )
    )

    return report


# ── Context helpers ───────────────────────────────────────────────────────────


def _build_tree(root: Path, max_depth: int = 4) -> str:
    """Build a tree-like representation of the directory."""
    lines: list[str] = []

    def _walk(dir_path: Path, depth: int):
        if depth > max_depth:
            return
        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        except PermissionError:
            return

        for entry in entries:
            if entry.name in SKIP_DIRS:
                continue
            indent = "  " * depth
            if entry.is_dir():
                lines.append(f"{indent}{entry.name}/")
                _walk(entry, depth + 1)
            else:
                lines.append(f"{indent}{entry.name}")

    _walk(root, 0)
    return "\n".join(lines[:200])  # cap at 200 lines


def _read_first_n_lines(path: Path, max_lines: int = 200) -> str:
    """Read the first N lines of a file."""
    if not path.exists():
        return ""
    try:
        with open(path, errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line.rstrip("\n"))
            return "\n".join(lines)
    except (OSError, UnicodeDecodeError):
        return ""


def _collect_config_files(root: Path) -> dict[str, str]:
    """Collect content of key config files."""
    config_patterns = BUILD_FILE_MARKERS.copy()
    # Add additional build file patterns (not commonly used as project markers)
    config_patterns.extend([
        "Makefile", "go.mod", "Gemfile", "setup.py",
    ])
    configs = {}
    for pattern in config_patterns:
        p = root / pattern
        if p.exists():
            configs[pattern] = _read_first_n_lines(p, max_lines=100)
    return configs


def _collect_key_files(root: Path) -> dict[str, str]:
    """Collect content of key source files for understanding structure."""
    key_files = {}

    # Collect __init__.py from subdirectories
    for init in sorted(root.rglob("src/*/__init__.py")):
        if not any(skip in str(init) for skip in SKIP_DIRS):
            rel = init.relative_to(root)
            key_files[str(rel)] = _read_first_n_lines(init, max_lines=50)

    # Collect entry point files
    entry_patterns = ["main.py", "cli.py", "app.py", "wsgi.py", "asgi.py"]
    for pattern in entry_patterns:
        p = root / "src" / pattern
        if p.exists():
            rel = p.relative_to(root)
            key_files[str(rel)] = _read_first_n_lines(p, max_lines=100)

    return key_files


def _collect_source_samples(
    root: Path,
    max_files: int = 20,
    max_total_chars: int = 60000,
) -> dict[str, str]:
    """Collect actual source and test file content for LLM evaluation.

    Strategy:
    1. Entry points first (main.py, cli.py, app.py)
    2. Domain/core modules (src/*/domain/, src/*/core/, src/*/models/)
    3. Test files (tests/test_*.py, tests/*/test_*.py)
    4. Representative source files from src/
    5. Capped at max_files and max_total_chars (to stay within context budget)
    6. Graceful on binary files, giant files, or encoding errors

    Returns dict of {relative_filepath: content_string}.
    Returns empty dict on any error.
    """
    from harness.analysis.fast import SKIP_DIRS as FAST_SKIP_DIRS

    try:
        if not root.exists() or not root.is_dir():
            return {}

        all_skip_dirs = SKIP_DIRS | FAST_SKIP_DIRS

        # Priority collections
        candidate_files: list[Path] = []
        seen: set[Path] = set()

        def _add(path: Path) -> None:
            if path in seen:
                return
            if any(skip in str(path) for skip in all_skip_dirs):
                return
            seen.add(path)
            candidate_files.append(path)

        # 1. Entry points
        entry_patterns = ["main.py", "cli.py", "app.py", "wsgi.py", "asgi.py"]
        src_root = root / "src"
        if src_root.exists():
            for pattern in entry_patterns:
                p = src_root / pattern
                if p.exists():
                    _add(p)

        # 2. Domain/core modules
        for pattern in ["domain", "core", "models"]:
            for p in sorted(root.rglob(f"src/*/{pattern}/*.py")):
                _add(p)

        # 3. Test files
        for p in sorted(root.rglob("tests/test_*.py")):
            _add(p)
        for p in sorted(root.rglob("tests/*/test_*.py")):
            _add(p)

        # 4. Representative source files from src/
        for p in sorted(src_root.rglob("*.py")) if src_root.exists() else []:
            _add(p)

        # Limit to max_files
        candidate_files = candidate_files[:max_files]

        # Read contents with caps
        result: dict[str, str] = {}
        total_chars = 0
        max_lines_per_file = 500

        for file_path in candidate_files:
            try:
                rel = file_path.relative_to(root)
                content = file_path.read_text(errors="replace")
                lines = content.splitlines()
                if len(lines) > max_lines_per_file:
                    lines = lines[:max_lines_per_file]
                    lines.append(f"# ... truncated at {max_lines_per_file} lines")
                content = "\n".join(lines)

                chunk = content[:max_total_chars - total_chars]
                if not chunk and content:
                    # Content can't fit within remaining budget
                    break
                if not content:
                    # Empty file — skip it
                    continue
                result[str(rel)] = chunk
                total_chars += len(chunk)

                if total_chars >= max_total_chars:
                    break

            except (UnicodeDecodeError, OSError, PermissionError):
                continue

        return result

    except Exception:
        logger.debug("_collect_source_samples failed", exc_info=True)
        return {}


def _detect_entry_points(root: Path) -> list[str]:
    """Detect likely entry points in the codebase."""
    entry_points = []

    # Check pyproject.toml for console_scripts
    pyproject = root / PYPROJECT_TOML
    if pyproject.exists():
        content = pyproject.read_text(errors="replace")
        for match in re.finditer(
            r'([\w.-]+)\s*=\s*"([\w.]+):([\w]+)"',
            content,
        ):
            entry_points.append(f"script:{match.group(1)}")

    # Check for main() function definitions
    for py_file in root.rglob("*.py"):
        if any(skip in str(py_file) for skip in SKIP_DIRS):
            continue
        try:
            content = py_file.read_text(errors="replace")
            if re.search(r'if\s+__name__\s*==\s*["\']__main__["\']', content):
                rel = py_file.relative_to(root) if py_file != root else py_file
                entry_points.append(f"main:{rel}")
        except (OSError, UnicodeDecodeError):
            continue

    return entry_points


def _is_git_repo(root: Path) -> bool:
    """Check if the directory is a git repository."""
    return (root / ".git").exists()


# ── LLM prompt building ──────────────────────────────────────────────────────


def _format_context_for_llm(context: dict[str, Any]) -> str:
    """Format the gathered context into a structured text block for LLM input.

    Builds context as named sections with importance levels for semantic
    truncation. When the total exceeds MAX_CONTEXT_CHARS, sections are
    removed in order of least-to-most important:

    1. Source files (test content removed before source content)
    2. Key source files
    3. Config files
    4. README and entry points
    5. Directory tree and metadata (always kept)
    """
    # Build named sections: (priority, section_name, content_text)
    # Lower priority = removed first during truncation
    sections: list[tuple[int, str, str]] = []

    # (priority 5) Base location — always kept
    location_text = f"## Codebase Location\n{context['root']}\n"
    sections.append((5, "location", location_text))

    # (priority 5) Directory tree — always kept
    if context["directory_tree"]:
        tree_text = (
            "## Directory Structure\n```\n"
            f"{context['directory_tree']}\n```\n"
        )
        sections.append((5, "directory_tree", tree_text))

    # (priority 5) Metadata — always kept
    metadata_text = "## Metadata\n"
    metadata_text += f"- Has Dockerfile: {context['has_dockerfile']}\n"
    metadata_text += f"- Has Makefile: {context['has_makefile']}\n"
    metadata_text += f"- Has test directory: {context['test_directory']}\n"
    metadata_text += f"- Is git repo: {context['is_git_repo']}\n"
    sections.append((5, "metadata", metadata_text))

    # (priority 4) README
    if context["readme_content"]:
        readme_text = (
            "## README\n```\n"
            f"{context['readme_content']}\n```\n"
        )
        sections.append((4, "readme", readme_text))

    # (priority 4) Entry points
    if context["entry_points"]:
        ep_lines = "## Entry Points\n"
        for ep in context["entry_points"]:
            ep_lines += f"- {ep}\n"
        sections.append((4, "entry_points", ep_lines))

    # (priority 3) Config files
    if context["config_files"]:
        config_text = "## Config Files\n"
        for name, content in context["config_files"].items():
            if content:
                config_text += f"### {name}\n```\n{content}\n```\n"
        sections.append((3, "config_files", config_text))

    # (priority 2) Key source files
    if context["key_source_files"]:
        key_text = "## Key Source Files\n"
        for name, content in context["key_source_files"].items():
            if content:
                key_text += f"### {name}\n```\n{content}\n```\n"
        sections.append((2, "key_source_files", key_text))

    # (priority 1) Source content — split into two: test and non-test
    source_content = context.get("source_content", {})
    if source_content:
        test_content_parts: dict[str, str] = {}
        src_content_parts: dict[str, str] = {}
        for filepath, content in source_content.items():
            if "test" in filepath:
                test_content_parts[filepath] = content
            else:
                src_content_parts[filepath] = content

        # Build test source section (priority 1 — removed first)
        if test_content_parts:
            test_text = "## Source Content (Test Files)\n"
            for fpath, content in sorted(test_content_parts.items()):
                if content:
                    test_text += f"### {fpath}\n```\n{content}\n```\n"
            sections.append((1, "source_test", test_text))

        # Build source section (priority 1 — removed after test)
        if src_content_parts:
            src_text = "## Source Content\n"
            for fpath, content in sorted(src_content_parts.items()):
                if content:
                    src_text += f"### {fpath}\n```\n{content}\n```\n"
            sections.append((1, "source_src", src_text))

    # Build context from sections, applying semantic truncation
    return _join_sections(sections, max_chars=MAX_CONTEXT_CHARS)


def _join_sections(
    sections: list[tuple[int, str, str]],
    max_chars: int = MAX_CONTEXT_CHARS,
) -> str:
    """Join sections, truncating by importance if total exceeds max_chars.

    Removes entire sections starting from lowest priority (1) to highest (5),
    preserving section boundaries. Within the same priority, later sections
    are removed first.
    """
    total = sum(len(text) for _, _, text in sections)

    if total <= max_chars:
        return "\n".join(text for _, _, text in sections)

    # Build removal order: lowest priority first, then reverse index within same priority
    indexed = list(enumerate(sections))
    removal_order = sorted(
        indexed, key=lambda x: (x[1][0], -x[0])
    )

    # Track which original indices to keep
    keep_indices = set(range(len(sections)))

    for orig_idx, (_prio, _name, text) in removal_order:
        if total <= max_chars:
            break
        if orig_idx in keep_indices:
            total -= len(text)
            keep_indices.remove(orig_idx)

    if not keep_indices:
        # Fallback: at least keep location + tree + metadata
        fallback = [
            text for _, name, text in sections
            if name in ("location", "directory_tree", "metadata")
        ]
        return "\n".join(fallback)

    return "\n".join(
        text for i, (_, _, text) in enumerate(sections) if i in keep_indices
    )


def _build_agent_prompt(agent: AnalysisAgent, context: str) -> str:
    """Build the full prompt for an analysis agent.

    Combines the agent's system prompt, codebase context, and output
    schema instructions into a single spec_content string for the
    AgentRunner.
    """
    schema_json = json.dumps(agent.output_schema, indent=2)

    return (
        f"{agent.system_prompt}\n\n"
        f"---\n\n"
        f"Analyse the following codebase and produce a structured assessment.\n\n"
        f"{context}\n\n"
        f"---\n\n"
        f"Respond with ONLY a valid JSON object matching this schema. "
        f"Do not include any explanatory text before or after the JSON.\n\n"
        f"```json\n{schema_json}\n```"
    )


# ── JSON extraction ──────────────────────────────────────────────────────────


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from text, trying multiple strategies.

    1. Try to parse the entire text as JSON
    2. Try to find a ```json ... ``` code block
    3. Try to find a { ... } block at the top level
    """
    # Strategy 1: Full text parse
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from JSON code block
    json_match = re.search(
        r"```(?:json)?\n?(.*?)```", text, re.DOTALL
    )
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find top-level { ... } with string boundary awareness
    # Handles cases where JSON contains code snippets with braces in string values.
    brace_start = text.find("{")
    if brace_start >= 0:
        depth = 0
        in_string = False
        escape = False
        for i in range(brace_start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\" and in_string:
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[brace_start : i + 1])
                        except json.JSONDecodeError:
                            break

    return None


# ── Result merging ───────────────────────────────────────────────────────────


def _merge_agent_output(
    report: AssessmentReport,
    agent_name: str,
    data: dict[str, Any],
) -> None:
    """Merge an agent's output into the assessment report."""
    if agent_name == "project-profiler":
        projects = data.get("projects", [])
        report.projects.extend(projects)
        for p in projects:
            report.findings.append({
                "severity": "info",
                "category": "project_profile",
                "message": (
                    f"Detected project '{p.get('name', 'unknown')}' "
                    f"as {p.get('type', 'unknown')} "
                    f"({p.get('language', 'unknown')})"
                ),
                "file": p.get("name", ""),
                "confidence": p.get("confidence", "low"),
            })

    elif agent_name == "responsibility-decoder":
        projects = data.get("projects", [])
        _merge_purposes(report, projects)
        for p in projects:
            report.findings.append({
                "severity": "info",
                "category": "purpose",
                "message": (
                    f"Project '{p.get('name', 'unknown')}' purpose: "
                    f"{p.get('purpose', 'unknown')} "
                    f"(confidence: {p.get('confidence', 'low')})"
                ),
                "file": p.get("name", ""),
            })

    elif agent_name == "architecture-critic":
        arch = data.get("architecture", {})
        pattern = arch.get("recognised_pattern", "unrecognisable")
        report.findings.append({
            "severity": "info",
            "category": "architecture",
            "message": (
                f"Architecture pattern: {pattern} "
                f"(confidence: {arch.get('confidence', 'low')})"
            ),
        })

        violations = data.get("boundary_violations", [])
        for v in violations:
            report.findings.append({
                "severity": v.get("severity", "warning"),
                "category": "architecture",
                "message": (
                    f"Boundary violation: {v.get('violation', '')} "
                    f"in {v.get('violator', 'unknown')}"
                ),
                "file": v.get("violator", ""),
            })

        recs = data.get("recommendations", [])
        report.recommendations.extend(
            f"[Architecture] {r}" for r in recs
        )

    elif agent_name == "code-critic":
        dims = data.get("dimensions", [])
        for d in dims:
            rating = d.get("rating", "pass")
            if rating == "fail":
                severity = "error"
            elif rating == "warn":
                severity = "warning"
            else:
                severity = "info"
            for finding in d.get("findings", []):
                report.findings.append({
                    "severity": finding.get("severity", severity),
                    "category": "code_quality",
                    "message": (
                        f"[{d.get('name', 'unknown')}] "
                        f"{finding.get('message', '')}"
                    ),
                    "file": finding.get("file", ""),
                    "line": finding.get("line"),
                })

        recs = data.get("recommendations", [])
        report.recommendations.extend(
            f"[Code Quality] {r}" for r in recs
        )

    elif agent_name == "test-auditor":
        coverage = data.get("coverage_assessment", {})
        report.findings.append({
            "severity": "info",
            "category": "test_coverage",
            "message": (
                f"Coverage: {coverage.get('estimated_coverage_pct', 'unknown')}% "
                f"({coverage.get('assessment', 'unknown')})"
            ),
        })
        for gap in coverage.get("critical_gaps", []):
            report.findings.append({
                "severity": "warning",
                "category": "test_coverage",
                "message": f"Coverage gap: {gap}",
            })

        recs = data.get("recommendations", [])
        report.recommendations.extend(
            f"[Tests] {r}" for r in recs
        )


def _merge_purposes(
    report: AssessmentReport,
    purposes: list[dict[str, Any]],
) -> None:
    """Merge purpose data into project profiles."""
    purpose_map = {p.get("name", ""): p for p in purposes}
    for project in report.projects:
        name = project.get("name", "")
        if name in purpose_map:
            project["purpose"] = purpose_map[name].get("purpose", "")
            project["purpose_confidence"] = purpose_map[name].get(
                "confidence", "low"
            )
            project["responsibilities"] = purpose_map[name].get(
                "key_responsibilities", []
            )


# ── Deduplication ─────────────────────────────────────────────────────────


def _deduplicate_findings(
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deduplicate findings by (message, file, category) key.

    Preserves the first occurrence; adds a _count field so
    signal isn't lost when multiple agents report the same finding.
    """
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    for finding in findings:
        key = (
            finding.get("message", "").strip(),
            finding.get("file", ""),
            finding.get("category", ""),
        )
        if key in seen:
            seen[key]["_count"] = seen[key].get("_count", 1) + 1
        else:
            finding["_count"] = 1
            seen[key] = finding
    return list(seen.values())


# ── Scoring ──────────────────────────────────────────────────────────────────


def _compute_overall_score(report: AssessmentReport) -> str:
    """Derive an overall score from all agent results."""
    if not report.agent_results:
        return "unknown"

    scores_map = {"excellent": 4, "good": 3, "fair": 2, "poor": 1}
    reverse_map = {v: k for k, v in scores_map.items()}

    scores: list[int] = []

    for agent_name, data in report.agent_results.items():
        status = report.agent_status.get(agent_name, "failure")
        if status != "success":
            continue

        if agent_name == "architecture-critic":
            s = data.get("score", "")
            if s in scores_map:
                scores.append(scores_map[s])

        elif agent_name == "code-critic":
            s = data.get("overall_rating", "")
            if s in scores_map:
                scores.append(scores_map[s])

        elif agent_name == "test-auditor":
            ca = data.get("coverage_assessment", {})
            s = ca.get("assessment", "")
            if s in scores_map:
                scores.append(scores_map[s])

    if not scores:
        return "unknown"

    avg_score = sum(scores) / len(scores)
    if avg_score >= 3.5:
        return "excellent"
    elif avg_score >= 2.5:
        return "good"
    elif avg_score >= 1.5:
        return "fair"
    else:
        return "poor"


# ── Report formatting ────────────────────────────────────────────────────────


def format_assessment_report(report: AssessmentReport) -> str:
    """Format an AssessmentReport as a human-readable markdown string."""
    lines: list[str] = [
        f"# Assessment: {report.path}",
        "",
    ]

    # Score banner
    score_banners = {
        "excellent": "✅ **Excellent** — well-structured codebase",
        "good": "👍 **Good** — minor improvements recommended",
        "fair": "⚠️ **Fair** — several areas need attention",
        "poor": "🔴 **Poor** — significant issues found",
        "unknown": "❓ **Unknown** — insufficient data to score",
    }
    lines.append(f"**Overall Score:** {score_banners.get(report.score, report.score)}")
    lines.append("")

    # Metrics
    lines.append("## Assessment Metrics")
    lines.append(f"- Agents run: {report.metrics.get('agents_run', 0)}")
    lines.append(f"- Succeeded: {report.metrics.get('agents_succeeded', 0)}")
    lines.append(f"- Degraded/Failed: {report.metrics.get('agents_degraded', 0)}"
                 f"/{report.metrics.get('agents_failed', 0)}")
    lines.append(f"- Duration: {report.metrics.get('duration_ms', 0)}ms")
    lines.append("")

    # Projects
    if report.projects:
        lines.append("## Projects Detected")
        lines.append("")
        for p in report.projects:
            name = p.get("name", "unknown")
            ptype = p.get("type", "unknown")
            lang = p.get("language", "unknown")
            purpose = p.get("purpose", "")
            confidence = p.get("confidence", "low") or p.get("purpose_confidence", "")
            lines.append(f"### {name}")
            lines.append(f"- **Type:** {ptype}")
            lines.append(f"- **Language:** {lang}")
            lines.append(f"- **Build:** {p.get('build_system', 'none detected')}")
            if p.get("frameworks"):
                lines.append(f"- **Frameworks:** {', '.join(p['frameworks'])}")
            if purpose:
                lines.append(f"- **Purpose:** {purpose} (confidence: {confidence})")
            if p.get("responsibilities"):
                lines.append("- **Responsibilities:**")
                for r in p["responsibilities"]:
                    lines.append(f"  - {r}")
            lines.append("")

    # Findings
    if report.findings:
        lines.append("## Findings")
        lines.append("")
        for f in report.findings:
            severity = f.get("severity", "info")
            label = severity.upper()
            file_ref = f" `{f.get('file', '')}`" if f.get("file") else ""
            lines.append(f"- **[{label}]{file_ref}** — {f.get('message', '')}")
        lines.append("")

    # Recommendations
    if report.recommendations:
        lines.append("## Recommendations")
        lines.append("")
        for r in report.recommendations:
            lines.append(f"- {r}")
        lines.append("")

    # Agent status
    lines.append("## Agent Status")
    lines.append("")
    for agent_name, status in report.agent_status.items():
        icon = {
            "success": "✅",
            "degraded": "⚠️",
            "failure": "❌",
            "skipped": "⏭️",
        }.get(status, "❓")
        lines.append(f"- {icon} **{agent_name}**: {status}")
    lines.append("")

    return "\n".join(lines)
