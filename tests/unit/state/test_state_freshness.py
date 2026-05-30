"""Tests for harness.state.freshness."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from harness.state.freshness import (
    FreshnessRecord,
    load_freshness,
    save_freshness,
)


class TestFreshnessRecord:
    def test_create_record(self):
        record = FreshnessRecord(
            branch="main",
            head_sha="abc123",
            last_reconciled="2024-01-15T10:00:00",
        )
        assert record.branch == "main"
        assert record.head_sha == "abc123"
        assert not record.stale

    def test_mark_stale(self):
        record = FreshnessRecord(
            branch="main",
            head_sha="abc123",
            last_reconciled="2024-01-15T10:00:00",
            stale=False,
        )
        stale = record.mark_stale()
        assert stale.stale
        assert stale.head_sha == "abc123"

    def test_mark_fresh(self):
        record = FreshnessRecord(
            branch="main",
            head_sha="old_sha",
            last_reconciled="2024-01-15T10:00:00",
            stale=True,
        )
        fresh = record.mark_fresh(head_sha="new_sha")
        assert not fresh.stale
        assert fresh.head_sha == "new_sha"
        assert "T" in fresh.last_reconciled  # ISO-8601


class TestLoadFreshness:
    def test_returns_none_when_no_file(self, tmp_path: Path):
        assert load_freshness(tmp_path) is None

    def test_loads_valid_file(self, tmp_path: Path):
        (tmp_path / ".harness-freshness.yaml").write_text(yaml.dump({
            "branch": "main",
            "head_sha": "abc123",
            "last_reconciled": "2024-01-15T10:00:00",
            "stale": False,
        }))
        record = load_freshness(tmp_path)
        assert record is not None
        assert record.branch == "main"
        assert record.head_sha == "abc123"
        assert not record.stale


class TestSaveFreshness:
    def test_saves_to_freshness_file(self, tmp_path: Path):
        # Need a .harness dir since freshness file is at root
        (tmp_path / ".harness").mkdir()
        record = FreshnessRecord(
            branch="feature",
            head_sha="def456",
            last_reconciled="2024-01-15T12:00:00",
            stale=False,
        )
        save_freshness(record, tmp_path)
        saved = tmp_path / ".harness-freshness.yaml"
        assert saved.is_file()
        data = yaml.safe_load(saved.read_text())
        assert data["branch"] == "feature"
        assert data["head_sha"] == "def456"

    def test_overwrites_existing(self, tmp_path: Path):
        (tmp_path / ".harness").mkdir()
        record1 = FreshnessRecord(
            branch="main", head_sha="aaa", last_reconciled="t1",
        )
        save_freshness(record1, tmp_path)
        record2 = FreshnessRecord(
            branch="main", head_sha="bbb", last_reconciled="t2",
        )
        save_freshness(record2, tmp_path)
        data = yaml.safe_load((tmp_path / ".harness-freshness.yaml").read_text())
        assert data["head_sha"] == "bbb"

    def test_preserves_stale_flag(self, tmp_path: Path):
        (tmp_path / ".harness").mkdir()
        record = FreshnessRecord(
            branch="main",
            head_sha="abc",
            last_reconciled="t",
            stale=True,
        )
        save_freshness(record, tmp_path)
        data = yaml.safe_load((tmp_path / ".harness-freshness.yaml").read_text())
        assert data["stale"] is True

    def test_roundtrip_complex_values(self, tmp_path: Path):
        (tmp_path / ".harness").mkdir()
        original = FreshnessRecord(
            branch="feature/long-name",
            head_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaabbb",
            last_reconciled="2024-01-15T12:34:56.789Z",
            stale=False,
        )
        save_freshness(original, tmp_path)
        loaded = load_freshness(tmp_path)
        assert loaded is not None
        assert loaded.branch == original.branch
        assert loaded.head_sha == original.head_sha
        assert loaded.last_reconciled == original.last_reconciled
        assert loaded.stale == original.stale
