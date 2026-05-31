"""Tests for infrastructure/yaml/engagement_repo.py.

YamlEngagementRepository delegates to the JSON-based repository.
We test the delegation layer.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.infrastructure.yaml.engagement_repo import YamlEngagementRepository
from harness.domain.engagement.model import Engagement, EngagementStatus
from harness.domain.identifiers import Slug


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_impl():
    with patch("harness.infrastructure.yaml.engagement_repo.JsonEngagementRepository") as m:
        instance = MagicMock()
        m.return_value = instance
        yield instance


@pytest.fixture
def repo(mock_impl) -> YamlEngagementRepository:
    return YamlEngagementRepository(root=Path("/tmp/fake"))


# ── Implementation access ───────────────────────────────────────────────────


class TestImplAccess:
    def test_root_property(self, mock_impl):
        mock_impl.root = Path("/test/root")
        repo = YamlEngagementRepository(root=Path("/test/root"))
        assert repo.root == Path("/test/root")

    def test_root_delegates_to_impl(self, mock_impl):
        mock_impl.root = Path("/expected")
        repo = YamlEngagementRepository()
        assert repo.root == Path("/expected")


# ── Delegation methods ──────────────────────────────────────────────────────


class TestSave:
    def test_save_delegates_for_engagement(self, repo, mock_impl):
        eng = Engagement(slug="test-eng")
        repo.save(eng)
        mock_impl.save.assert_called_once_with(eng)

    def test_save_ignores_non_engagement(self, repo, mock_impl):
        repo.save({"not": "engagement"})
        mock_impl.save.assert_not_called()


class TestGet:
    def test_get_returns_engagement(self, repo, mock_impl):
        mock_impl.load.return_value = "mock_engagement"
        result = repo.get(Slug("test-eng"))
        mock_impl.load.assert_called_once_with("test-eng")
        assert result == "mock_engagement"

    def test_get_returns_none_on_not_found(self, repo, mock_impl):
        from harness.errors import EngagementNotFoundError
        mock_impl.load.side_effect = EngagementNotFoundError("test-eng")
        result = repo.get(Slug("test-eng"))
        assert result is None


class TestExists:
    def test_exists_delegates(self, repo, mock_impl):
        mock_impl.exists.return_value = True
        assert repo.exists(Slug("eng")) is True
        mock_impl.exists.assert_called_once_with("eng")

    def test_exists_false(self, repo, mock_impl):
        mock_impl.exists.return_value = False
        assert repo.exists(Slug("missing")) is False


class TestDelete:
    def test_delete_delegates(self, repo, mock_impl):
        repo.delete(Slug("to-delete"))
        mock_impl.delete.assert_called_once_with("to-delete")


class TestListAll:
    def test_list_all_delegates(self, repo, mock_impl):
        mock_impl.list_all.return_value = ["eng1", "eng2"]
        result = repo.list_all()
        assert result == ["eng1", "eng2"]
        mock_impl.list_all.assert_called_once()


class TestUpdateStatus:
    def test_update_status_with_string(self, repo, mock_impl):
        repo.update_status(Slug("eng"), "active")
        mock_impl.update_status.assert_called_once_with("eng", EngagementStatus("active"))

    def test_update_status_with_enum(self, repo, mock_impl):
        repo.update_status(Slug("eng"), EngagementStatus.ACTIVE)
        mock_impl.update_status.assert_called_once_with("eng", EngagementStatus.ACTIVE)
