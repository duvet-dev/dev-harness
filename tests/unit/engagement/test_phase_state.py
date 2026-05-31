"""Tests for harness.domain.engagement.phase_state."""

import pytest
import yaml

from harness.domain.engagement.phase_state import (
    InvalidTransitionError,
    PhaseNotFoundError,
    PhaseRecord,
    PhaseState,
    PhaseStateManager,
)


class TestPhaseState:
    def test_values(self):
        assert PhaseState.NOT_STARTED.value == "not_started"
        assert PhaseState.ACTIVE.value == "active"
        assert PhaseState.COMPLETED.value == "completed"
        assert PhaseState.PAUSED.value == "paused"
        assert PhaseState.FEEDBACK_SENT.value == "feedback_sent"
        assert PhaseState.FEEDBACK_WAIT.value == "feedback_wait"


class TestPhaseRecord:
    def test_default_state(self):
        rec = PhaseRecord()
        assert rec.state == PhaseState.NOT_STARTED

    def test_to_dict_includes_only_set_fields(self):
        rec = PhaseRecord(state=PhaseState.ACTIVE)
        d = rec.to_dict()
        assert d["state"] == "active"
        assert "completed_at" not in d

    def test_to_dict_includes_timestamps(self):
        rec = PhaseRecord(
            state=PhaseState.COMPLETED,
            completed_at="2026-05-23T12:00:00",
            checkpoint_ref="cp-01",
            feedback_target="build",
        )
        d = rec.to_dict()
        assert d["completed_at"] == "2026-05-23T12:00:00"
        assert d["checkpoint_ref"] == "cp-01"
        assert d["feedback_target"] == "build"

    def test_from_dict_roundtrip(self):
        data = {
            "state": "paused",
            "paused_at": "2026-05-23T12:00:00",
            "checkpoint_ref": "cp-01",
        }
        rec = PhaseRecord.from_dict(data)
        assert rec.state == PhaseState.PAUSED
        assert rec.paused_at == "2026-05-23T12:00:00"
        assert rec.checkpoint_ref == "cp-01"


class TestPhaseStateManager:
    def test_ensure_phase_creates_new(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        rec = mgr.ensure_phase("design")
        assert rec.state == PhaseState.NOT_STARTED
        assert "design" in mgr.list_phases()

    def test_ensure_phase_returns_existing(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        rec1 = mgr.ensure_phase("design")
        rec2 = mgr.ensure_phase("design")
        assert rec1 is rec2

    def test_get_state_creates_phase(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        state = mgr.get_state("build")
        assert state == PhaseState.NOT_STARTED

    def test_transition_not_started_to_active(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        mgr.ensure_phase("design")
        mgr.transition("design", PhaseState.ACTIVE)
        assert mgr.get_state("design") == PhaseState.ACTIVE

    def test_transition_active_to_completed(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        mgr.transition("design", PhaseState.ACTIVE)
        mgr.transition("design", PhaseState.COMPLETED)
        assert mgr.get_state("design") == PhaseState.COMPLETED
        rec = mgr.list_phases()["design"]
        assert rec.completed_at is not None

    def test_transition_active_to_paused(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        mgr.transition("design", PhaseState.ACTIVE)
        mgr.transition("design", PhaseState.PAUSED)
        assert mgr.get_state("design") == PhaseState.PAUSED
        assert mgr.list_phases()["design"].paused_at is not None

    def test_transition_paused_to_active_clears_paused_at(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        mgr.transition("design", PhaseState.ACTIVE)
        mgr.transition("design", PhaseState.PAUSED)
        mgr.transition("design", PhaseState.ACTIVE)
        rec = mgr.list_phases()["design"]
        assert rec.state == PhaseState.ACTIVE
        assert rec.paused_at is None

    def test_transition_completed_is_terminal(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        mgr.transition("design", PhaseState.ACTIVE)
        mgr.transition("design", PhaseState.COMPLETED)
        with pytest.raises(InvalidTransitionError):
            mgr.transition("design", PhaseState.ACTIVE)

    def test_invalid_transition_raises(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        with pytest.raises(InvalidTransitionError):
            mgr.transition("design", PhaseState.COMPLETED)  # NOT_STARTED → COMPLETED invalid

    def test_invalid_transition_error_message(self):
        err = InvalidTransitionError(PhaseState.NOT_STARTED, PhaseState.COMPLETED, "design")
        assert "design" in str(err)
        assert "not_started" in str(err)
        assert "completed" in str(err)

    def test_mark_feedback_sent(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        mgr.transition("design", PhaseState.ACTIVE)
        rec = mgr.mark_feedback_sent("design", "build", "cp-01")
        assert rec.state == PhaseState.FEEDBACK_SENT
        assert rec.feedback_target == "build"
        assert rec.checkpoint_ref == "cp-01"

    def test_clear_feedback(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        mgr.transition("design", PhaseState.ACTIVE)
        mgr.mark_feedback_sent("design", "build", "cp-01")
        mgr.clear_feedback("design")
        rec = mgr.list_phases()["design"]
        assert rec.feedback_target is None
        assert rec.checkpoint_ref is None

    def test_reset_clears_all_fields(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        mgr.transition("design", PhaseState.ACTIVE)
        mgr.transition("design", PhaseState.COMPLETED)
        mgr.reset("design")
        rec = mgr.list_phases()["design"]
        assert rec.state == PhaseState.NOT_STARTED
        assert rec.completed_at is None
        assert rec.paused_at is None

    def test_persistence_writes_and_reads(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        mgr.transition("design", PhaseState.ACTIVE)
        mgr.transition("design", PhaseState.COMPLETED)
        mgr.save()

        # New manager loads from file
        mgr2 = PhaseStateManager(tmp_path, "test-eng")
        phases = mgr2.list_phases()
        assert "design" in phases
        assert phases["design"].state == PhaseState.COMPLETED

    def test_load_from_missing_file(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        # No phases.yaml should exist yet
        assert mgr.list_phases() == {}

    def test_state_path_property(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        expected = tmp_path / ".harness" / "engagements" / "test-eng" / "phases.yaml"
        assert mgr.state_path == expected

    def test_save_writes_valid_yaml(self, tmp_path):
        mgr = PhaseStateManager(tmp_path, "test-eng")
        mgr.transition("design", PhaseState.ACTIVE)
        mgr.save()
        data = yaml.safe_load(mgr.state_path.read_text())
        assert "phases" in data
        assert data["phases"]["design"]["state"] == "active"

    def test_load_corrupt_yaml_graceful(self, tmp_path):
        """Corrupt YAML in state file doesn't crash _load() (lines 238-239)."""
        mgr = PhaseStateManager(tmp_path, "test-eng")
        target_dir = mgr.state_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        mgr.state_path.write_text("invalid: [yaml: broken: [[")
        # Force re-load by creating a new manager
        mgr2 = PhaseStateManager(tmp_path, "test-eng")
        assert mgr2.list_phases() == {}
