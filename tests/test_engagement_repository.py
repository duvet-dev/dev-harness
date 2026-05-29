"""Tests for EngagementRepository — save, load, list, delete, error handling.

Uses temporary directories to avoid polluting the real .harness directory.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from harness.engagement.model import Engagement, EngagementStatus, HealthWarning
from harness.engagement.repository import EngagementRepository
from harness.errors import EngagementNotFoundError


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    """Create a temporary project root with .harness/ directory."""
    harness_dir = tmp_path / ".harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def repo(tmp_root: Path) -> EngagementRepository:
    return EngagementRepository(root=tmp_root)


@pytest.fixture
def sample_engagement() -> Engagement:
    return Engagement(
        slug="test-eng",
        workflow_name="standard",
        session_type="greenfield",
        status=EngagementStatus.CREATED,
        target_branch="eng/test-eng",
    )


@pytest.fixture
def saved_engagement(repo: EngagementRepository) -> Engagement:
    """Save a sample engagement and return it."""
    eng = Engagement(
        slug="saved-eng",
        workflow_name="standard",
        status=EngagementStatus.ACTIVE,
        target_branch="eng/saved-eng",
    )
    repo.save(eng)
    return eng


# ── Save Tests ──────────────────────────────────────────────────────


class TestEngagementRepositorySave:
    """Tests for EngagementRepository.save()."""

    def test_save_creates_file(self, repo: EngagementRepository, sample_engagement: Engagement):
        """Saving an engagement creates a JSON file."""
        repo.save(sample_engagement)
        path = repo._engagement_path("test-eng")
        assert path.is_file()

    def test_save_creates_directory(self, repo: EngagementRepository, sample_engagement: Engagement):
        """Saving an engagement creates the engagement directory."""
        repo.save(sample_engagement)
        eng_dir = repo._engagement_path("test-eng").parent
        assert eng_dir.is_dir()

    def test_save_empty_slug_raises(self, repo: EngagementRepository):
        """Saving with empty slug raises ValueError."""
        eng = Engagement(slug="")
        with pytest.raises(ValueError, match="cannot be empty"):
            repo.save(eng)

    def test_save_overwrites_existing(self, repo: EngagementRepository):
        """Saving the same slug overwrites the existing file."""
        eng1 = Engagement(slug="test", target_branch="branch1")
        repo.save(eng1)
        eng2 = Engagement(slug="test", target_branch="branch2")
        repo.save(eng2)
        loaded = repo.load("test")
        assert loaded.target_branch == "branch2"


# ── Load Tests ──────────────────────────────────────────────────────


class TestEngagementRepositoryLoad:
    """Tests for EngagementRepository.load()."""

    def test_load_returns_saved_engagement(
        self, repo: EngagementRepository, sample_engagement: Engagement
    ):
        """Loading a saved engagement returns matching data."""
        repo.save(sample_engagement)
        loaded = repo.load("test-eng")
        assert loaded.slug == "test-eng"
        assert loaded.workflow_name == "standard"
        assert loaded.session_type == "greenfield"
        assert loaded.status == EngagementStatus.CREATED
        assert loaded.target_branch == "eng/test-eng"

    def test_load_with_warnings(self, repo: EngagementRepository):
        """Loading an engagement with warnings restores them."""
        eng = Engagement(
            slug="warn-eng",
            warnings=[
                HealthWarning(type="dirty_repo", message="Uncommitted changes"),
                HealthWarning(type="branch_missing", message="Branch not found"),
            ],
        )
        repo.save(eng)
        loaded = repo.load("warn-eng")
        assert len(loaded.warnings) == 2
        assert loaded.warnings[0].type == "dirty_repo"
        assert loaded.warnings[1].type == "branch_missing"

    def test_load_nonexistent_raises(self, repo: EngagementRepository):
        """Loading a non-existent slug raises EngagementNotFoundError."""
        with pytest.raises(EngagementNotFoundError, match="not found"):
            repo.load("does-not-exist")

    def test_load_empty_slug_raises(self, repo: EngagementRepository):
        """Loading with empty slug raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            repo.load("")

    def test_load_corrupt_file_raises(self, repo: EngagementRepository):
        """Loading a corrupt JSON file raises EngagementNotFoundError."""
        eng_dir = repo._engagement_path("corrupt").parent
        eng_dir.mkdir(parents=True, exist_ok=True)
        repo._engagement_path("corrupt").write_text("not valid json{")
        with pytest.raises(EngagementNotFoundError, match="corrupt"):
            repo.load("corrupt")

    def test_load_status_enum_restored(
        self, repo: EngagementRepository, saved_engagement: Engagement
    ):
        """Loading restores the EngagementStatus enum correctly."""
        loaded = repo.load("saved-eng")
        assert loaded.status == EngagementStatus.ACTIVE
        assert isinstance(loaded.status, EngagementStatus)

    def test_load_datetime_restored(
        self, repo: EngagementRepository, saved_engagement: Engagement
    ):
        """Loading restores datetime fields correctly."""
        loaded = repo.load("saved-eng")
        assert isinstance(loaded.created_at, datetime)
        assert isinstance(loaded.last_active, datetime)


