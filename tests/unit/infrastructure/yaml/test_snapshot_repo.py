"""Tests for infrastructure/yaml/snapshot_repo.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.infrastructure.yaml.snapshot_repo import YamlSnapshotRepository
from harness.domain.identifiers import EngagementId
from harness.domain.enums import SnapshotStatus


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def repo() -> YamlSnapshotRepository:
    return YamlSnapshotRepository()


class TestWrite:
    def test_write_with_project_snapshot(self, repo):
        """Writing a ProjectSnapshot delegates to SnapshotWriter."""
        MockSnapshotCls = type("MockSnapshot", (), {})
        with patch("harness.infrastructure.yaml.snapshot_repo.ProjectSnapshot", MockSnapshotCls):
            with patch.object(repo._writer, "write") as mock_write:
                snapshot = MagicMock(spec=MockSnapshotCls)
                path = Path("/tmp/snap.yaml")
                repo.write(snapshot, path)
                mock_write.assert_called_once_with(snapshot, path)

    def test_write_ignores_non_snapshot(self, repo):
        with patch.object(repo._writer, "write") as mock_write:
            repo.write({"not": "snapshot"}, Path("/tmp/x.yaml"))
            mock_write.assert_not_called()


class TestWritePhaseCheckpoint:
    def test_write_checkpoint_delegates(self, repo):
        with patch("harness.state.snapshot._load_or_create") as mock_load:
            with patch.object(repo._writer, "write_phase_checkpoint") as mock_write:
                mock_load.return_value = "loaded_snapshot"
                path = Path("/tmp/checkpoint.yaml")
                repo.write_phase_checkpoint(
                    EngagementId("eng-1"),
                    "design",
                    SnapshotStatus.IN_PROGRESS,
                    path,
                    retry_count=2,
                    has_stale_summary=True,
                )
                mock_load.assert_called_once_with(path)
                mock_write.assert_called_once_with(
                    engagement_id="eng-1",
                    phase="design",
                    status="in_progress",
                    path=path,
                    retry_count=2,
                    has_stale_summary=True,
                )

    def test_write_checkpoint_with_string_status(self, repo):
        with patch("harness.state.snapshot._load_or_create") as mock_load:
            with patch.object(repo._writer, "write_phase_checkpoint") as mock_write:
                mock_load.return_value = "loaded"
                path = Path("/tmp/cp.yaml")
                repo.write_phase_checkpoint(
                    EngagementId("e1"), "build", "completed", path,
                )
                mock_write.assert_called_once_with(
                    engagement_id="e1",
                    phase="build",
                    status="completed",
                    path=path,
                    retry_count=0,
                    has_stale_summary=False,
                )
