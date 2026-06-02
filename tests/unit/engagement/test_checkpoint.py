"""Tests for harness.domain.engagement.checkpoint."""

import json
from pathlib import Path

import pytest

from harness.domain.engagement.checkpoint import (
    CHECKPOINT_EXPIRY_HOURS,
    Checkpoint,
    CheckpointManager,
    _gather_hashes,
    _hash_file,
)


class TestHashFile:
    def test_hash_known_content(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h = _hash_file(f)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_hash_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        h = _hash_file(f)
        assert isinstance(h, str)
        assert len(h) == 64


class TestGatherHashes:
    def test_gathers_all_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("aaa")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.txt").write_text("bbb")
        hashes = _gather_hashes(tmp_path)
        assert len(hashes) == 2
        assert "a.txt" in hashes
        assert "sub/b.txt" in hashes

    def test_returns_empty_for_nonexistent_dir(self, tmp_path):
        hashes = _gather_hashes(tmp_path / "nonexistent")
        assert hashes == {}

    def test_respects_max_files(self, tmp_path):
        for i in range(10):
            (tmp_path / f"f{i}.txt").write_text(f"content{i}")
        hashes = _gather_hashes(tmp_path, max_files=3)
        assert len(hashes) <= 3

    def test_skips_symlinks(self, tmp_path):
        (tmp_path / "real.txt").write_text("real")
        (tmp_path / "link.txt").symlink_to("real.txt")
        hashes = _gather_hashes(tmp_path)
        assert "real.txt" in hashes
        assert "link.txt" not in hashes


class TestCheckpoint:
    def test_default_timestamp_set_on_init(self):
        ckpt = Checkpoint(checkpoint_id="cp-01", phase_name="design", engagement_slug="test")
        assert ckpt.timestamp != ""

    def test_is_stale_returns_true_for_past_date(self):
        ckpt = Checkpoint(
            checkpoint_id="cp-01",
            phase_name="design",
            engagement_slug="test",
            timestamp="2020-01-01T00:00:00+00:00",
        )
        assert ckpt.is_stale() is True

    def test_is_stale_returns_false_for_recent(self):
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        ckpt = Checkpoint(
            checkpoint_id="cp-01",
            phase_name="design",
            engagement_slug="test",
            timestamp=recent,
        )
        assert ckpt.is_stale() is False

    def test_is_stale_returns_true_on_parse_error(self):
        ckpt = Checkpoint(
            checkpoint_id="cp-01",
            phase_name="design",
            engagement_slug="test",
            timestamp="not-a-date",
        )
        assert ckpt.is_stale() is True


class TestCheckpointManager:
    def test_create_creates_directory_and_files(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "test-eng")
        ckpt = mgr.create(phase_name="design", context="Working on API", feedback_content="# Feedback")
        ckpt_dir = tmp_path / ".harness" / "engagements" / "test-eng" / "checkpoints" / ckpt.checkpoint_id
        assert ckpt_dir.is_dir()
        snapshot = mgr._snapshot_path(ckpt.checkpoint_id)
        assert snapshot.is_file()
        context_file = mgr._context_path(ckpt.checkpoint_id)
        assert context_file.read_text() == "Working on API"
        feedback_file = mgr._feedback_path(ckpt.checkpoint_id)
        assert feedback_file.is_file()

    def test_create_with_snapshot_dir(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("print('hello')")
        mgr = CheckpointManager(tmp_path, "test-eng")
        ckpt = mgr.create(phase_name="build", snapshot_dir=src)
        assert "main.py" in ckpt.file_hashes

    def test_load_returns_checkpoint(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "test-eng")
        ckpt = mgr.create(phase_name="design", context="Initial design")
        loaded = mgr.load(ckpt.checkpoint_id)
        assert loaded is not None
        assert loaded.checkpoint_id == ckpt.checkpoint_id
        assert loaded.phase_name == "design"
        assert loaded.context == "Initial design"

    def test_load_returns_none_for_unknown(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "test-eng")
        assert mgr.load("nonexistent") is None

    def test_load_handles_corrupt_snapshot(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "test-eng")
        ckpt_dir = mgr._checkpoint_dir("checkpoint-01")
        ckpt_dir.mkdir(parents=True)
        (ckpt_dir / "snapshot.json").write_text("not json")
        assert mgr.load("checkpoint-01") is None

    def test_list_checkpoints_returns_newest_first(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "test-eng")
        ckpt1 = mgr.create(phase_name="phase1")
        import time
        time.sleep(0.01)
        ckpt2 = mgr.create(phase_name="phase2")
        checkpoints = mgr.list_checkpoints()
        assert len(checkpoints) == 2
        assert checkpoints[0].checkpoint_id == ckpt2.checkpoint_id

    def test_list_checkpoints_empty(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "test-eng")
        assert mgr.list_checkpoints() == []

    def test_get_latest_returns_newest(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "test-eng")
        ckpt1 = mgr.create(phase_name="phase1")
        latest = mgr.get_latest()
        assert latest is not None
        assert latest.checkpoint_id == ckpt1.checkpoint_id

    def test_get_latest_returns_none_when_empty(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "test-eng")
        assert mgr.get_latest() is None

    def test_delete_removes_directory(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "test-eng")
        ckpt = mgr.create(phase_name="design")
        assert mgr.delete(ckpt.checkpoint_id) is True
        assert not mgr._checkpoint_dir(ckpt.checkpoint_id).exists()

    def test_delete_returns_false_for_unknown(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "test-eng")
        assert mgr.delete("nonexistent") is False

    def test_next_id_sequences_correctly(self, tmp_path):
        mgr = CheckpointManager(tmp_path, "test-eng")
        ckpt = mgr.create(phase_name="one")
        assert ckpt.checkpoint_id == "checkpoint-01"
        ckpt = mgr.create(phase_name="two")
        assert ckpt.checkpoint_id == "checkpoint-02"