# ── Exists Tests ────────────────────────────────────────────────────


class TestEngagementRepositoryExists:
    """Tests for EngagementRepository.exists()."""

    def test_exists_returns_true(self, repo: EngagementRepository, sample_engagement: Engagement):
        """exists returns True for saved engagements."""
        repo.save(sample_engagement)
        assert repo.exists("test-eng") is True

    def test_exists_returns_false(self, repo: EngagementRepository):
        """exists returns False for unsaved engagements."""
        assert repo.exists("nonexistent") is False


# ── Delete Tests ────────────────────────────────────────────────────


class TestEngagementRepositoryDelete:
    """Tests for EngagementRepository.delete()."""

    def test_delete_removes_file(
        self, repo: EngagementRepository, sample_engagement: Engagement
    ):
        """Deleting a saved engagement removes its file."""
        repo.save(sample_engagement)
        repo.delete("test-eng")
        assert not repo.exists("test-eng")

    def test_delete_nonexistent_raises(self, repo: EngagementRepository):
        """Deleting a non-existent slug raises EngagementNotFoundError."""
        with pytest.raises(EngagementNotFoundError, match="not found"):
            repo.delete("does-not-exist")

    def test_delete_empty_slug_raises(self, repo: EngagementRepository):
        """Deleting with empty slug raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            repo.delete("")


# ── List All Tests ─────────────────────────────────────────────────


class TestEngagementRepositoryListAll:
    """Tests for EngagementRepository.list_all()."""

    def test_list_all_empty(self, repo: EngagementRepository):
        """list_all returns empty list when no engagements exist."""
        assert repo.list_all() == []

    def test_list_all_returns_all(
        self, repo: EngagementRepository
    ):
        """list_all returns all saved engagements."""
        repo.save(Engagement(slug="eng-1", target_branch="b1"))
        repo.save(Engagement(slug="eng-2", target_branch="b2"))
        engagements = repo.list_all()
        assert len(engagements) == 2
        slugs = [e.slug for e in engagements]
        assert "eng-1" in slugs
        assert "eng-2" in slugs

    def test_list_all_skips_corrupt(self, repo: EngagementRepository):
        """list_all skips corrupt files without raising."""
        repo.save(Engagement(slug="good-eng", target_branch="b1"))
        # Create a corrupt file
        bad_dir = repo._engagement_path("bad-eng").parent
        bad_dir.mkdir(parents=True, exist_ok=True)
        repo._engagement_path("bad-eng").write_text("{corrupt}")
        engagements = repo.list_all()
        assert len(engagements) == 1
        assert engagements[0].slug == "good-eng"

    def test_list_all_sorted(self, repo: EngagementRepository):
        """list_all returns engagements in alphabetical order."""
        repo.save(Engagement(slug="z-eng", target_branch="b1"))
        repo.save(Engagement(slug="a-eng", target_branch="b2"))
        engagements = repo.list_all()
        assert engagements[0].slug == "a-eng"
        assert engagements[1].slug == "z-eng"


# ── Update Status Tests ─────────────────────────────────────────────


class TestEngagementRepositoryUpdateStatus:
    """Tests for EngagementRepository.update_status()."""

    def test_update_status_changes_status(
        self, repo: EngagementRepository, sample_engagement: Engagement
    ):
        """update_status changes the engagement status."""
        repo.save(sample_engagement)
        updated = repo.update_status("test-eng", EngagementStatus.ACTIVE)
        assert updated.status == EngagementStatus.ACTIVE

    def test_update_status_persists(
        self, repo: EngagementRepository, sample_engagement: Engagement
    ):
        """update_status persists the change to disk."""
        repo.save(sample_engagement)
        repo.update_status("test-eng", EngagementStatus.ACTIVE)
        loaded = repo.load("test-eng")
        assert loaded.status == EngagementStatus.ACTIVE

    def test_update_status_nonexistent_raises(self, repo: EngagementRepository):
        """update_status on non-existent slug raises EngagementNotFoundError."""
        with pytest.raises(EngagementNotFoundError):
            repo.update_status("does-not-exist", EngagementStatus.ACTIVE)
