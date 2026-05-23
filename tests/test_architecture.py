"""Tests for harness.config.architecture."""

from pathlib import Path

import pytest
import yaml

from harness.config.architecture import (
    ArchitectureGoal,
    DetectionRule,
    LayerGoal,
    load_architecture_goal,
    save_architecture_goal,
)


class TestLayerGoal:
    def test_defaults(self):
        lg = LayerGoal(name="domain")
        assert lg.name == "domain"
        assert lg.description == ""
        assert lg.allowed_imports == []

    def test_with_values(self):
        lg = LayerGoal(
            name="application",
            description="Orchestration layer",
            allowed_imports=["domain.*"],
        )
        assert lg.name == "application"
        assert lg.allowed_imports == ["domain.*"]


class TestDetectionRule:
    def test_default_severity(self):
        dr = DetectionRule(name="no_cycles")
        assert dr.severity == "warning"
        assert dr.description == ""
        assert dr.rule == ""

    def test_with_values(self):
        dr = DetectionRule(
            name="layer_violation",
            severity="error",
            description="Layer boundary crossed",
            rule="import not in allowed list",
        )
        assert dr.severity == "error"


class TestArchitectureGoal:
    def test_default_creates_layered(self):
        goal = ArchitectureGoal.default()
        assert goal.pattern == "layered"
        assert len(goal.layers) == 3
        assert goal.layers[0].name == "domain"
        assert goal.layers[1].name == "application"
        assert goal.layers[2].name == "adapters"

    def test_to_dict_round_trip(self):
        goal = ArchitectureGoal(
            pattern="hexagonal",
            description="Hexagonal architecture",
            layers=[
                LayerGoal(name="domain", description="Core"),
                LayerGoal(name="infra", description="Infrastructure"),
            ],
            detection_rules={
                "no_cycles": DetectionRule(
                    name="no_cycles",
                    severity="error",
                    description="No circular imports",
                    rule="no_circular_deps",
                ),
            },
        )
        d = goal.to_dict()
        restored = ArchitectureGoal.from_dict(d)
        assert restored.pattern == "hexagonal"
        assert restored.description == "Hexagonal architecture"
        assert len(restored.layers) == 2
        assert restored.layers[0].name == "domain"
        assert "no_cycles" in restored.detection_rules
        assert restored.detection_rules["no_cycles"].severity == "error"

    def test_from_dict_with_string_detection_rule(self):
        data = {
            "pattern": "layered",
            "layers": [],
            "detection_rules": {
                "simple_rule": "Just a description",
            },
        }
        goal = ArchitectureGoal.from_dict(data)
        assert "simple_rule" in goal.detection_rules
        assert goal.detection_rules["simple_rule"].description == "Just a description"

    def test_from_dict_empty(self):
        goal = ArchitectureGoal.from_dict({})
        assert goal.pattern == "layered"
        assert goal.layers == []

    def test_to_dict_without_detection_rules(self):
        goal = ArchitectureGoal.default()
        d = goal.to_dict()
        assert "detection_rules" in d
        assert d["detection_rules"] == {}


class TestLoadSave:
    def test_save_and_load_round_trip(self, tmp_path):
        goal = ArchitectureGoal.default()
        saved_path = save_architecture_goal(tmp_path, goal)
        assert saved_path.exists()
        assert saved_path.name == "architecture-goal.yaml"

        loaded = load_architecture_goal(tmp_path)
        assert loaded.pattern == goal.pattern
        assert len(loaded.layers) == len(goal.layers)

    def test_load_with_explicit_path(self, tmp_path):
        # Write a custom architecture goal to the .harness path
        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir()
        goal_file = harness_dir / "architecture-goal.yaml"
        goal = ArchitectureGoal(
            pattern="hexagonal",
            layers=[LayerGoal(name="domain")],
        )
        save_architecture_goal(tmp_path, goal)
        loaded = load_architecture_goal(tmp_path)
        assert loaded.pattern == "hexagonal"

    def test_load_falls_back_to_default_when_no_file(self, tmp_path):
        goal = load_architecture_goal(tmp_path)
        assert goal.pattern == "layered"
        assert len(goal.layers) == 3

    def test_save_engagement_override(self, tmp_path):
        goal = ArchitectureGoal(pattern="event-driven")
        slug = "test-engagement"
        saved_path = save_architecture_goal(tmp_path, goal, engagement_slug=slug)
        # Should be in engagements/<slug>/architecture-goal.yaml
        assert "engagements" in str(saved_path)
        assert slug in str(saved_path)
        assert saved_path.exists()

    def test_load_uses_engagement_override(self, tmp_path):
        # Save a project-level default
        project_goal = ArchitectureGoal.default()
        save_architecture_goal(tmp_path, project_goal)

        # Save an engagement override
        eng_goal = ArchitectureGoal(pattern="event-driven")
        save_architecture_goal(tmp_path, eng_goal, engagement_slug="my-eng")

        # Loading with slug should get the override
        loaded = load_architecture_goal(tmp_path, engagement_slug="my-eng")
        assert loaded.pattern == "event-driven"

    def test_load_engagement_falls_back_to_project(self, tmp_path):
        # Only save project-level
        project_goal = ArchitectureGoal(pattern="hexagonal")
        save_architecture_goal(tmp_path, project_goal)

        # No engagement file exists, should fall back to project
        loaded = load_architecture_goal(tmp_path, engagement_slug="nonexistent")
        assert loaded.pattern == "hexagonal"

    def test_load_nonexistent_engagement_no_project(self, tmp_path):
        """No project file, no engagement file → default."""
        loaded = load_architecture_goal(tmp_path, engagement_slug="ghost")
        assert loaded.pattern == "layered"

    def test_save_creates_parent_dirs(self, tmp_path):
        deep_path = tmp_path / "a" / "b" / "c"
        goal = ArchitectureGoal.default()
        # Override: use the path module directly; just test via save
        path = save_architecture_goal(deep_path, goal)
        assert path.parent.exists()
        assert path.exists()

    def test_load_malformed_yaml(self, tmp_path):
        """Malformed YAML should raise an error."""
        goal_path = tmp_path / ".harness" / "architecture-goal.yaml"
        goal_path.parent.mkdir(parents=True)
        goal_path.write_text(": broken yaml [")

        with pytest.raises(Exception):
            load_architecture_goal(tmp_path)


class TestLayerGoalEdgeCases:
    def test_empty_allowed_imports(self):
        lg = LayerGoal(name="domain", allowed_imports=[])
        assert lg.allowed_imports == []

    def test_multiple_allowed_imports(self):
        lg = LayerGoal(
            name="adapters",
            allowed_imports=["domain.*", "application.*", "infrastructure.*"],
        )
        assert len(lg.allowed_imports) == 3


class TestDetectionRuleEdgeCases:
    def test_error_severity(self):
        dr = DetectionRule(name="critical", severity="error")
        dr2 = DetectionRule(name="info", severity="info")
        assert dr.severity == "error"
        assert dr2.severity == "info"
