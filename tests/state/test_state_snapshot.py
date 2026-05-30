"""Tests for harness.state.snapshot — SnapshotWriter and data classes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from harness.state.snapshot import (
    EngagementSnapshot,
    ProjectSnapshot,
    SnapshotWriter,
    _engagement_to_dict,
    _project_to_dict,
    _load_or_create,
)


class TestEngagementSnapshot:
    """Tests for the EngagementSnapshot dataclass."""

    def test_create_minimal(self):
        snap = EngagementSnapshot(
            id="eng-1",
            description="Test engagement",
            status="planning",
            gate_mode="auto",
            phase="requirements",
        )
        assert snap.id == "eng-1"
        assert snap.retry_count == 0
        assert snap.has_stale_summary is False

    def test_create_full(self):
        snap = EngagementSnapshot(
            id="eng-1",
            description="Full test",
            status="in_progress",
            gate_mode="full",
            phase="build",
            retry_count=3,
            has_stale_summary=True,
        )
        assert snap.retry_count == 3
        assert snap.has_stale_summary is True


class TestProjectSnapshot:
    """Tests for the ProjectSnapshot dataclass."""

    def test_create(self):
        eng = EngagementSnapshot(
            id="eng-1", description="Test", status="active",
            gate_mode="auto", phase="requirements",
        )
        snap = ProjectSnapshot(
            project_name="my-project",
            version="0.2.0",
            current_engagement="eng-1",
            engagements=[eng],
        )
        assert snap.project_name == "my-project"
        assert snap.current_engagement == "eng-1"
        assert len(snap.engagements) == 1

    def test_auto_timestamp_on_create(self):
        snap = ProjectSnapshot(
            project_name="p",
            version="1.0",
            current_engagement=None,
            engagements=[],
        )
        # last_updated should be set automatically
        assert snap.last_updated != ""
        # Valid ISO-8601 timestamp
        datetime.fromisoformat(snap.last_updated)

    def test_explicit_timestamp(self):
        ts = "2026-01-01T00:00:00+00:00"
        snap = ProjectSnapshot(
            project_name="p",
            version="1.0",
            current_engagement=None,
            engagements=[],
            last_updated=ts,
        )
        assert snap.last_updated == ts


class TestEngagementToDict:
    """Tests for the _engagement_to_dict helper."""

    def test_basic_conversion(self):
        eng = EngagementSnapshot(
            id="eng-1", description="Test", status="planning",
            gate_mode="auto", phase="requirements",
        )
        d = _engagement_to_dict(eng)
        assert d["id"] == "eng-1"
        assert d["retry_count"] == 0
        assert d["has_stale_summary"] is False


class TestProjectToDict:
    """Tests for the _project_to_dict helper."""

    def test_basic_conversion(self):
        eng = EngagementSnapshot(
            id="eng-1", description="Test", status="planning",
            gate_mode="auto", phase="requirements",
        )
        snap = ProjectSnapshot(
            project_name="p",
            version="0.1",
            current_engagement="eng-1",
            engagements=[eng],
        )
        d = _project_to_dict(snap)
        assert d["project_name"] == "p"
        assert d["current_engagement"] == "eng-1"
        assert len(d["engagements"]) == 1


class TestLoadOrCreate:
    """Tests for the _load_or_create helper."""

    def test_loads_existing_file(self, tmp_path):
        path = tmp_path / "snap.yaml"
        data = {
            "project_name": "my-project",
            "version": "1.0",
            "current_engagement": "eng-1",
            "engagements": [
                {
                    "id": "eng-1",
                    "description": "Test",
                    "status": "active",
                    "gate_mode": "auto",
                    "phase": "build",
                    "retry_count": 0,
                    "has_stale_summary": False,
                },
            ],
            "last_updated": "2026-01-01T00:00:00+00:00",
        }
        with open(path, "w") as f:
            yaml.dump(data, f)

        loaded = _load_or_create(path)
        assert loaded.project_name == "my-project"
        assert loaded.current_engagement == "eng-1"
        assert len(loaded.engagements) == 1

    def test_returns_default_when_file_missing(self, tmp_path):
        path = tmp_path / "nonexistent.yaml"
        loaded = _load_or_create(path)
        assert loaded.project_name == "unknown"
        assert loaded.current_engagement is None
        assert loaded.engagements == []

    def test_handles_empty_yaml(self, tmp_path):
        path = tmp_path / "empty.yaml"
        path.write_text("")
        loaded = _load_or_create(path)
        assert loaded.project_name == "unknown"


class TestSnapshotWriter:
    """Tests for the SnapshotWriter class."""

    def test_write_creates_file(self, tmp_path):
        eng = EngagementSnapshot(
            id="eng-1", description="Test", status="active",
            gate_mode="auto", phase="build",
        )
        snap = ProjectSnapshot(
            project_name="test-project",
            version="0.1.0",
            current_engagement="eng-1",
            engagements=[eng],
        )
        path = tmp_path / "sub" / "snapshot.yaml"
        SnapshotWriter.write(snap, path)

        assert path.exists()
        content = yaml.safe_load(path.read_text())
        assert content["project_name"] == "test-project"
        assert content["current_engagement"] == "eng-1"

    def test_write_creates_parent_dirs(self, tmp_path):
        eng = EngagementSnapshot(
            id="eng-1", description="T", status="active",
            gate_mode="auto", phase="build",
        )
        snap = ProjectSnapshot(
            project_name="p", version="1.0",
            current_engagement="eng-1", engagements=[eng],
        )
        deep_path = tmp_path / "a" / "b" / "c" / "snap.yaml"
        SnapshotWriter.write(snap, deep_path)
        assert deep_path.exists()

    def test_write_yaml_format(self, tmp_path):
        eng = EngagementSnapshot(
            id="eng-1", description="Test", status="active",
            gate_mode="auto", phase="build",
        )
        snap = ProjectSnapshot(
            project_name="p", version="1.0",
            current_engagement="eng-1", engagements=[eng],
        )
        path = tmp_path / "snap.yaml"
        SnapshotWriter.write(snap, path)
        raw = path.read_text()
        # Should be human-readable YAML with dashes for list items
        assert "engagement_id:" not in raw  # uses 'id:'
        assert "project_name: p" in raw

    def test_write_phase_checkpoint_new_engagement(self, tmp_path):
        path = tmp_path / "snap.yaml"
        SnapshotWriter.write_phase_checkpoint(
            engagement_id="eng-new",
            phase="build",
            status="in_progress",
            path=path,
        )
        assert path.exists()
        loaded = _load_or_create(path)
        assert len(loaded.engagements) == 1
        assert loaded.engagements[0].id == "eng-new"
        assert loaded.engagements[0].phase == "build"

    def test_write_phase_checkpoint_updates_existing(self, tmp_path):
        path = tmp_path / "snap.yaml"
        # First write
        SnapshotWriter.write_phase_checkpoint(
            engagement_id="eng-1", phase="requirements", status="completed",
            path=path,
        )
        # Update
        SnapshotWriter.write_phase_checkpoint(
            engagement_id="eng-1", phase="design", status="in_progress",
            path=path, retry_count=2, has_stale_summary=True,
        )
        loaded = _load_or_create(path)
        assert len(loaded.engagements) == 1
        assert loaded.engagements[0].phase == "design"
        assert loaded.engagements[0].retry_count == 2
        assert loaded.engagements[0].has_stale_summary is True

    def test_write_phase_checkpoint_multiple_engagements(self, tmp_path):
        path = tmp_path / "snap.yaml"
        SnapshotWriter.write_phase_checkpoint(
            engagement_id="eng-1", phase="build", status="completed", path=path,
        )
        SnapshotWriter.write_phase_checkpoint(
            engagement_id="eng-2", phase="design", status="in_progress", path=path,
        )
        loaded = _load_or_create(path)
        assert len(loaded.engagements) == 2
        ids = {e.id for e in loaded.engagements}
        assert ids == {"eng-1", "eng-2"}
