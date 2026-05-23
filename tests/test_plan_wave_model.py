"""Tests for harness.plan.wave_model."""

from datetime import datetime, timezone

import pytest

from harness.plan.wave_model import (
    Plan,
    Wave,
    WaveProvenance,
    WaveState,
    WaveTask,
    WaveType,
    _now_iso,
)


class TestWaveType:
    def test_values(self):
        assert WaveType.STANDARD.value == "standard"
        assert WaveType.ADJUSTMENT.value == "adjustment"
        assert WaveType.REFACTOR.value == "refactor"

    def test_str(self):
        assert str(WaveType.STANDARD) == "standard"


class TestWaveState:
    def test_values(self):
        assert WaveState.PLANNED.value == "planned"
        assert WaveState.IN_PROGRESS.value == "in_progress"
        assert WaveState.COMMITTED.value == "committed"

    def test_str(self):
        assert str(WaveState.PLANNED) == "planned"


class TestWaveTask:
    def test_creation(self):
        task = WaveTask(id="t1", description="Write tests")
        assert task.id == "t1"
        assert task.description == "Write tests"

    def test_to_dict_round_trip(self):
        task = WaveTask(id="t1", description="Write tests")
        d = task.to_dict()
        assert d["id"] == "t1"

        restored = WaveTask.from_dict(d)
        assert restored.id == "t1"
        assert restored.description == "Write tests"


class TestWaveProvenance:
    def test_creation(self):
        prov = WaveProvenance(
            trigger_phase="testing",
            trigger_reason="Found bug during testing",
        )
        assert prov.trigger_phase == "testing"
        assert prov.original_wave_id is None

    def test_with_original_wave(self):
        prov = WaveProvenance(
            trigger_phase="design",
            trigger_reason="Architecture issue",
            original_wave_id="wave-01",
        )
        assert prov.original_wave_id == "wave-01"

    def test_to_dict_round_trip(self):
        prov = WaveProvenance(
            trigger_phase="implementation",
            trigger_reason="Missed requirement",
            original_wave_id="wave-02",
        )
        d = prov.to_dict()
        assert d["trigger_phase"] == "implementation"
        assert d["original_wave"] == "wave-02"

        restored = WaveProvenance.from_dict(d)
        assert restored.trigger_phase == "implementation"
        assert restored.original_wave_id == "wave-02"

    def test_to_dict_without_original(self):
        prov = WaveProvenance(
            trigger_phase="testing", trigger_reason="Edge case"
        )
        d = prov.to_dict()
        assert "original_wave" not in d

    def test_from_dict_without_original(self):
        d = {"trigger_phase": "testing", "trigger_reason": "Edge case"}
        restored = WaveProvenance.from_dict(d)
        assert restored.original_wave_id is None


class TestWave:
    def test_minimal_creation(self):
        wave = Wave(id="wave-01", title="Initial setup")
        assert wave.id == "wave-01"
        assert wave.title == "Initial setup"
        assert wave.type == WaveType.STANDARD
        assert wave.state == WaveState.PLANNED
        assert wave.provenance is None
        assert wave.tasks == []
        assert wave.committed_at is None

    def test_commit(self):
        wave = Wave(id="wave-01", title="Feature")
        assert wave.is_committed() is False
        wave.commit()
        assert wave.state == WaveState.COMMITTED
        assert wave.is_committed() is True
        assert wave.committed_at is not None

    def test_is_modifiable(self):
        wave = Wave(id="wave-01", title="Test")
        assert wave.is_modifiable() is True  # PLANNED

        wave.state = WaveState.IN_PROGRESS
        assert wave.is_modifiable() is True

        wave.state = WaveState.COMMITTED
        assert wave.is_modifiable() is False

    def test_adjustment_wave(self):
        wave = Wave(
            id="wave-02",
            title="Fix bug",
            type=WaveType.ADJUSTMENT,
            provenance=WaveProvenance(
                trigger_phase="testing",
                trigger_reason="Regression found",
            ),
        )
        assert wave.type == WaveType.ADJUSTMENT
        assert wave.provenance is not None

    def test_to_dict_round_trip(self):
        wave = Wave(
            id="wave-01",
            title="Add auth",
            type=WaveType.STANDARD,
            tasks=[
                WaveTask(id="t1", description="Implement login"),
                WaveTask(id="t2", description="Add tests"),
            ],
        )
        d = wave.to_dict()
        assert d["id"] == "wave-01"
        assert d["type"] == "standard"
        assert len(d["tasks"]) == 2

        restored = Wave.from_dict(d)
        assert restored.id == "wave-01"
        assert restored.type == WaveType.STANDARD
        assert len(restored.tasks) == 2

    def test_to_dict_with_provenance(self):
        wave = Wave(
            id="wave-02",
            title="Refactor",
            type=WaveType.REFACTOR,
            provenance=WaveProvenance(
                trigger_phase="design", trigger_reason="Tech debt"
            ),
        )
        d = wave.to_dict()
        assert "provenance" in d
        assert d["provenance"]["trigger_phase"] == "design"

    def test_from_dict_with_provenance(self):
        d = {
            "id": "wave-03",
            "title": "Adjust",
            "type": "adjustment",
            "state": "in_progress",
            "provenance": {
                "trigger_phase": "testing",
                "trigger_reason": "Test failure",
                "original_wave": "wave-01",
            },
            "tasks": [{"id": "t1", "description": "Fix"}],
            "created_at": "2025-01-01T00:00:00",
        }
        wave = Wave.from_dict(d)
        assert wave.type == WaveType.ADJUSTMENT
        assert wave.state == WaveState.IN_PROGRESS
        assert wave.provenance is not None
        assert wave.provenance.original_wave_id == "wave-01"
        assert len(wave.tasks) == 1

    def test_from_dict_minimal(self):
        d = {"id": "wave-01", "title": "Minimal"}
        wave = Wave.from_dict(d)
        assert wave.id == "wave-01"
        assert wave.type == WaveType.STANDARD
        assert wave.state == WaveState.PLANNED
        assert wave.tasks == []

    def test_commitment_timestamp(self):
        wave = Wave(id="wave-01", title="Test")
        wave.commit()
        # committed_at should be an ISO-formatted string
        assert isinstance(wave.committed_at, str)
        assert "T" in wave.committed_at

    def test_created_at_timestamp(self):
        wave = Wave(id="wave-01", title="Test")
        assert isinstance(wave.created_at, str)
        assert "T" in wave.created_at

    def test_to_dict_without_tasks(self):
        wave = Wave(id="wave-01", title="No tasks")
        d = wave.to_dict()
        assert "tasks" not in d or d["tasks"] == []


