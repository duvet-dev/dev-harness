"""Tests for harness.domain.engagement.resolver."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from harness.domain.engagement.resolver import (
    ENG_BRANCH_PATTERN,
    load_active_engagements,
    resolve_active_engagement,
    save_active_engagements,
)


class TestEngBranchPattern:
    def test_matches_eng_slug(self):
        m = ENG_BRANCH_PATTERN.match("eng/my-feature")
        assert m is not None
        assert m.group("slug") == "my-feature"

    def test_matches_slug_with_numbers(self):
        m = ENG_BRANCH_PATTERN.match("eng/feat-123")
        assert m is not None
        assert m.group("slug") == "feat-123"

    def test_does_not_match_non_eng(self):
        assert ENG_BRANCH_PATTERN.match("feature/my-feature") is None

    def test_does_not_match_plain_branch(self):
        assert ENG_BRANCH_PATTERN.match("main") is None


class TestResolveActiveEngagement:
    def test_resolves_from_branch_name(self, tmp_path):
        with patch("harness.scm.git.GitRepo") as MockGitRepo:
            mock_repo = MagicMock()
            mock_repo.branch.return_value = "eng/my-design"
            MockGitRepo.return_value = mock_repo
            slug = resolve_active_engagement(tmp_path)
            assert slug == "my-design"

    def test_falls_back_to_mapping_file(self, tmp_path):
        mapping_dir = tmp_path / ".harness"
        mapping_dir.mkdir(parents=True)
        mapping_file = mapping_dir / "active-engagements.yaml"
        mapping_file.write_text(yaml.dump({"branches": {"main": "my-eng"}}))

        with patch("harness.scm.git.GitRepo") as MockGitRepo:
            mock_repo = MagicMock()
            mock_repo.branch.return_value = "main"
            MockGitRepo.return_value = mock_repo
            slug = resolve_active_engagement(tmp_path)
            assert slug == "my-eng"

    def test_returns_none_when_no_match(self, tmp_path):
        with patch("harness.scm.git.GitRepo") as MockGitRepo:
            mock_repo = MagicMock()
            mock_repo.branch.return_value = "other-branch"
            MockGitRepo.return_value = mock_repo
            slug = resolve_active_engagement(tmp_path)
            assert slug is None

    def test_returns_none_when_no_mapping_file(self, tmp_path):
        with patch("harness.scm.git.GitRepo") as MockGitRepo:
            mock_repo = MagicMock()
            mock_repo.branch.return_value = "main"
            MockGitRepo.return_value = mock_repo
            slug = resolve_active_engagement(tmp_path)
            assert slug is None


class TestLoadActiveEngagements:
    def test_returns_default_when_no_file(self, tmp_path):
        result = load_active_engagements(tmp_path)
        assert result == {"branches": {}}

    def test_returns_content_when_file_exists(self, tmp_path):
        mapping_dir = tmp_path / ".harness"
        mapping_dir.mkdir(parents=True)
        mapping_file = mapping_dir / "active-engagements.yaml"
        mapping_file.write_text(yaml.dump({"branches": {"main": "eng-1"}}))
        result = load_active_engagements(tmp_path)
        assert result["branches"]["main"] == "eng-1"

    def test_ensures_branches_key(self, tmp_path):
        mapping_dir = tmp_path / ".harness"
        mapping_dir.mkdir(parents=True)
        mapping_file = mapping_dir / "active-engagements.yaml"
        mapping_file.write_text(yaml.dump({"other": "data"}))
        result = load_active_engagements(tmp_path)
        assert "branches" in result


class TestSaveActiveEngagements:
    def test_writes_mapping_file(self, tmp_path):
        mapping = {"branches": {"main": "my-eng"}}
        save_active_engagements(tmp_path, mapping)
        mapping_file = tmp_path / ".harness" / "active-engagements.yaml"
        assert mapping_file.is_file()
        data = yaml.safe_load(mapping_file.read_text())
        assert data == mapping

    def test_creates_parent_directory(self, tmp_path):
        deep_path = tmp_path / "deep" / "nested"
        mapping = {"branches": {}}
        save_active_engagements(deep_path, mapping)
        assert (deep_path / ".harness" / "active-engagements.yaml").is_file()
