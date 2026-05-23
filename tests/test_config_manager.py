"""Tests for harness.config.manager."""

from pathlib import Path

import pytest
import yaml

from harness.config.manager import (
    HarnessConfigManager,
    allow_refactoring_suggestions,
    ensure_project_config,
    load_project_config,
)


class TestHarnessConfigManager:
    def test_default_refactoring(self, tmp_path):
        mgr = HarnessConfigManager(tmp_path)
        assert mgr.allow_refactoring_suggestions() is True

    def test_project_config_refactoring_false(self, tmp_path):
        config_dir = tmp_path / ".harness"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"allow_refactoring_suggestions": False}, f)

        mgr = HarnessConfigManager(tmp_path)
        assert mgr.allow_refactoring_suggestions() is False

    def test_project_config_refactoring_true(self, tmp_path):
        config_dir = tmp_path / ".harness"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"allow_refactoring_suggestions": True}, f)

        mgr = HarnessConfigManager(tmp_path)
        assert mgr.allow_refactoring_suggestions() is True

    def test_engagement_override_true_when_project_false(self, tmp_path):
        # Project says False
        config_dir = tmp_path / ".harness"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"allow_refactoring_suggestions": False}, f)

        # Engagement says True
        eng_dir = config_dir / "engagements" / "my-slug"
        eng_dir.mkdir(parents=True)
        eng_file = eng_dir / "engagement.yaml"
        with open(eng_file, "w") as f:
            yaml.dump({"allow_refactoring_suggestions": True}, f)

        mgr = HarnessConfigManager(tmp_path)
        assert mgr.allow_refactoring_suggestions("my-slug") is True

    def test_engagement_override_false_when_project_missing(self, tmp_path):
        # No project config, engagement says False
        eng_dir = tmp_path / ".harness" / "engagements" / "my-slug"
        eng_dir.mkdir(parents=True)
        eng_file = eng_dir / "engagement.yaml"
        with open(eng_file, "w") as f:
            yaml.dump({"allow_refactoring_suggestions": False}, f)

        mgr = HarnessConfigManager(tmp_path)
        assert mgr.allow_refactoring_suggestions("my-slug") is False

    def test_engagement_returns_none_if_no_file(self, tmp_path):
        mgr = HarnessConfigManager(tmp_path)
        # Internal method
        assert mgr._engagement_allow_refactoring("ghost") is None

    def test_set_project_allow_refactoring(self, tmp_path):
        mgr = HarnessConfigManager(tmp_path)
        mgr.set_project_allow_refactoring(False)

        # Reload with a new manager
        mgr2 = HarnessConfigManager(tmp_path)
        assert mgr2.allow_refactoring_suggestions() is False

    def test_set_project_allow_refactoring_twice(self, tmp_path):
        mgr = HarnessConfigManager(tmp_path)
        mgr.set_project_allow_refactoring(False)
        mgr.set_project_allow_refactoring(True)

        mgr2 = HarnessConfigManager(tmp_path)
        assert mgr2.allow_refactoring_suggestions() is True

    def test_set_engagement_allow_refactoring(self, tmp_path):
        mgr = HarnessConfigManager(tmp_path)
        mgr.set_engagement_allow_refactoring("my-slug", False)

        assert mgr.allow_refactoring_suggestions("my-slug") is False

    def test_set_engagement_allow_refactoring_overwrites(self, tmp_path):
        mgr = HarnessConfigManager(tmp_path)
        mgr.set_engagement_allow_refactoring("my-slug", False)
        mgr.set_engagement_allow_refactoring("my-slug", True)

        assert mgr.allow_refactoring_suggestions("my-slug") is True

    def test_set_engagement_creates_file(self, tmp_path):
        mgr = HarnessConfigManager(tmp_path)
        mgr.set_engagement_allow_refactoring("brand-new", True)

        eng_path = tmp_path / ".harness" / "engagements" / "brand-new" / "engagement.yaml"
        assert eng_path.is_file()


class TestModuleLevelHelpers:
    def test_allow_refactoring_suggestions_default(self, tmp_path):
        assert allow_refactoring_suggestions(tmp_path) is True

    def test_allow_refactoring_suggestions_with_slug(self, tmp_path):
        assert allow_refactoring_suggestions(tmp_path, "ghost") is True

    def test_load_project_config_missing(self, tmp_path):
        assert load_project_config(tmp_path) == {}

    def test_load_project_config_present(self, tmp_path):
        config_dir = tmp_path / ".harness"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"allow_refactoring_suggestions": False}, f)

        config = load_project_config(tmp_path)
        assert config == {"allow_refactoring_suggestions": False}

    def test_load_project_config_with_extra_keys(self, tmp_path):
        config_dir = tmp_path / ".harness"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"allow_refactoring_suggestions": True, "extra": "value"}, f)

        config = load_project_config(tmp_path)
        assert config["allow_refactoring_suggestions"] is True
        assert config["extra"] == "value"

    def test_ensure_project_config_creates_file(self, tmp_path):
        ensure_project_config(tmp_path)
        config_file = tmp_path / ".harness" / "config.yaml"
        assert config_file.is_file()
        with open(config_file) as f:
            data = yaml.safe_load(f)
        assert data["allow_refactoring_suggestions"] is True

    def test_ensure_project_config_idempotent(self, tmp_path):
        ensure_project_config(tmp_path)
        ensure_project_config(tmp_path)  # second call should not error
        config_file = tmp_path / ".harness" / "config.yaml"
        assert config_file.is_file()


class TestConfigManagerEdgeCases:
    def test_engagement_file_with_missing_key(self, tmp_path):
        """Engagement file exists but has no allow_refactoring_suggestions key."""
        eng_dir = tmp_path / ".harness" / "engagements" / "my-slug"
        eng_dir.mkdir(parents=True)
        eng_file = eng_dir / "engagement.yaml"
        with open(eng_file, "w") as f:
            yaml.dump({"other_key": 42}, f)

        mgr = HarnessConfigManager(tmp_path)
        # Should fall through to project (missing) → default True
        assert mgr.allow_refactoring_suggestions("my-slug") is True

    def test_project_config_caching(self, tmp_path):
        """Manager should cache loaded config."""
        config_dir = tmp_path / ".harness"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"allow_refactoring_suggestions": False}, f)

        mgr = HarnessConfigManager(tmp_path)
        assert mgr.allow_refactoring_suggestions() is False

        # Change file on disk
        with open(config_file, "w") as f:
            yaml.dump({"allow_refactoring_suggestions": True}, f)

        # Manager should still return cached False
        assert mgr.allow_refactoring_suggestions() is False
