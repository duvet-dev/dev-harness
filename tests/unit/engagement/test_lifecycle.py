"""Tests for harness.domain.engagement.lifecycle."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from harness.domain.engagement.lifecycle import (
    _load_active_mapping,
    _parse_engagement_md,
    _save_active_mapping,
    close_engagement,
    create_engagement_dir,
    engagement_dir_for,
    read_active_engagement,
    set_active_engagement,
    slugify,
    update_active_engagement_mapping,
    write_engagement_metadata,
)


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_already_kebab(self):
        assert slugify("hello-world") == "hello-world"

    def test_special_chars_removed(self):
        assert slugify("Hello! World?") == "hello-world"

    def test_mixed_case(self):
        assert slugify("MY EngAGEment") == "my-engagement"

    def test_leading_trailing(self):
        assert slugify("  Spaces  ") == "--spaces--"

    def test_empty_string(self):
        assert slugify("") == ""


class TestCreateEngagementDir:
    def test_creates_directory_structure(self, tmp_path):
        slug = "test-eng"
        eng_dir = create_engagement_dir(tmp_path, slug)
        assert eng_dir.is_dir()
        assert (eng_dir / "engagement.md").exists()
        assert (eng_dir / "engagement.yaml").exists()
        assert (eng_dir / "plan.md").exists()
        assert (eng_dir / "plan.yaml").exists()
        assert (eng_dir / "waves").is_dir()

    def test_raises_if_exists(self, tmp_path):
        slug = "existing-eng"
        create_engagement_dir(tmp_path, slug)
        with pytest.raises(FileExistsError):
            create_engagement_dir(tmp_path, slug)

    def test_plan_yaml_initial_content(self, tmp_path):
        slug = "plan-test"
        create_engagement_dir(tmp_path, slug)
        plan_yaml = tmp_path / ".harness" / "engagements" / slug / "plan.yaml"
        content = plan_yaml.read_text()
        assert "waves:" in content

    def test_engagement_yaml_initial_content(self, tmp_path):
        slug = "yaml-test"
        create_engagement_dir(tmp_path, slug)
        eng_yaml = tmp_path / ".harness" / "engagements" / slug / "engagement.yaml"
        data = yaml.safe_load(eng_yaml.read_text())
        assert data["slug"] == slug


class TestWriteEngagementMetadata:
    def test_writes_frontmatter_and_yaml(self, tmp_path):
        slug = "meta-test"
        eng_dir = create_engagement_dir(tmp_path, slug)
        write_engagement_metadata(
            eng_dir,
            name="Test Engagement",
            slug=slug,
            branch="main",
            session_type="refactoring",
            allow_refactoring_suggestions=True,
        )
        md = (eng_dir / "engagement.md").read_text()
        assert "slug:" in md
        assert "branch: main" in md
        assert "status: planning" in md
        assert "# Test Engagement" in md

        eng_yaml = eng_dir / "engagement.yaml"
        data = yaml.safe_load(eng_yaml.read_text())
        assert data["session_type"] == "refactoring"
        assert data["allow_refactoring_suggestions"] is True

    def test_optional_params_omitted(self, tmp_path):
        slug = "bare-meta"
        eng_dir = create_engagement_dir(tmp_path, slug)
        write_engagement_metadata(eng_dir, name="Bare", slug=slug, branch="dev")
        data = yaml.safe_load((eng_dir / "engagement.yaml").read_text())
        assert "session_type" not in data
        assert "allow_refactoring_suggestions" not in data


class TestSetActiveEngagement:
    def test_sets_active_engagement(self, tmp_path):
        slug = "active-test"
        create_engagement_dir(tmp_path, slug)

        with patch("harness.scm.git.GitRepo") as MockGitRepo:
            mock_repo = MagicMock()
            mock_repo.branch.return_value = "feature-x"
            MockGitRepo.return_value = mock_repo

            set_active_engagement(tmp_path, slug)

            mapping = _load_active_mapping(tmp_path)
            assert mapping["branches"]["feature-x"] == slug

    def test_raises_if_engagement_missing(self, tmp_path):
        with patch("harness.scm.git.GitRepo"):
            with pytest.raises(ValueError, match="not found"):
                set_active_engagement(tmp_path, "nonexistent")

    def test_updates_existing_mapping(self, tmp_path):
        slug1 = "eng-one"
        slug2 = "eng-two"
        create_engagement_dir(tmp_path, slug1)
        create_engagement_dir(tmp_path, slug2)

        with patch("harness.scm.git.GitRepo") as MockGitRepo:
            mock_repo = MagicMock()
            mock_repo.branch.return_value = "main"
            MockGitRepo.return_value = mock_repo
            set_active_engagement(tmp_path, slug1)

            mock_repo.branch.return_value = "feature"
            set_active_engagement(tmp_path, slug2)

        mapping = _load_active_mapping(tmp_path)
        assert mapping["branches"]["main"] == slug1
        assert mapping["branches"]["feature"] == slug2


class TestCloseEngagement:
    def test_closes_engagement_and_clears_mapping(self, tmp_path):
        slug = "close-test"
        eng_dir = create_engagement_dir(tmp_path, slug)
        write_engagement_metadata(eng_dir, name="Close Test", slug=slug, branch="main")

        with patch("harness.scm.git.GitRepo") as MockGitRepo:
            mock_repo = MagicMock()
            mock_repo.branch.return_value = "main"
            MockGitRepo.return_value = mock_repo
            set_active_engagement(tmp_path, slug)

        metadata = close_engagement(tmp_path, slug)
        assert metadata["status"] == "completed"
        assert "completed_at" in metadata

        # Check mapping is cleared
        mapping = _load_active_mapping(tmp_path)
        assert "main" not in mapping.get("branches", {})

    def test_raises_if_not_found(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            close_engagement(tmp_path, "nonexistent")


class TestReadActiveEngagement:
    def test_returns_active_slug(self, tmp_path):
        slug = "read-test"
        create_engagement_dir(tmp_path, slug)

        with patch("harness.scm.git.GitRepo") as MockGitRepo:
            mock_repo = MagicMock()
            mock_repo.branch.return_value = "main"
            MockGitRepo.return_value = mock_repo
            set_active_engagement(tmp_path, slug)

        with patch("harness.scm.git.GitRepo") as MockGitRepo2:
            mock_repo2 = MagicMock()
            mock_repo2.branch.return_value = "main"
            MockGitRepo2.return_value = mock_repo2
            result = read_active_engagement(tmp_path)
            assert result == slug

    def test_returns_none_when_no_mapping(self, tmp_path):
        with patch("harness.scm.git.GitRepo") as MockGitRepo:
            mock_repo = MagicMock()
            mock_repo.branch.return_value = "main"
            MockGitRepo.return_value = mock_repo
            result = read_active_engagement(tmp_path)
            assert result is None

    def test_returns_none_on_git_error(self, tmp_path):
        with patch("harness.scm.git.GitRepo", side_effect=Exception("No git")):
            result = read_active_engagement(tmp_path)
            assert result is None


class TestUpdateActiveEngagementMapping:
    def test_updates_mapping_for_all_branches(self, tmp_path):
        mapping = {"branches": {"main": "old-slug", "feat": "old-slug"}}
        _save_active_mapping(tmp_path, mapping)
        update_active_engagement_mapping(tmp_path, "old-slug", "new-slug")
        loaded = _load_active_mapping(tmp_path)
        assert loaded["branches"]["main"] == "new-slug"
        assert loaded["branches"]["feat"] == "new-slug"

    def test_noop_when_not_found(self, tmp_path):
        mapping = {"branches": {"main": "other-slug"}}
        _save_active_mapping(tmp_path, mapping)
        update_active_engagement_mapping(tmp_path, "old-slug", "new-slug")
        loaded = _load_active_mapping(tmp_path)
        assert loaded["branches"]["main"] == "other-slug"

    def test_noop_when_no_mapping_file(self, tmp_path):
        update_active_engagement_mapping(tmp_path, "old", "new")
        # Should not raise


class TestEngagementDirFor:
    def test_returns_path_regardless_of_existence(self, tmp_path):
        path = engagement_dir_for(tmp_path, "fake")
        assert path.name == "fake"
        assert not path.exists()


class TestParseEngagementMd:
    def test_parses_frontmatter(self, tmp_path):
        md_file = tmp_path / "engagement.md"
        md_file.write_text("---\nslug: test\nstatus: planning\n---\n\n# Test\n")
        result = _parse_engagement_md(md_file)
        assert result["slug"] == "test"
        assert result["status"] == "planning"

    def test_returns_empty_for_no_frontmatter(self, tmp_path):
        md_file = tmp_path / "engagement.md"
        md_file.write_text("# Test\n\nNo frontmatter.\n")
        result = _parse_engagement_md(md_file)
        assert result == {}

    def test_returns_empty_for_malformed(self, tmp_path):
        md_file = tmp_path / "engagement.md"
        md_file.write_text("---\n- invalid: [\n---\n")
        result = _parse_engagement_md(md_file)
        assert result == {}

    def test_returns_empty_on_empty_file(self, tmp_path):
        md_file = tmp_path / "engagement.md"
        md_file.write_text("")
        result = _parse_engagement_md(md_file)
        assert result == {}


class TestLoadSaveActiveMapping:
    def test_load_returns_default_when_no_file(self, tmp_path):
        result = _load_active_mapping(tmp_path / "nonexistent")
        assert result == {"branches": {}}

    def test_save_and_load_roundtrip(self, tmp_path):
        data = {"branches": {"main": "my-eng"}}
        _save_active_mapping(tmp_path, data)
        loaded = _load_active_mapping(tmp_path)
        assert loaded == data

    def test_load_ensures_branches_key(self, tmp_path):
        path = tmp_path / ".harness" / "active-engagements.yaml"
        path.parent.mkdir(parents=True)
        path.write_text("{}\n")
        result = _load_active_mapping(tmp_path)
        assert "branches" in result
