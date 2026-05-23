"""Tests for harness.constitution.models."""

import pytest

from harness.constitution.models import (
    AnalysisConfig,
    AgentDef,
    BackendDef,
    BackendRef,
    CodingConfig,
    Constitution,
    ConstitutionError,
    GateConfig,
    PhilosophyConfig,
    ProjectInfo,
    default_constitution,
)


class TestProjectInfo:
    def test_minimal(self):
        info = ProjectInfo(name="my-project", template="backend-service")
        assert info.name == "my-project"
        assert info.template == "backend-service"
        assert info.description == ""

    def test_full(self):
        info = ProjectInfo(
            name="test", template="library", description="A library"
        )
        assert info.description == "A library"


class TestPhilosophyConfig:
    def test_defaults(self):
        pc = PhilosophyConfig()
        assert pc.requires_ddd is False
        assert pc.requires_clean_architecture is True
        assert pc.requires_hexagonal is True
        assert pc.strict_deps is True

    def test_custom(self):
        pc = PhilosophyConfig(
            requires_ddd=True, strict_deps=False, encoding_notes="test"
        )
        assert pc.requires_ddd is True
        assert pc.strict_deps is False
        assert pc.encoding_notes == "test"


class TestGateConfig:
    def test_defaults(self):
        gc = GateConfig()
        assert gc.default_mode == "auto"
        assert gc.available_modes == ("wild", "auto", "full")

    def test_custom(self):
        gc = GateConfig(default_mode="wild")
        assert gc.default_mode == "wild"


class TestBackendDef:
    def test_minimal(self):
        bd = BackendDef(name="test-backend", backend_type="cli")
        assert bd.name == "test-backend"
        assert bd.backend_type == "cli"
        assert bd.command == ""

    def test_full(self):
        bd = BackendDef(
            name="custom-llm",
            backend_type="cli",
            command="./generate.sh",
            provider="custom",
            model="llama3",
        )
        assert bd.command == "./generate.sh"
        assert bd.provider == "custom"


class TestCodingConfig:
    def test_defaults(self):
        cc = CodingConfig()
        assert cc.default_backend == "custom-llm"
        assert cc.backends == []

    def test_with_backends(self):
        cc = CodingConfig(
            default_backend="openai",
            backends=[
                BackendDef(name="openai", backend_type="api"),
            ],
        )
        assert cc.default_backend == "openai"
        assert len(cc.backends) == 1


class TestAnalysisConfig:
    def test_defaults(self):
        ac = AnalysisConfig()
        assert "on_summary" in ac.fast_scan_triggers
        assert "post_merge" in ac.fast_scan_triggers

    def test_custom(self):
        ac = AnalysisConfig(fast_scan_triggers=["on_demand"])
        assert ac.fast_scan_triggers == ["on_demand"]


class TestBackendRef:
    def test_defaults(self):
        br = BackendRef(backend_name="deepseek")
        assert br.backend_name == "deepseek"
        assert br.model_key == "default"
        assert br.fallbacks == []

    def test_with_fallbacks(self):
        br = BackendRef(
            backend_name="deepseek",
            model_key="pro",
            fallbacks=[{"backend": "openai", "model": "gpt-4o"}],
        )
        assert br.model_key == "pro"
        assert len(br.fallbacks) == 1


class TestAgentDef:
    def test_minimal(self):
        ad = AgentDef(name="planner", phase="planning")
        assert ad.name == "planner"
        assert ad.phase == "planning"
        assert ad.agent_type == "built-in"
        assert ad.backend == ""

    def test_with_backend(self):
        ad = AgentDef(
            name="coder",
            phase="implementation",
            backend="deepseek",
            model="default",
        )
        assert ad.backend == "deepseek"


class TestConstitution:
    def test_default_constitution(self):
        c = default_constitution()
        assert c.project.name == "my-project"
        assert c.project.template == "backend-service"
        assert len(c.agents) == 3
        assert c.agents[0].name == "planner"

    def test_default_constitution_custom_name(self):
        c = default_constitution(name="my-app", template="cli-tool")
        assert c.project.name == "my-app"
        assert c.project.template == "cli-tool"

    def test_to_dict_round_trip(self):
        original = Constitution(
            project=ProjectInfo(name="test", template="lib"),
            philosophy=PhilosophyConfig(strict_deps=False),
            gates=GateConfig(default_mode="wild"),
            analysis=AnalysisConfig(fast_scan_triggers=["on_summary"]),
            agents=[
                AgentDef(name="coder", phase="impl"),
            ],
        )
        d = original.to_dict()
        restored = Constitution.from_dict(d)
        assert restored.project.name == "test"
        assert restored.gates.default_mode == "wild"
        assert restored.philosophy.strict_deps is False
        assert len(restored.agents) == 1

    def test_from_dict_full(self):
        data = {
            "project": {
                "name": "my-service",
                "template": "backend-service",
                "description": "A backend service",
            },
            "philosophy": {
                "requires_ddd": True,
            },
            "gates": {
                "default_mode": "full",
            },
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
            "analysis": {
                "fast_scan_triggers": ["post_merge"],
            },
            "agents": [
                {"name": "planner", "phase": "planning"},
                {"name": "coder", "phase": "implementation"},
            ],
        }
        c = Constitution.from_dict(data)
        assert c.project.description == "A backend service"
        assert c.philosophy.requires_ddd is True
        assert len(c.agents) == 2

    def test_from_dict_unknown_field(self):
        data = {
            "project": {"name": "x", "template": "y"},
            "unknown_field": "should not be here",
        }
        with pytest.raises(ConstitutionError, match="Unknown field"):
            Constitution.from_dict(data)

    def test_from_dict_missing_required_field(self):
        data = {
            "project": {"template": "y"},
            # missing "name"
        }
        with pytest.raises(ConstitutionError, match="Missing required"):
            Constitution.from_dict(data)

    def test_to_dict_omits_defaults(self):
        c = Constitution(
            project=ProjectInfo(name="x", template="y"),
            philosophy=PhilosophyConfig(),
        )
        d = c.to_dict()
        # Philosophy has all defaults, should be omitted
        assert "philosophy" not in d
        assert d["project"]["name"] == "x"

    def test_from_dict_partial(self):
        data = {
            "project": {"name": "test", "template": "lib"},
            "agents": [
                {"name": "reviewer", "phase": "review"},
            ],
        }
        c = Constitution.from_dict(data)
        assert c.project.name == "test"
        assert c.gates.default_mode == "auto"  # default
        assert c.analysis.fast_scan_triggers is not None


class TestConstitutionError:
    def test_is_exception(self):
        err = ConstitutionError("test error")
        assert isinstance(err, Exception)
        assert str(err) == "test error"
