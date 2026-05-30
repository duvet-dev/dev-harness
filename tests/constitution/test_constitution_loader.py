"""Tests for harness.constitution.loader."""

from pathlib import Path

import pytest
import yaml

from harness.constitution.loader import load, scaffold, validate, write
from harness.constitution.models import (
    AgentDef,
    AnalysisConfig,
    BackendDef,
    CodingConfig,
    Constitution,
    ConstitutionError,
    GateConfig,
    PhilosophyConfig,
    ProjectInfo,
)


class TestLoad:
    def test_load_valid(self, tmp_path):
        path = tmp_path / "constitution.yaml"
        data = {
            "project": {"name": "test", "template": "backend-service"},
            "agents": [{"name": "coder", "phase": "impl"}],
        }
        with open(path, "w") as f:
            yaml.safe_dump(data, f)

        c = load(path)
        assert c.project.name == "test"
        assert c.project.template == "backend-service"
        assert len(c.agents) == 1

    def test_load_missing_file(self, tmp_path):
        with pytest.raises(ConstitutionError, match="not found"):
            load(tmp_path / "nonexistent.yaml")

    def test_load_malformed_yaml(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text(": broken yaml [")
        with pytest.raises(ConstitutionError, match="Malformed YAML"):
            load(path)

    def test_load_root_not_dict(self, tmp_path):
        path = tmp_path / "list.yaml"
        path.write_text("- item1\n- item2\n")
        with pytest.raises(ConstitutionError, match="mapping"):
            load(path)

    def test_load_empty_yaml(self, tmp_path):
        path = tmp_path / "empty.yaml"
        path.write_text("")
        with pytest.raises(ConstitutionError, match="mapping"):
            load(path)


class TestWrite:
    def test_write_atomic(self, tmp_path):
        path = tmp_path / "out.yaml"
        c = Constitution(
            project=ProjectInfo(name="test", template="backend-service"),
        )
        write(c, path, atomic=True)
        assert path.is_file()
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["project"]["name"] == "test"

    def test_write_non_atomic(self, tmp_path):
        path = tmp_path / "out.yaml"
        c = Constitution(
            project=ProjectInfo(name="test", template="backend-service"),
        )
        write(c, path, atomic=False)
        assert path.is_file()

    def test_write_round_trip(self, tmp_path):
        original = Constitution(
            project=ProjectInfo(name="my-app", template="cli-tool"),
            agents=[
                AgentDef(name="planner", phase="planning"),
                AgentDef(name="coder", phase="implementation"),
            ],
        )
        path = tmp_path / "round-trip.yaml"
        write(original, path)

        loaded = load(path)
        assert loaded.project.name == "my-app"
        assert loaded.project.template == "cli-tool"
        assert len(loaded.agents) == 2

    def test_write_creates_parent_dir(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "constitution.yaml"
        c = Constitution(
            project=ProjectInfo(name="test", template="lib"),
        )
        write(c, path)
        assert path.is_file()


class TestScaffold:
    def test_scaffold_backend_service(self, tmp_path):
        path = tmp_path / "constitution.yaml"
        c = scaffold("backend-service", "my-api", path)
        assert c.project.name == "my-api"
        assert c.project.template == "backend-service"
        assert path.is_file()

    def test_scaffold_with_overrides(self, tmp_path):
        path = tmp_path / "constitution.yaml"
        c = scaffold(
            "backend-service",
            "my-api",
            path,
            overrides={
                "project": {"description": "My custom API"},
                "gates": {"default_mode": "full"},
            },
        )
        assert c.project.description == "My custom API"
        assert c.gates.default_mode == "full"

    def test_scaffold_with_deep_override(self, tmp_path):
        path = tmp_path / "constitution.yaml"
        c = scaffold(
            "backend-service",
            "my-api",
            path,
            overrides={
                "coding": {
                    "default_backend": "openai",
                    "backends": [
                        {
                            "name": "openai",
                            "backend_type": "api",
                            "provider": "openai",
                            "model": "gpt-4o",
                        },
                    ],
                },
            },
        )
        assert c.coding.default_backend == "openai"
        assert len(c.coding.backends) == 1

    def test_scaffold_invalid_template(self, tmp_path):
        path = tmp_path / "constitution.yaml"
        with pytest.raises(KeyError, match="Unknown template"):
            scaffold("nonexistent-template", "my-app", path)

    def test_scaffold_with_empty_overrides(self, tmp_path):
        path = tmp_path / "constitution.yaml"
        c = scaffold("library", "my-lib", path, overrides={})
        assert c.project.name == "my-lib"

    def test_scaffold_overrides_add_new_keys(self, tmp_path):
        path = tmp_path / "constitution.yaml"
        c = scaffold(
            "cli-tool",
            "my-cli",
            path,
            overrides={
                "analysis": {
                    "fast_scan_triggers": ["on_summary", "on_push"],
                },
            },
        )
        assert "on_push" in c.analysis.fast_scan_triggers

    def test_scaffold_writes_file(self, tmp_path):
        path = tmp_path / "constitution.yaml"
        scaffold("library", "my-lib", path)
        assert path.is_file()
        with open(path) as f:
            raw = yaml.safe_load(f)
        assert raw["project"]["name"] == "my-lib"


class TestValidate:
    def test_validate_valid(self):
        c = Constitution(
            project=ProjectInfo(name="test", template="backend-service"),
        )
        warnings = validate(c)
        assert warnings == []

    def test_validate_empty_project_name(self):
        c = Constitution(
            project=ProjectInfo(name="", template="backend-service"),
        )
        warnings = validate(c)
        assert "project.name is empty" in warnings

    def test_validate_empty_template(self):
        c = Constitution(
            project=ProjectInfo(name="test", template=""),
        )
        warnings = validate(c)
        assert "project.template is empty" in warnings

    def test_validate_invalid_gate_mode(self):
        c = Constitution(
            project=ProjectInfo(name="test", template="backend-service"),
            gates=GateConfig(default_mode="invalid"),
        )
        warnings = validate(c)
        assert "gates.default_mode" in " ".join(warnings)

    def test_validate_duplicate_agent_names(self):
        c = Constitution(
            project=ProjectInfo(name="test", template="backend-service"),
            agents=[
                AgentDef(name="coder", phase="impl"),
                AgentDef(name="coder", phase="review"),
            ],
        )
        warnings = validate(c)
        assert any("duplicate" in w and "coder" in w for w in warnings)

    def test_validate_empty_agent_name(self):
        c = Constitution(
            project=ProjectInfo(name="test", template="backend-service"),
            agents=[
                AgentDef(name="", phase="impl"),
            ],
        )
        warnings = validate(c)
        assert any("empty name" in w for w in warnings)

    def test_validate_empty_agent_phase(self):
        c = Constitution(
            project=ProjectInfo(name="test", template="backend-service"),
            agents=[
                AgentDef(name="coder", phase=""),
            ],
        )
        warnings = validate(c)
        assert any("empty phase" in w for w in warnings)

    def test_validate_empty_backend_name(self):
        c = Constitution(
            project=ProjectInfo(name="test", template="backend-service"),
            coding=CodingConfig(
                default_backend="test",
                backends=[
                    BackendDef(name="", backend_type="cli"),
                ],
            ),
        )
        warnings = validate(c)
        assert any("empty name" in w for w in warnings)

    def test_validate_duplicate_backend_names(self):
        c = Constitution(
            project=ProjectInfo(name="test", template="backend-service"),
            coding=CodingConfig(
                default_backend="test",
                backends=[
                    BackendDef(name="b1", backend_type="cli"),
                    BackendDef(name="b1", backend_type="api"),
                ],
            ),
        )
        warnings = validate(c)
        assert any("duplicate" in w and "b1" in w for w in warnings)

    def test_validate_multiple_issues(self):
        c = Constitution(
            project=ProjectInfo(name="", template=""),
            gates=GateConfig(default_mode="bad"),
            agents=[
                AgentDef(name="", phase=""),
                AgentDef(name="", phase=""),
            ],
            coding=CodingConfig(
                default_backend="test",
                backends=[
                    BackendDef(name="", backend_type="cli"),
                    BackendDef(name="", backend_type="api"),
                ],
            ),
        )
        warnings = validate(c)
        # Should have multiple warnings
        assert len(warnings) >= 3
