"""Tests for infrastructure/yaml/plan_repo.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.infrastructure.yaml.plan_repo import YamlPlanRepository
from harness.domain.identifiers import WaveId


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def repo() -> YamlPlanRepository:
    return YamlPlanRepository()


class TestSave:
    def test_save_delegates_to_plan(self, repo):
        """Save passes _save call through for a Plan instance."""
        MockPlanCls = type("MockPlan", (), {"_save": MagicMock()})
        with patch("harness.infrastructure.yaml.plan_repo.Plan", MockPlanCls):
            plan_instance = MagicMock(spec=MockPlanCls)
            repo.save(plan_instance)
            plan_instance._save.assert_called_once()

    def test_save_ignores_non_plan(self, repo):
        repo.save({"not": "a plan"})  # no error


class TestGet:
    def test_get_returns_none_if_no_file(self, repo, tmp_path):
        result = repo.get("missing-eng", tmp_path)
        assert result is None

    def test_get_returns_plan_from_disk(self, repo, tmp_path):
        """With a valid plan.yaml file, Plan.load is called."""
        eng_dir = tmp_path / ".harness" / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (eng_dir / "plan.yaml").write_text("waves: []\n")
        with patch("harness.infrastructure.yaml.plan_repo.Plan") as MockPlan:
            MockPlan.load.return_value = "mock_plan"
            result = repo.get("test-eng", tmp_path)
            MockPlan.load.assert_called_once_with(tmp_path, "test-eng")
            assert result == "mock_plan"


class TestCommitWave:
    def test_commit_wave_returns_false(self, repo):
        """Without root context, commit_wave returns False."""
        result = repo.commit_wave(WaveId("w1"))
        assert result is False


class TestSetWaveState:
    def test_set_wave_state_returns_false(self, repo):
        """Without root context, set_wave_state returns False."""
        result = repo.set_wave_state(WaveId("w1"), "completed")
        assert result is False