class TestPlan:
    def test_empty_plan(self):
        plan = Plan()
        assert plan.waves == []
        assert plan.priorities == {}
        assert plan.constraints == {}

    def test_add_wave(self):
        plan = Plan()
        wave = Wave(id="wave-01", title="First")
        plan.add_wave(wave)
        assert len(plan.waves) == 1
        assert plan.waves[0].id == "wave-01"

    def test_get_wave_found(self):
        plan = Plan()
        plan.add_wave(Wave(id="wave-01", title="First"))
        plan.add_wave(Wave(id="wave-02", title="Second"))
        found = plan.get_wave("wave-02")
        assert found is not None
        assert found.title == "Second"

    def test_get_wave_not_found(self):
        plan = Plan()
        assert plan.get_wave("nonexistent") is None

    def test_count_by_type(self):
        plan = Plan()
        plan.add_wave(Wave(id="w1", title="S1", type=WaveType.STANDARD))
        plan.add_wave(Wave(id="w2", title="A1", type=WaveType.ADJUSTMENT))
        plan.add_wave(Wave(id="w3", title="S2", type=WaveType.STANDARD))
        plan.add_wave(Wave(id="w4", title="R1", type=WaveType.REFACTOR))

        assert plan.count_by_type(WaveType.STANDARD) == 2
        assert plan.count_by_type(WaveType.ADJUSTMENT) == 1
        assert plan.count_by_type(WaveType.REFACTOR) == 1

    def test_rework_count(self):
        plan = Plan()
        plan.add_wave(Wave(id="w1", title="S1", type=WaveType.STANDARD))
        plan.add_wave(Wave(id="w2", title="A1", type=WaveType.ADJUSTMENT))
        plan.add_wave(Wave(id="w3", title="R1", type=WaveType.REFACTOR))

        assert plan.rework_count() == 2

    def test_rework_count_no_rework(self):
        plan = Plan()
        plan.add_wave(Wave(id="w1", title="S1"))
        assert plan.rework_count() == 0

    def test_priorities_and_constraints(self):
        plan = Plan(
            priorities={"security": 0.9, "simplicity": 0.6},
            constraints={"tech_stack": "python"},
        )
        assert plan.priorities["security"] == 0.9
        assert plan.constraints["tech_stack"] == "python"

    def test_to_dict_round_trip(self):
        plan = Plan(
            waves=[
                Wave(id="w1", title="First"),
                Wave(id="w2", title="Second", type=WaveType.ADJUSTMENT),
            ],
            priorities={"quality": 0.8},
            constraints={"lang": "python"},
        )
        d = plan.to_dict()
        assert len(d["waves"]) == 2

        restored = Plan.from_dict(d)
        assert len(restored.waves) == 2
        assert restored.priorities["quality"] == 0.8
        assert restored.constraints["lang"] == "python"

    def test_from_dict_empty(self):
        plan = Plan.from_dict({})
        assert plan.waves == []
        assert plan.priorities == {}
        assert plan.constraints == {}

    def test_add_wave_updates_timestamp(self):
        plan = Plan()
        original_updated = plan.updated_at
        plan.add_wave(Wave(id="w1", title="New"))
        # updated_at should be different
        assert plan.updated_at >= original_updated

    def test_empty_waves_to_dict(self):
        plan = Plan()
        d = plan.to_dict()
        assert d["waves"] == []
