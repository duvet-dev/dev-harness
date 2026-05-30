"""Tests for harness.state.store."""

from __future__ import annotations

import pytest

from harness.state.store import Phase1StateStore


class TestPhase1StateStore:
    def test_create_engagement(self):
        store = Phase1StateStore()
        eng = store.create_engagement("Test engagement")
        assert eng.id.startswith("eng-")
        assert eng.description == "Test engagement"
        assert eng.status == "planning"
        assert eng.phase == "1"

    def test_create_engagement_sets_current(self):
        store = Phase1StateStore()
        eng = store.create_engagement("Test")
        assert store.current() == eng

    def test_get_engagement(self):
        store = Phase1StateStore()
        eng = store.create_engagement("Test")
        retrieved = store.get_engagement(eng.id)
        assert retrieved is not None
        assert retrieved.id == eng.id

    def test_get_engagement_missing(self):
        store = Phase1StateStore()
        assert store.get_engagement("nonexistent") is None

    def test_update_status(self):
        store = Phase1StateStore()
        eng = store.create_engagement("Test")
        store.update_status(eng.id, "active")
        updated = store.get_engagement(eng.id)
        assert updated is not None
        assert updated.status == "active"

    def test_update_status_raises_on_missing(self):
        store = Phase1StateStore()
        with pytest.raises(KeyError, match="not found"):
            store.update_status("nonexistent", "active")

    def test_current_returns_none_when_empty(self):
        store = Phase1StateStore()
        assert store.current() is None

    def test_all_returns_empty_on_init(self):
        store = Phase1StateStore()
        assert store.all() == []

    def test_all_returns_insertion_order(self):
        store = Phase1StateStore()
        eng1 = store.create_engagement("First")
        eng2 = store.create_engagement("Second")
        all_engs = store.all()
        assert len(all_engs) == 2
        assert all_engs[0].id == eng1.id
        assert all_engs[1].id == eng2.id

    def test_monotonic_ids(self):
        store = Phase1StateStore()
        for i in range(5):
            eng = store.create_engagement(f"Eng-{i}")
            expected_id = f"eng-{i + 1}"
            assert eng.id == expected_id
