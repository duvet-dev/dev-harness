"""Tests for domain/resolver.py — active engagement resolver.

Uses tmp_path and mocks to avoid real filesystem/git interactions.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from harness.domain.resolver import (
    resolve_active_engagement,
    load_active_engagements,
    save_active_engagements,
    ENG_BRANCH_PATTERN,
)


# ── ENG_BRANCH_PATTERN ──────────────────────────────────────────────────────


class TestEngBranchPattern:
    def test_matches_valid_eng_branch(self):
        m = ENG_BRANCH_PATTERN.match("eng/my-slug")
        assert m is not None
        assert m.group("slug") == "my-slug"

    def test_matches_hyphenated_slug(self):
        m = ENG_BRANCH_PATTERN.match("eng/my-long-slug-123")
        assert m is not None
        assert m.group("slug") == "my-long-slug-123"

    def test_rejects_non_eng_branch(self):
        assert ENG_BRANCH_PATTERN.match("main") is None
        assert ENG_BRANCH_PATTERN.match("feature/x") is None

    def test_rejects_empty_slug(self):
        assert ENG_BRANCH_PATTERN.match("eng/") is None


# ── load_active_engagements ────────────────────────────────────────────────


class TestLoadActiveEngagements:
    def test_returns_default_if_no_file(self, tmp_path):
        result = load_active_engagements(tmp_path)
        assert result == {"branches": {}}

    def test_loads_existing_mapping(self, tmp_path):
        active_path = tmp_path / ".harness" / "active-engagements.yaml"
        active_path.parent.mkdir(parents=True, exist_ok=True)
        active_path.write_text(yaml.dump({"branches": {"main": "slug-1"}}))
        result = load_active_engagements(tmp_path)
        assert result["branches"]["main"] == "slug-1"

    def test_adds_missing_branches_key(self, tmp_path):
        active_path = tmp_path / ".harness" / "active-engagements.yaml"
        active_path.parent.mkdir(parents=True, exist_ok=True)
        active_path.write_text(yaml.dump({"some_key": "value"}))
        result = load_active_engagements(tmp_path)
        assert result["branches"] == {}


# ── save_active_engagements ────────────────────────────────────────────────


class TestSaveActiveEngagements:
    def test_saves_mapping(self, tmp_path):
        mapping = {"branches": {"dev": "slug-2"}}
        save_active_engagements(tmp_path, mapping)
        active_path = tmp_path / ".harness" / "active-engagements.yaml"
        assert active_path.exists()
        loaded = yaml.safe_load(active_path.read_text())
        assert loaded["branches"]["dev"] == "slug-2"

    def test_creates_parent_dir(self, tmp_path):
        save_active_engagements(tmp_path, {"branches": {}})
        assert (tmp_path / ".harness" / "active-engagements.yaml").exists()


# ── resolve_active_engagement ──────────────────────────────────────────────


class TestResolveActiveEngagement:
    def test_returns_slug_from_eng_branch(self, tmp_path):
        with patch("harness.scm.git.GitRepo") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.branch.return_value = "eng/my-test-slug"
            result = resolve_active_engagement(tmp_path)
            assert result == "my-test-slug"

    def test_returns_from_mapping_when_not_eng_branch(self, tmp_path):
        save_active_engagements(tmp_path, {"branches": {"main": "from-mapping"}})
        with patch("harness.scm.git.GitRepo") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.branch.return_value = "main"
            result = resolve_active_engagement(tmp_path)
            assert result == "from-mapping"

    def test_returns_none_when_not_found(self, tmp_path):
        with patch("harness.scm.git.GitRepo") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.branch.return_value = "feature/x"
            result = resolve_active_engagement(tmp_path)
            assert result is None
