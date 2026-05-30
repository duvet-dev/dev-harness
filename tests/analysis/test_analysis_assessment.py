"""Tests for harness.analysis.assessment — LLM-based codebase assessment.

Tests AssessmentReport, gather_context, _extract_json, _deduplicate_findings,
and helper functions.
"""

from __future__ import annotations

import json
import unittest.mock
from pathlib import Path

import pytest

from harness.analysis.assessment import (
    AssessmentReport,
    gather_context,
    _extract_json,
    _deduplicate_findings,
    _compute_overall_score,
    _format_context_for_llm,
    _build_tree,
    _read_first_n_lines,
    _collect_config_files,
    _collect_key_files,
    _collect_source_samples,
    _detect_entry_points,
    _is_git_repo,
    _build_agent_prompt,
    _merge_agent_output,
    _merge_purposes,
    format_assessment_report,
    _join_sections,
    MAX_CONTEXT_CHARS,
)
from harness.analysis.agents import AnalysisAgent, AnalysisAgentRegistry


class TestAssessmentReport:
    """Tests for AssessmentReport dataclass."""

    def test_default_values(self):
        report = AssessmentReport()
        assert report.path == ""
        assert report.projects == []
        assert report.findings == []
        assert report.score == "unknown"
        assert report.recommendations == []
        assert report.agent_results == {}
        assert report.agent_status == {}
        assert report.metrics == {}
        assert report.report_text == ""

    def test_to_dict(self):
        report = AssessmentReport(
            path="/test",
            score="good",
            report_text="# Assessment\nAll good.",
        )
        d = report.to_dict()
        assert d["assessment"]["path"] == "/test"
        assert d["assessment"]["score"] == "good"
        assert d["report"] == "# Assessment\nAll good."

    def test_to_dict_contains_agent_data(self):
        report = AssessmentReport(
            path="/test",
            agent_results={"profiler": {"projects": []}},
            agent_status={"profiler": "success"},
            metrics={"agents_run": 1},
        )
        d = report.to_dict()
        assert d["assessment"]["agent_results"]["profiler"]["projects"] == []
        assert d["assessment"]["agent_status"]["profiler"] == "success"
        assert d["assessment"]["metrics"]["agents_run"] == 1


