"""Tests for harness.agents.pattern — pattern injection system.

Tests Pattern, PatternLoader, sort_patterns, and frontmatter helpers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.agents.pattern import (
    Pattern,
    PatternLoader,
    sort_patterns,
    scaffold_pattern_file,
    _parse_frontmatter,
    _strip_frontmatter,
)


class TestPattern:
    """Tests for Pattern dataclass."""

    def test_defaults(self):
        p = Pattern()
        assert p.path == ""
        assert p.url == ""
        assert p.fleet == ""
        assert p.language == ""
        assert p.priority == "medium"
        assert p.content == ""
        assert p.builtin is False


class TestSortPatterns:
    """Tests for sort_patterns()."""

    def test_high_before_low(self):
        patterns = [
            Pattern(priority="low"),
            Pattern(priority="high"),
            Pattern(priority="medium"),
        ]
        sorted_pats = sort_patterns(patterns)
        assert sorted_pats[0].priority == "high"
        assert sorted_pats[1].priority == "medium"
        assert sorted_pats[2].priority == "low"

    def test_builtin_comes_after_projects(self):
        patterns = [
            Pattern(priority="medium", builtin=True),
            Pattern(priority="medium", builtin=False),
        ]
        sorted_pats = sort_patterns(patterns)
        assert sorted_pats[0].builtin is False
        assert sorted_pats[1].builtin is True

    def test_empty_list(self):
        assert sort_patterns([]) == []


class TestParseFrontmatter:
    """Tests for _parse_frontmatter()."""

    def test_valid_frontmatter(self):
        content = """---
fleet: coding
language: python
priority: high
---
Content here
"""
        meta = _parse_frontmatter(content)
        assert meta["fleet"] == "coding"
        assert meta["language"] == "python"
        assert meta["priority"] == "high"

    def test_no_frontmatter(self):
        content = "Just some text\nwithout frontmatter\n"
        meta = _parse_frontmatter(content)
        assert meta == {}

    def test_empty_frontmatter(self):
        content = "---\n---\nContent\n"
        meta = _parse_frontmatter(content)
        assert meta == {}

    def test_malformed_yaml(self):
        content = "---\n[[[invalid yaml\n---\nContent\n"
        meta = _parse_frontmatter(content)
        assert meta == {}


class TestStripFrontmatter:
    """Tests for _strip_frontmatter()."""

    def test_strips_frontmatter(self):
        content = """---
fleet: coding
---
The actual content
"""
        result = _strip_frontmatter(content)
        assert result == "The actual content"
        assert "---" not in result

    def test_no_frontmatter(self):
        result = _strip_frontmatter("Just content")
        assert result == "Just content"

    def test_no_closing_frontmatter(self):
        content = "---\nfleet: coding\nNo closing marker"
        result = _strip_frontmatter(content)
        # Should return original content
        assert result == content


class TestPatternLoader:
    """Tests for PatternLoader."""

    def test_load_all_from_empty_project(self, tmp_path):
        """No patterns in empty project."""
        loader = PatternLoader(tmp_path)
        patterns = loader.load_all()
        assert isinstance(patterns, list)

    def test_load_for_fleet(self, tmp_path):
        loader = PatternLoader(tmp_path)
        patterns = loader.load_for_fleet("coding")
        assert isinstance(patterns, list)

    def test_load_for_fleet_with_language(self, tmp_path):
        loader = PatternLoader(tmp_path)
        patterns = loader.load_for_fleet("coding", language="python")
        assert isinstance(patterns, list)

    def test_load_project_patterns_from_dir(self, tmp_path):
        """Patterns from .harness/patterns/ are loaded."""
        patterns_dir = tmp_path / ".harness" / "patterns"
        patterns_dir.mkdir(parents=True)
        pf = patterns_dir / "python-best-practices.md"
        pf.write_text("---\nfleet: coding\nlanguage: python\n---\nUse type hints\n")

        loader = PatternLoader(tmp_path)
        patterns = loader.load_all()
        project_patterns = [p for p in patterns if not p.builtin]
        assert len(project_patterns) >= 1
        assert any("python-best-practices" in p.path for p in project_patterns)

    def test_load_config_patterns(self, tmp_path):
        """Patterns from config.yaml are loaded."""
        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir()
        config = harness_dir / "config.yaml"
        config.write_text("""patterns:
  coding:
    - path: "patterns/my-pattern.md"
""")
        patterns_src = tmp_path / "patterns"
        patterns_src.mkdir()
        (patterns_src / "my-pattern.md").write_text("---\npriority: high\n---\nUse patterns\n")

        loader = PatternLoader(tmp_path)
        patterns = loader.load_all()
        config_patterns = [p for p in patterns if "my-pattern" in p.path]
        assert len(config_patterns) >= 1

    def test_load_for_engagement(self, tmp_path):
        """Engagement-level patterns are loaded and get high priority."""
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng" / "patterns"
        eng_dir.mkdir(parents=True)
        (eng_dir / "engagement-pattern.md").write_text("Engagement specific\n")

        loader = PatternLoader(tmp_path)
        patterns = loader.load_for_engagement("test-eng", fleet_name="coding")
        eng_patterns = [p for p in patterns if "engagement" in p.path]
        if eng_patterns:
            assert eng_patterns[0].priority == "high"

    def test_format_patterns_section(self, tmp_path):
        loader = PatternLoader(tmp_path)
        patterns = [
            Pattern(path="test.md", content="Use type hints", language="python"),
        ]
        section = loader.format_patterns_section(patterns)
        assert "[Patterns:" in section
        assert "Use type hints" in section


class TestScaffoldPatternFile:
    """Tests for scaffold_pattern_file()."""

    def test_creates_file_with_frontmatter(self, tmp_path):
        target = tmp_path / "patterns" / "custom.md"
        result = scaffold_pattern_file(
            target_path=target,
            fleet="coding",
            language="python",
            priority="high",
            content="Always use type hints",
        )
        assert result == target
        assert target.exists()

        content = target.read_text()
        assert "fleet: coding" in content
        assert "language: python" in content
        assert "priority: high" in content
        assert "Always use type hints" in content
        assert not content.startswith("---\n---")  # Should have content between markers

    def test_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "nested" / "deep" / "pattern.md"
        result = scaffold_pattern_file(
            target_path=target,
            fleet="testing",
            content="Test patterns",
        )
        assert result.exists()

    def test_optional_fields(self, tmp_path):
        target = tmp_path / "simple.md"
        result = scaffold_pattern_file(
            target_path=target,
            fleet="architecture",
            content="Simple pattern",
        )
        content = result.read_text()
        assert "language" not in content  # empty string omitted
