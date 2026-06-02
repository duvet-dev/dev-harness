"""Tests for domain/lifecycle.py — engagement directory lifecycle.

Uses tmp_path to avoid touching real filesystem state.
"""

from __future__ import annotations

from pathlib import Path

from unittest.mock import patch

import pytest
import yaml

from harness.domain.lifecycle import (
    create_engagement_dir,
    write_engagement_metadata,
    set_active_engagement,
    close_engagement,
    slugify,
    read_active_engagement,
    _parse_engagement_md,
    _load_active_mapping,
    _save_active_mapping,
    update_active_engagement_mapping,
    engagement_dir_for,
)


# ── slugify ─────────────────────────────────────────────────────────────────


class TestSlugify:
    def test_lowercase_and_hyphens(self):
        assert slugify("Hello World") == "hello-world"

    def test_removes_special_chars(self):
        assert slugify("Hello! World? #1") == "hello-world-1"

    def test_strips_spaces(self):
        assert slugify("hello world") == "hello-world"

    def test_empty_string(self):
        assert slugify("") == ""


# ── create_engagement_dir ───────────────────────────────────────────────────


class TestCreateEngagementDir:
    def test_creates_directory_structure(self, tmp_path):
        eng_dir = create_engagement_dir(tmp_path, "test-eng")
        assert eng_dir.exists()
        assert eng_dir.is_dir()
        assert (eng_dir / "engagement.md").exists()
        assert (eng_dir / "plan.md").exists()
        assert (eng_dir / "plan.yaml").exists()
        assert (eng_dir / "waves").exists()

    def test_raises_if_exists(self, tmp_path):
        create_engagement_dir(tmp_path, "dup-eng")
        with pytest.raises(FileExistsError, match="already exists"):
            create_engagement_dir(tmp_path, "dup-eng")

    def test_plan_yaml_has_waves_list(self, tmp_path):
        eng_dir = create_engagement_dir(tmp_path, "eng-waves")
        plan_yaml = eng_dir / "plan.yaml"
        data = yaml.safe_load(plan_yaml.read_text())
        assert data == {"waves": []}

    def test_engagement_yaml_has_slug(self, tmp_path):
        eng_dir = create_engagement_dir(tmp_path, "eng-slug")
        eng_yaml = eng_dir / "engagement.yaml"
        data = yaml.safe_load(eng_yaml.read_text())
        assert data["slug"] == "eng-slug"


# ── write_engagement_metadata ───────────────────────────────────────────────


class TestWriteEngagementMetadata:
    def test_writes_markdown_and_yaml(self, tmp_path):
        eng_dir = create_engagement_dir(tmp_path, "meta-eng")
        write_engagement_metadata(
            eng_dir, "Meta Eng", "meta-eng", "main",
            session_type="greenfield",
        )
        md_content = (eng_dir / "engagement.md").read_text()
        assert "Meta Eng" in md_content
        assert "main" in md_content
        eng_yaml = yaml.safe_load((eng_dir / "engagement.yaml").read_text())
        assert eng_yaml["session_type"] == "greenfield"

    def test_allows_refactoring_suggestions(self, tmp_path):
        eng_dir = create_engagement_dir(tmp_path, "ref-eng")
        write_engagement_metadata(
            eng_dir, "Ref", "ref-eng", "main",
            allow_refactoring_suggestions=True,
        )
        eng_yaml = yaml.safe_load((eng_dir / "engagement.yaml").read_text())
        assert eng_yaml["allow_refactoring_suggestions"] is True

    def test_updates_existing_yaml(self, tmp_path):
        eng_dir = create_engagement_dir(tmp_path, "update-eng")
        eng_yaml = eng_dir / "engagement.yaml"
        eng_yaml.write_text(yaml.dump({"slug": "update-eng", "existing": "value"}))
        write_engagement_metadata(
            eng_dir, "Update", "update-eng", "main",
            session_type="refactor",
        )
        data = yaml.safe_load(eng_yaml.read_text())
        assert data["existing"] == "value"
        assert data["session_type"] == "refactor"


# ── Active engagement mapping ────────────────────────────────────────────────