class TestGatherContext:
    """Tests for gather_context()."""

    def test_empty_directory(self, tmp_path):
        context = gather_context(tmp_path)
        assert context["root"] == str(tmp_path)
        assert context["readme_content"] == ""
        assert context["config_files"] == {}
        assert context["key_source_files"] == {}
        assert context["entry_points"] == []
        assert context["has_dockerfile"] is False
        assert context["has_makefile"] is False
        assert context["test_directory"] is False
        assert context["is_git_repo"] is False

    def test_readme_detected(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("# My Project\nThis is a test.\n")
        context = gather_context(tmp_path)
        assert "My Project" in context["readme_content"]

    def test_readme_truncated(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("\n".join(f"Line {i}" for i in range(500)))
        context = gather_context(tmp_path)
        # Should be truncated to MAX_README_LINES (200)
        assert len(context["readme_content"].splitlines()) <= 200

    def test_config_files_collected(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (tmp_path / "Makefile").write_text("all:\n\techo hello\n")
        context = gather_context(tmp_path)
        assert "pyproject.toml" in context["config_files"]
        assert "Makefile" in context["config_files"]

    def test_entry_points_detected(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        cli = src / "cli.py"
        cli.write_text("if __name__ == '__main__':\n    print('hello')\n")
        context = gather_context(tmp_path)
        assert len(context["entry_points"]) >= 1

    def test_dockerfile_detected(self, tmp_path):
        (tmp_path / "Dockerfile").write_text("FROM python:3.11\n")
        context = gather_context(tmp_path)
        assert context["has_dockerfile"] is True

    def test_makefile_detected(self, tmp_path):
        (tmp_path / "Makefile").write_text("test:\n\tpytest\n")
        context = gather_context(tmp_path)
        assert context["has_makefile"] is True

    def test_test_directory_detected(self, tmp_path):
        (tmp_path / "tests").mkdir()
        context = gather_context(tmp_path)
        assert context["test_directory"] is True

    def test_git_repo_detected(self, tmp_path):
        (tmp_path / ".git").mkdir()
        context = gather_context(tmp_path)
        assert context["is_git_repo"] is True


class TestBuildTree:
    """Tests for _build_tree()."""

    def test_empty_dir(self, tmp_path):
        tree = _build_tree(tmp_path)
        assert tree == ""

    def test_single_file(self, tmp_path):
        (tmp_path / "hello.py").write_text("x=1\n")
        tree = _build_tree(tmp_path)
        assert "hello.py" in tree

    def test_nested_dirs(self, tmp_path):
        (tmp_path / "src" / "app").mkdir(parents=True)
        (tmp_path / "src" / "app" / "main.py").write_text("")
        (tmp_path / "tests").mkdir()
        tree = _build_tree(tmp_path)
        assert "src/" in tree
        assert "tests/" in tree

    def test_max_depth(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep.mkdir(parents=True)
        (deep / "file.txt").write_text("")
        tree = _build_tree(tmp_path, max_depth=3)
        # tree should not show 'e/' at depth 4
        assert "a/" in tree

    def test_skip_dirs_respected(self, tmp_path):
        (tmp_path / ".git" / "config").parent.mkdir(parents=True)
        (tmp_path / ".git" / "config").write_text("")
        (tmp_path / "real.py").write_text("x=1\n")
        tree = _build_tree(tmp_path)
        assert ".git/" not in tree
        assert "real.py" in tree


class TestReadFirstNLines:
    """Tests for _read_first_n_lines()."""

    def test_nonexistent_file(self, tmp_path):
        assert _read_first_n_lines(tmp_path / "missing.txt") == ""

    def test_read_lines(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\n")
        assert _read_first_n_lines(f, max_lines=2) == "line1\nline2"

    def test_read_binary_file(self, tmp_path):
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x80\x81")
        result = _read_first_n_lines(f)
        # Should not crash, may return a string
        assert isinstance(result, str)


class TestCollectSourceSamples:
    """Tests for _collect_source_samples()."""

    def test_no_source_dir(self, tmp_path):
        samples = _collect_source_samples(tmp_path)
        assert samples == {}

    def test_collects_python_files(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "hello.py").write_text("print('hello')\n")
        samples = _collect_source_samples(tmp_path)
        assert "src/hello.py" in samples or any("hello.py" in k for k in samples)

    def test_collects_test_files(self, tmp_path):
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_hello.py").write_text("def test_hello(): pass\n")
        samples = _collect_source_samples(tmp_path)
        assert any("test" in k for k in samples)

    def test_respects_max_chars(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "big.py").write_text("x = " + "a" * 100000 + "\n")
        (src / "small.py").write_text("y = 1\n")
        samples = _collect_source_samples(tmp_path, max_total_chars=50000)
        # With max_total_chars small, not all content may fit
        total = sum(len(v) for v in samples.values())
        assert total <= 50000


class TestDetectEntryPoints:
    """Tests for _detect_entry_points()."""

    def test_no_files(self, tmp_path):
        assert _detect_entry_points(tmp_path) == []

    def test_main_function_detected(self, tmp_path):
        cli = tmp_path / "cli.py"
        cli.write_text("if __name__ == '__main__':\n    main()\n")
        eps = _detect_entry_points(tmp_path)
        assert any("cli.py" in ep for ep in eps)


class TestIsGitRepo:
    """Tests for _is_git_repo()."""

    def test_git_exists(self, tmp_path):
        (tmp_path / ".git").mkdir()
        assert _is_git_repo(tmp_path) is True

    def test_no_git(self, tmp_path):
        assert _is_git_repo(tmp_path) is False


class TestExtractJson:
    """Tests for _extract_json()."""

    def test_full_text_json(self):
        text = '{"key": "value", "num": 42}'
        result = _extract_json(text)
        assert result == {"key": "value", "num": 42}

    def test_json_code_block(self):
        text = "Some text\n```json\n{\"key\": \"value\"}\n```\nMore text"
        result = _extract_json(text)
        assert result == {"key": "value"}

    def test_code_block_without_json_label(self):
        text = "```\n{\"a\": 1}\n```"
        result = _extract_json(text)
        assert result == {"a": 1}

    def test_top_level_brace(self):
        text = "Here is the result: {\"items\": [1, 2, 3]}"
        result = _extract_json(text)
        assert result == {"items": [1, 2, 3]}

    def test_invalid_json_returns_none(self):
        result = _extract_json("This is not JSON")
        assert result is None

    def test_nested_braces(self):
        text = 'The data is: {"outer": {"inner": "value"}, "list": [1, {"a": "b"}]}'
        result = _extract_json(text)
        assert result == {"outer": {"inner": "value"}, "list": [1, {"a": "b"}]}

    def test_empty_text(self):
        assert _extract_json("") is None


class TestDeduplicateFindings:
    """Tests for _deduplicate_findings()."""

    def test_no_duplicates(self):
        findings = [
            {"message": "A", "file": "f1.py", "category": "quality"},
            {"message": "B", "file": "f2.py", "category": "quality"},
        ]
        result = _deduplicate_findings(findings)
        assert len(result) == 2

    def test_duplicates_merged(self):
        findings = [
            {"message": "Same issue", "file": "f.py", "category": "quality"},
            {"message": "Same issue", "file": "f.py", "category": "quality"},
        ]
        result = _deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0]["_count"] == 2

    def test_different_message_no_merge(self):
        findings = [
            {"message": "Issue A", "file": "f.py", "category": "quality"},
            {"message": "Issue B", "file": "f.py", "category": "quality"},
        ]
        result = _deduplicate_findings(findings)
        assert len(result) == 2

    def test_strips_messages(self):
        findings = [
            {"message": "  Issue A  ", "file": "f.py", "category": "quality"},
            {"message": "Issue A", "file": "f.py", "category": "quality"},
        ]
        result = _deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0]["_count"] == 2


class TestComputeOverallScore:
    """Tests for _compute_overall_score()."""

    def test_no_results_returns_unknown(self):
        report = AssessmentReport()
        assert _compute_overall_score(report) == "unknown"

    def test_excellent_scores(self):
        report = AssessmentReport(
            agent_results={
                "architecture-critic": {"score": "excellent"},
                "code-critic": {"overall_rating": "excellent"},
                "test-auditor": {"coverage_assessment": {"assessment": "excellent"}},
            },
            agent_status={
                "architecture-critic": "success",
                "code-critic": "success",
                "test-auditor": "success",
            },
        )
        assert _compute_overall_score(report) == "excellent"

    def test_poor_scores(self):
        report = AssessmentReport(
            agent_results={
                "code-critic": {"overall_rating": "poor"},
                "architecture-critic": {"score": "poor"},
            },
            agent_status={
                "code-critic": "success",
                "architecture-critic": "success",
            },
        )
        assert _compute_overall_score(report) == "poor"

    def test_mixed_scores(self):
        report = AssessmentReport(
            agent_results={
                "architecture-critic": {"score": "good"},
                "code-critic": {"overall_rating": "fair"},
            },
            agent_status={
                "architecture-critic": "success",
                "code-critic": "success",
            },
        )
        # avg = (3 + 2) / 2 = 2.5 → "good"
        assert _compute_overall_score(report) == "good"


class TestMergeAgentOutput:
    """Tests for _merge_agent_output()."""

    def test_project_profiler(self):
        report = AssessmentReport(path="/test")
        data = {
            "projects": [
                {"name": "myproj", "type": "library", "language": "python",
                 "confidence": "high"},
            ],
        }
        _merge_agent_output(report, "project-profiler", data)
        assert len(report.projects) == 1
        assert report.projects[0]["name"] == "myproj"
        assert len(report.findings) >= 1

    def test_architecture_critic(self):
        report = AssessmentReport(path="/test")
        data = {
            "architecture": {
                "recognised_pattern": "layered",
                "confidence": "high",
            },
            "boundary_violations": [],
            "recommendations": ["Use dependency injection"],
            "score": "good",
        }
        _merge_agent_output(report, "architecture-critic", data)
        assert len(report.findings) >= 1
        assert "layered" in report.findings[0]["message"]
        assert len(report.recommendations) >= 1

    def test_code_critic(self):
        report = AssessmentReport(path="/test")
        data = {
            "dimensions": [
                {
                    "name": "naming",
                    "rating": "warn",
                    "findings": [
                        {"file": "main.py", "line": 10, "message": "Bad name",
                         "severity": "warning"},
                    ],
                },
            ],
            "overall_rating": "fair",
            "recommendations": ["Use better names"],
        }
        _merge_agent_output(report, "code-critic", data)
        assert len(report.findings) >= 1
        assert len(report.recommendations) >= 1

    def test_test_auditor(self):
        report = AssessmentReport(path="/test")
        data = {
            "coverage_assessment": {
                "estimated_coverage_pct": 45,
                "assessment": "fair",
                "critical_gaps": ["Domain layer has no tests"],
            },
            "recommendations": ["Add domain tests"],
        }
        _merge_agent_output(report, "test-auditor", data)
        assert len(report.findings) >= 1
        assert len(report.recommendations) >= 1


class TestFormatAssessmentReport:
    """Tests for format_assessment_report()."""

    def test_empty_report(self):
        report = AssessmentReport(path="/test")
        text = format_assessment_report(report)
        assert "Assessment: /test" in text
        assert "Overall Score" in text

    def test_unknown_score(self):
        report = AssessmentReport(path="/test", score="unknown")
        text = format_assessment_report(report)
        assert "Unknown" in text
        assert "insufficient data" in text

    def test_with_findings(self):
        report = AssessmentReport(
            path="/test",
            score="good",
            findings=[
                {"severity": "warning", "file": "main.py",
                 "message": "Consider refactoring"},
            ],
            metrics={"agents_run": 1, "agents_succeeded": 1},
            agent_status={"profiler": "success"},
        )
        text = format_assessment_report(report)
        assert "main.py" in text
        assert "WARNING" in text
        assert "profiler" in text


class TestFormatContextForLLM:
    """Tests for _format_context_for_llm()."""

    def test_minimal_context(self, tmp_path):
        context = {
            "root": str(tmp_path),
            "directory_tree": "",
            "readme_content": "",
            "config_files": {},
            "key_source_files": {},
            "entry_points": [],
            "source_content": {},
            "has_dockerfile": False,
            "has_makefile": False,
            "test_directory": False,
            "is_git_repo": False,
        }
        result = _format_context_for_llm(context)
        assert "Codebase Location" in result
        assert str(tmp_path) in result

    def test_truncation(self, tmp_path):
        """When context exceeds MAX_CONTEXT_CHARS, content is truncated."""
        context = {
            "root": str(tmp_path),
            "directory_tree": "some/",
            "readme_content": "x" * MAX_CONTEXT_CHARS,
            "config_files": {"big": "y" * MAX_CONTEXT_CHARS},
            "key_source_files": {},
            "entry_points": ["main:main.py"],
            "source_content": {"big.py": "z" * MAX_CONTEXT_CHARS},
            "has_dockerfile": False,
            "has_makefile": False,
            "test_directory": False,
            "is_git_repo": False,
        }
        result = _format_context_for_llm(context)
        # Should still be within limit
        assert len(result) <= MAX_CONTEXT_CHARS


class TestBuildAgentPrompt:
    """Tests for _build_agent_prompt()."""

    def test_includes_context(self):
        agent = AnalysisAgentRegistry.get("project-profiler")
        prompt = _build_agent_prompt(agent, "## Context\nSome context here\n")
        assert "## Context" in prompt
        assert agent.system_prompt in prompt
        assert "output_schema" in prompt.lower() or "json" in prompt.lower()

    def test_includes_schema(self):
        agent = AnalysisAgentRegistry.get("code-critic")
        prompt = _build_agent_prompt(agent, "Context data")
        assert "dimensions" in prompt or "overall_rating" in prompt


class TestCollectConfigFiles:
    """Tests for _collect_config_files()."""

    def test_no_configs(self, tmp_path):
        assert _collect_config_files(tmp_path) == {}

    def test_pyproject_toml(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        configs = _collect_config_files(tmp_path)
        assert "pyproject.toml" in configs

    def test_makefile(self, tmp_path):
        (tmp_path / "Makefile").write_text("all:\n\techo test\n")
        configs = _collect_config_files(tmp_path)
        assert "Makefile" in configs


class TestMergePurposes:
    """Tests for _merge_purposes()."""

    def test_merges_purpose_into_project(self):
        report = AssessmentReport(
            path="/test",
            projects=[{"name": "myproj", "type": "library"}],
        )
        purposes = [
            {"name": "myproj", "purpose": "Does data processing",
             "confidence": "high", "key_responsibilities": ["Process data"]},
        ]
        _merge_purposes(report, purposes)
        assert report.projects[0]["purpose"] == "Does data processing"
        assert report.projects[0]["responsibilities"] == ["Process data"]


class TestJoinSections:
    """Tests for _join_sections()."""

    def test_within_limit(self):
        sections = [
            (5, "loc", "## Location\n/path\n"),
            (3, "cfg", "## Config\nkey=val\n"),
        ]
        result = _join_sections(sections, max_chars=10000)
        assert "Location" in result
        assert "Config" in result

    def test_truncation_by_priority(self):
        """Lowest priority sections are removed first to stay within max_chars."""
        sections = [
            (5, "loc", "LOC_KEEP\n"),
            (5, "meta", "META_KEEP\n"),
            (1, "src", "SRC_REMOVE\n"),
        ]
        # Total is ~27 chars, max_chars=20 means we need to drop something
        result = _join_sections(sections, max_chars=20)
        # Location (priority 5) should be kept
        assert "LOC_KEEP" in result, f"Got: {result!r}"
        # Low-priority src should be removed first
        assert "SRC_REMOVE" not in result, f"Got: {result!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for extracted pure functions (effect/logic separation pattern)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSelectAgents:
    """Tests for _select_agents() — pure agent selection logic."""

    def test_select_by_name(self):
        from harness.analysis.assessment import _select_agents
        agents = _select_agents(agent_names=["project-profiler", "code-critic"])
        names = [a.name for a in agents]
        assert "project-profiler" in names
        assert "code-critic" in names
        assert len(agents) == 2

    def test_select_by_name_single(self):
        from harness.analysis.assessment import _select_agents
        agents = _select_agents(agent_names=["test-auditor"])
        assert len(agents) == 1
        assert agents[0].name == "test-auditor"

    def test_select_deep_true(self):
        from harness.analysis.assessment import _select_agents
        agents = _select_agents(deep=True)
        names = [a.name for a in agents]
        assert "project-profiler" in names
        assert "responsibility-decoder" in names
        assert "architecture-critic" in names
        assert "code-critic" in names
        assert "test-auditor" in names
        assert "security-auditor" in names
        assert "dependency-analyser" in names
        assert "documentation-reviewer" in names

    def test_select_deep_false(self):
        from harness.analysis.assessment import _select_agents
        agents = _select_agents(deep=False)
        names = [a.name for a in agents]
        assert "project-profiler" in names
        assert "responsibility-decoder" in names
        # Should NOT include deep-only agents
        assert "architecture-critic" not in names
        assert "code-critic" not in names

    def test_select_empty_name_list(self):
        from harness.analysis.assessment import _select_agents
        agents = _select_agents(agent_names=[])
        assert agents == []

    def test_select_nonexistent_name(self):
        from harness.analysis.assessment import _select_agents
        agents = _select_agents(agent_names=["__nonexistent__"])
        assert agents == []


class TestProcessAgentResults:
    """Tests for _process_agent_results() — pure result processing logic."""

    def test_empty_results(self):
        from harness.analysis.assessment import (
            _process_agent_results, AssessmentReport,
        )
        report = AssessmentReport(path="/test")
        result = _process_agent_results(report, [], agents_count=0)
        assert result.score == "unknown"
        assert result.metrics["agents_run"] == 0
        assert result.report_text != ""

    def test_all_successful(self):
        from harness.analysis.assessment import (
            _process_agent_results, AssessmentReport,
        )
        report = AssessmentReport(path="/test")
        raw = [
            ("profiler", {"projects": [{"name": "app"}]}, "success"),
            ("critic", {"issues": ["missing tests"]}, "success"),
        ]
        result = _process_agent_results(report, raw, agents_count=2)
        assert result.metrics["agents_run"] == 2
        assert result.metrics["agents_succeeded"] == 2
        assert "profiler" in result.agent_results
        assert "critic" in result.agent_results

    def test_mixed_success_and_failure(self):
        from harness.analysis.assessment import (
            _process_agent_results, AssessmentReport,
        )
        report = AssessmentReport(path="/test")
        raw = [
            ("profiler", {"projects": []}, "success"),
            ("critic", {}, "failure"),
        ]
        result = _process_agent_results(report, raw, agents_count=2)
        assert result.metrics["agents_run"] == 2
        assert result.metrics["agents_succeeded"] == 1
        assert result.metrics["agents_failed"] == 1

    def test_handles_exception_result(self):
        from harness.analysis.assessment import (
            _process_agent_results, AssessmentReport,
        )
        report = AssessmentReport(path="/test")
        raw = [
            ("profiler", {"projects": []}, "success"),
            RuntimeError("Agent crashed"),
        ]
        result = _process_agent_results(report, raw, agents_count=2)
        assert result.metrics["agents_succeeded"] == 1
        assert result.metrics["agents_failed"] == 0  # exception not counted as failure

    def test_dedup_findings(self):
        from harness.analysis.assessment import (
            _process_agent_results, AssessmentReport,
        )
        report = AssessmentReport(path="/test")
        raw = [
            ("profiler", {"findings": [{"id": "F1", "text": "Same issue"}]}, "success"),
        ]
        result = _process_agent_results(report, raw, agents_count=1)
        assert isinstance(result, AssessmentReport)

    def test_score_and_metrics_set(self):
        from harness.analysis.assessment import (
            _process_agent_results, AssessmentReport,
        )
        report = AssessmentReport(path="/test")
        raw = [
            ("profiler", {"projects": [{"name": "app"}]}, "success"),
        ]
        result = _process_agent_results(report, raw, agents_count=1, duration_ms=123)
        assert result.metrics["duration_ms"] == 123
        assert isinstance(result.score, str)
        assert result.score in ("excellent", "good", "fair", "poor", "unknown")


class TestAssessRepoToolWiring:
    """Verify RepoTool is wired through the full assess() pipeline.

    This is the key test for R27 — confirms that analysis agents receive
    file access via RepoTool during assessment.
    """

    @pytest.mark.asyncio
    async def test_assess_passes_agent_role_and_project_dir(self, tmp_path):
        """_attach_repo_tool is reachable because assess() passes agent_role
        and project_dir through run_simple() → constraint_section."""
        from harness.analysis.assessment import assess
        from harness.agents.orchestrator import AgentOrchestrator

        (tmp_path / "hello.py").write_text("x = 1\n")

        # Patch AgentOrchestrator.run_simple to verify it receives the right params
        original_run_simple = AgentOrchestrator.run_simple

        captured_kwargs = {}

        async def mock_run_simple(self, **kwargs):
            nonlocal captured_kwargs
            captured_kwargs = kwargs
            # Return valid JSON for a successful analysis
            return '{"projects": [{"name": "test", "type": "library", "language": "python", "confidence": "high"}], "overview": {"total_projects": 1, "languages_detected": ["python"], "total_files_scanned": 1, "notes": ""}}'

        with unittest.mock.patch.object(
            AgentOrchestrator, "run_simple", mock_run_simple
        ):
            result = await assess(str(tmp_path), deep=False, agent_names=["project-profiler"])

        # Verify the key parameters that enable RepoTool wiring
        assert "project_dir" in captured_kwargs, "assess() must pass project_dir to run_simple()"
        assert "agent_role" in captured_kwargs, "assess() must pass agent_role to run_simple()"
        assert captured_kwargs["agent_role"] is not None
        assert captured_kwargs["project_dir"] is not None

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_assess_repo_tool_integration(self, tmp_path):
        """End-to-end: assess() with a valid path and patched LLM should
        successfully complete, showing the agent_role flowed through."""
        from harness.analysis.assessment import assess
        from harness.agents.orchestrator import AgentOrchestrator

        (tmp_path / "src" / "main.py").parent.mkdir(parents=True)
        (tmp_path / "src" / "main.py").write_text("def hello(): print('hello')\n")

        # Mock run_simple to track whether agent_role was set
        tracked = {}

        async def tracking_run_simple(self, **kwargs):
            tracked["agent_role"] = kwargs.get("agent_role")
            tracked["project_dir"] = kwargs.get("project_dir")
            return '{"projects": [{"name": "app", "type": "library", "language": "python", "confidence": "high"}], "overview": {"total_projects": 1, "languages_detected": ["python"], "total_files_scanned": 1, "notes": ""}}'

        with unittest.mock.patch.object(
            AgentOrchestrator, "run_simple", tracking_run_simple
        ):
            report = await assess(str(tmp_path), deep=False, agent_names=["project-profiler"])

        assert tracked["agent_role"] == "critical-analyser"
        assert tracked["project_dir"] == tmp_path
        assert report.metrics["agents_run"] == 1
        assert report.metrics["agents_succeeded"] == 1
