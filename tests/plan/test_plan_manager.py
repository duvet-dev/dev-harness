"""Tests for harness.plan.plan_manager."""

from pathlib import Path

import pytest
import yaml

from harness.plan.plan_manager import PlanManager, PLAN_YAML
from harness.plan.wave_model import Plan, Wave, WaveState, WaveType


@pytest.fixture
def project_dir(tmp_path) -> Path:
    return tmp_path


@pytest.fixture
def manager(project_dir) -> PlanManager:
    return PlanManager(project_dir, "test-engagement")


class TestPlanManager:
    def test_load_empty(self, manager):
        plan = manager.load()
        assert plan.waves == []

    def test_save_and_load(self, manager):
        plan = Plan()
        plan.add_wave(Wave(id="wave-01", title="Initial"))
        manager.save(plan)

        loaded = manager.load()
        assert len(loaded.waves) == 1
        assert loaded.waves[0].title == "Initial"

    def test_save_creates_yaml(self, manager, project_dir):
        plan = Plan()
        plan.add_wave(Wave(id="wave-01", title="Test"))
        manager.save(plan)

        yaml_path = project_dir / ".harness" / "engagements" / "test-engagement" / PLAN_YAML
        assert yaml_path.is_file()

        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        assert len(data["waves"]) == 1

    def test_save_creates_parent_dirs(self, manager, project_dir):
        """Save should create the .harness/engagements/slug/ directory."""
        manager.save(Plan())
        eng_dir = project_dir / ".harness" / "engagements" / "test-engagement"
        assert eng_dir.is_dir()

    def test_sync_to_md_creates_plan_md(self, manager, project_dir):
        plan = Plan()
        plan.add_wave(Wave(id="wave-01", title="Feature X"))
        manager.save(plan)

        md_path = project_dir / ".harness" / "engagements" / "test-engagement" / "plan.md"
        assert md_path.is_file()
        content = md_path.read_text()
        assert "Feature X" in content
        assert "wave-01" in content

    def test_sync_to_md_with_provenance(self, manager):
        from harness.plan.wave_model import WaveProvenance
        plan = Plan()
        wave = Wave(
            id="wave-02",
            title="Fix",
            type=WaveType.ADJUSTMENT,
            provenance=WaveProvenance(
                trigger_phase="testing",
                trigger_reason="Bug found",
                original_wave_id="wave-01",
            ),
        )
        plan.add_wave(wave)
        manager.save(plan)

        md_path = manager._plan_dir / "plan.md"
        content = md_path.read_text()
        assert "Bug found" in content

    def test_sync_to_md_with_priorities_and_constraints(self, manager):
        plan = Plan(
            priorities={"security": 0.9},
            constraints={"lang": "python"},
        )
        manager._plan_dir.mkdir(parents=True, exist_ok=True)
        manager.sync_to_md(plan=plan)

        md_path = manager._plan_dir / "plan.md"
        content = md_path.read_text()
        assert "security" in content
        assert "python" in content

    def test_add_wave_generates_id(self, manager):
        wave = manager.add_wave("First wave")
        assert wave.id == "wave-01"
        assert wave.title == "First wave"
        assert wave.type == WaveType.STANDARD

    def test_add_wave_increments_id(self, manager):
        manager.add_wave("First")
        wave2 = manager.add_wave("Second")
        assert wave2.id == "wave-02"

    def test_add_wave_multiple(self, manager):
        for i in range(5):
            manager.add_wave(f"Wave {i}")
        plan = manager.load()
        assert len(plan.waves) == 5

    def test_add_wave_with_provenance(self, manager):
        wave = manager.add_wave(
            "Fix bug",
            wave_type="adjustment",
            trigger_phase="testing",
            trigger_reason="Found during test",
            original_wave_id="wave-01",
        )
        assert wave.type == WaveType.ADJUSTMENT
        assert wave.provenance is not None
        assert wave.provenance.trigger_phase == "testing"

    def test_add_wave_adjustment_type(self, manager):
        wave = manager.add_wave("Refactor", wave_type="refactor")
        assert wave.type == WaveType.REFACTOR

    def test_add_wave_persists(self, manager):
        manager.add_wave("Test wave")

        # New manager loading same plan
        mgr2 = PlanManager(manager._root, "test-engagement")
        plan = mgr2.load()
        assert len(plan.waves) == 1

    def test_commit_wave_success(self, manager):
        manager.add_wave("Test wave")
        result = manager.commit_wave("wave-01")
        assert result is True

        plan = manager.load()
        wave = plan.get_wave("wave-01")
        assert wave.is_committed() is True

    def test_commit_wave_not_found(self, manager):
        result = manager.commit_wave("nonexistent")
        assert result is False

    def test_get_status(self, manager):
        manager.add_wave("First")
        manager.add_wave("Second", wave_type="adjustment")

        status = manager.get_status()
        assert len(status) == 2
        assert status[0]["title"] == "First"
        assert status[0]["is_committed"] is False
        assert status[0]["is_modifiable"] is True
        assert status[0]["has_provenance"] is False

    def test_get_status_after_commit(self, manager):
        manager.add_wave("Test")
        manager.commit_wave("wave-01")

        status = manager.get_status()
        assert status[0]["is_committed"] is True
        assert status[0]["is_modifiable"] is False

    def test_set_wave_state(self, manager):
        manager.add_wave("Test")
        result = manager.set_wave_state("wave-01", "in_progress")
        assert result is True

        plan = manager.load()
        assert plan.get_wave("wave-01").state == WaveState.IN_PROGRESS

    def test_set_wave_state_committed(self, manager):
        manager.add_wave("Test")
        result = manager.set_wave_state("wave-01", "committed")
        assert result is True

        plan = manager.load()
        wave = plan.get_wave("wave-01")
        assert wave.state == WaveState.COMMITTED
        assert wave.committed_at is not None

    def test_set_wave_state_not_found(self, manager):
        result = manager.set_wave_state("nonexistent", "committed")
        assert result is False

    def test_summary_empty(self, manager):
        summary = manager.summary()
        assert "No waves defined" in summary

    def test_summary_with_waves(self, manager):
        manager.add_wave("Feature A")
        manager.add_wave("Bug fix", wave_type="adjustment")
        manager.add_wave("Refactor core", wave_type="refactor")

        summary = manager.summary()
        assert "3 wave(s)" in summary
        assert "wave-01" in summary
        assert "adjustment" in summary.lower() or "ADJUSTMENT" in summary
        assert "refactor" in summary.lower() or "REFACTOR" in summary

    def test_summary_with_committed(self, manager):
        manager.add_wave("Feature")
        manager.commit_wave("wave-01")

        summary = manager.summary()
        assert "committed" in summary

    def test_summary_with_in_progress(self, manager):
        manager.add_wave("Active")
        manager.set_wave_state("wave-01", "in_progress")

        summary = manager.summary()
        assert "in-progress" in summary or "in_progress" in summary

    def test_sync_to_md_without_argument(self, manager):
        """sync_to_md called without plan argument loads from disk."""
        manager.add_wave("Test")
        md_path = manager._plan_dir / "plan.md"
        content = md_path.read_text()
        assert "Test" in content

    def test_load_from_non_existent_file(self, manager):
        plan = manager.load()
        assert isinstance(plan, Plan)
        assert plan.waves == []

    def test_save_multiple_times(self, manager):
        for i in range(3):
            manager.add_wave(f"Wave {i}")
        plan = manager.load()
        assert len(plan.waves) == 3
        assert plan.waves[-1].title == "Wave 2"


class TestPlanManagerEdgeCases:
    def test_engagement_slug_isolation(self, project_dir):
        """Different slugs should have independent plans."""
        mgr1 = PlanManager(project_dir, "engagement-a")
        mgr1.add_wave("A wave")

        mgr2 = PlanManager(project_dir, "engagement-b")
        plan_b = mgr2.load()
        assert len(plan_b.waves) == 0

    def test_add_wave_with_empty_title(self, manager):
        wave = manager.add_wave("")
        assert wave.title == ""

    def test_add_wave_handles_missing_ids(self, manager):
        """Should work even with previously saved waves that have no wave- prefix."""
        plan = Plan()
        plan.add_wave(Wave(id="custom-1", title="Custom"))
        manager.save(plan)

        wave = manager.add_wave("New wave")
        assert wave.id == "wave-01"

    def test_commit_wave_already_committed(self, manager):
        manager.add_wave("Test")
        manager.commit_wave("wave-01")
        result = manager.commit_wave("wave-01")  # commit again
        assert result is True