class TestActiveEngagementMapping:
    def test_set_active_engagement_creates_mapping(self, tmp_path):
        create_engagement_dir(tmp_path, "active-eng")
        with patch("harness.scm.git.GitRepo") as MockGit:
            mock_repo = MockGit.return_value
            mock_repo.branch.return_value = "main"
            set_active_engagement(tmp_path, "active-eng")
        mapping = _load_active_mapping(tmp_path)
        assert "branches" in mapping
        assert mapping["branches"]["main"] == "active-eng"

    def test_set_active_raises_if_not_found(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            with patch("harness.scm.git.GitRepo") as MockGit:
                MockGit.return_value.branch.return_value = "main"
                set_active_engagement(tmp_path, "nonexistent")

    def test_read_active_returns_none_no_git(self, tmp_path):
        """Without a git repo, read_active returns None gracefully."""
        result = read_active_engagement(tmp_path)
        assert result is None  # no GitRepo available -> returns None from except Exception

    def test_update_active_engagement_mapping(self, tmp_path):
        mapping = {"branches": {"main": "old-slug"}}
        _save_active_mapping(tmp_path, mapping)
        update_active_engagement_mapping(tmp_path, "old-slug", "new-slug")
        updated = _load_active_mapping(tmp_path)
        assert updated["branches"]["main"] == "new-slug"

    def test_update_noop_for_unknown_slug(self, tmp_path):
        mapping = {"branches": {"main": "slug"}}
        _save_active_mapping(tmp_path, mapping)
        update_active_engagement_mapping(tmp_path, "nope", "new-nope")
        updated = _load_active_mapping(tmp_path)
        assert updated["branches"]["main"] == "slug"


# ── close_engagement ────────────────────────────────────────────────────────


class TestCloseEngagement:
    def test_close_sets_status_completed(self, tmp_path):
        create_engagement_dir(tmp_path, "close-eng")
        with patch("harness.scm.git.GitRepo") as MockGit:
            MockGit.return_value.branch.return_value = "main"
            set_active_engagement(tmp_path, "close-eng")
            metadata = close_engagement(tmp_path, "close-eng")
        assert metadata["status"] == "completed"
        assert "completed_at" in metadata

    def test_close_removes_from_active(self, tmp_path):
        create_engagement_dir(tmp_path, "close-eng")
        with patch("harness.scm.git.GitRepo") as MockGit:
            MockGit.return_value.branch.return_value = "main"
            set_active_engagement(tmp_path, "close-eng")
            close_engagement(tmp_path, "close-eng")
        mapping = _load_active_mapping(tmp_path)
        assert "close-eng" not in mapping.get("branches", {}).values()

    def test_close_raises_if_not_found(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            with patch("harness.scm.git.GitRepo") as MockGit:
                close_engagement(tmp_path, "nonexistent")


# ── _parse_engagement_md ────────────────────────────────────────────────────


class TestParseEngagementMd:
    def test_parses_frontmatter(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("---\ntitle: Test\nslug: test\n---\n\n# Test\n")
        result = _parse_engagement_md(md_file)
        assert result["title"] == "Test"
        assert result["slug"] == "test"

    def test_returns_empty_on_no_frontmatter(self, tmp_path):
        md_file = tmp_path / "plain.md"
        md_file.write_text("# Just a heading\n")
        result = _parse_engagement_md(md_file)
        assert result == {}

    def test_returns_empty_on_malformed(self, tmp_path):
        md_file = tmp_path / "bad.md"
        md_file.write_text("---\nnot: : valid: yaml\n---\n")
        result = _parse_engagement_md(md_file)
        assert result == {}


# ── engagement_dir_for ──────────────────────────────────────────────────────


class TestEngagementDirFor:
    def test_returns_expected_path(self, tmp_path):
        result = engagement_dir_for(tmp_path, "my-eng")
        assert ".harness/engagements/my-eng" in str(result)


# ── _load_active_mapping / _save_active_mapping ─────────────────────────────


class TestActiveMappingIO:
    def test_load_empty(self, tmp_path):
        mapping = _load_active_mapping(tmp_path)
        assert mapping == {"branches": {}}

    def test_save_and_load(self, tmp_path):
        _save_active_mapping(tmp_path, {"branches": {"dev": "slug-1"}})
        mapping = _load_active_mapping(tmp_path)
        assert mapping["branches"]["dev"] == "slug-1"

    def test_load_fixes_missing_branches(self, tmp_path):
        active_path = tmp_path / ".harness" / "active-engagements.yaml"
        active_path.parent.mkdir(parents=True, exist_ok=True)
        active_path.write_text(yaml.dump({"some_other_key": "value"}))
        mapping = _load_active_mapping(tmp_path)
        assert mapping["branches"] == {}
