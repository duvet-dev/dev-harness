"""Tests for phase/state_manager.py: PhaseStateManager."""

from __future__ import annotations

import pytest

from harness.phase.state_manager import PhaseStateManager


class TestPhaseStateManager:
    """PhaseStateManager tests."""

    def test_initial_empty(self) -> None:
        mgr = PhaseStateManager()
        assert mgr.list_phases() == []

    def test_set_and_get(self) -> None:
        mgr = PhaseStateManager()
        mgr.set_state("design", "artifact_count", 5)
        assert mgr.get_state("design", "artifact_count") == 5

    def test_get_default(self) -> None:
        mgr = PhaseStateManager()
        assert mgr.get_state("design", "nonexistent") is None
        assert mgr.get_state("design", "nonexistent", 42) == 42

    def test_has_state(self) -> None:
        mgr = PhaseStateManager()
        assert not mgr.has_state("design", "anything")
        mgr.set_state("design", "key1", 1)
        assert mgr.has_state("design", "key1")
        assert not mgr.has_state("design", "key2")

    def test_multiple_phases(self) -> None:
        mgr = PhaseStateManager()
        mgr.set_state("design", "count", 3)
        mgr.set_state("build", "count", 7)
        mgr.set_state("build", "status", "in_progress")

        assert mgr.get_state("design", "count") == 3
        assert mgr.get_state("build", "count") == 7
        assert mgr.get_state("build", "status") == "in_progress"
        assert mgr.get_state("test", "count") is None

        phases = mgr.list_phases()
        assert "design" in phases
        assert "build" in phases
        assert "test" not in phases

    def test_overwrite_state(self) -> None:
        mgr = PhaseStateManager()
        mgr.set_state("build", "step_index", 1)
        assert mgr.get_state("build", "step_index") == 1
        mgr.set_state("build", "step_index", 5)
        assert mgr.get_state("build", "step_index") == 5

    def test_clear_phase(self) -> None:
        mgr = PhaseStateManager()
        mgr.set_state("build", "count", 10)
        mgr.set_state("build", "status", "done")
        mgr.set_state("design", "count", 3)

        mgr.clear_phase("build")
        assert not mgr.has_state("build", "count")
        assert not mgr.has_state("build", "status")
        assert mgr.get_state("design", "count") == 3

        # Clearing non-existent phase is a no-op
        mgr.clear_phase("nonexistent")

    def test_list_keys(self) -> None:
        mgr = PhaseStateManager()
        assert mgr.list_keys("design") == []
        mgr.set_state("design", "a", 1)
        mgr.set_state("design", "b", 2)
        keys = mgr.list_keys("design")
        assert "a" in keys
        assert "b" in keys
        assert len(keys) == 2

    def test_isolated_phases(self) -> None:
        """State in one phase should not leak to another."""
        mgr = PhaseStateManager()
        mgr.set_state("design", "count", 1)
        mgr.set_state("build", "count", 2)
        assert mgr.get_state("design", "count") != mgr.get_state(
            "build", "count"
        )
