"""Tests for phase/bootstrap.py — bootstrap_phases, bootstrap_and_register.

Covers:
- Loading phases from YAML
- Fallback to default phases when YAML is absent
- Template expansion via StepTemplateRegistry
- Inline step conversion (agents, team, loop, phase)
- Mutual exclusivity validation on step definitions
- Error handling for missing/malformed YAML
- bootstrap_and_register integration with PhaseOrchestrator
- Template registration from step_templates.yaml
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from harness.errors import UnknownTemplateError, StepMutualExclusionError
from harness.phase.bootstrap import (
    _convert_inline_step,
    _convert_template_step,
    _load_yaml_phases,
    _load_templates_yaml,
    _parse_phases_yaml,
    bootstrap_phases,
    bootstrap_and_register,
    _DEFAULT_PHASES,
)
from harness.phase.model import (
    ConvergenceConfig,
    LoopConfig,
    Phase,
    Step,
)
from harness.phase.template_registry import StepTemplateRegistry
from harness.team.defaults import get_builtin_teams
from harness.team.registry import TeamRegistry


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def team_registry() -> TeamRegistry:
    return TeamRegistry(builtin=get_builtin_teams())


@pytest.fixture
def template_registry(team_registry: TeamRegistry) -> StepTemplateRegistry:
    return StepTemplateRegistry(team_registry=team_registry)


@pytest.fixture
def temp_dir() -> Path:
    """Create a temporary directory for YAML test files."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    """Create a mock PhaseOrchestrator-like object."""
    mock = MagicMock()
    mock.register_phases = MagicMock()
    mock.register_phase = MagicMock()
    return mock


# ── _load_yaml_phases ────────────────────────────────────────────────────


class TestLoadYamlPhases:
    """Tests for _load_yaml_phases()."""

    def test_load_valid_yaml(self, temp_dir: Path) -> None:
        """Loading valid phases.yaml returns the phases list."""
        path = temp_dir / "phases.yaml"
        data = {
            "phases": [
                {"name": "build", "lead_agent": "coding-agent",
                 "steps": [{"agents": ["coder"], "output": "impl"}]},
            ]
        }
        with open(path, "w") as f:
            yaml.dump(data, f)
        result = _load_yaml_phases(path)
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "build"

    def test_file_not_found(self, temp_dir: Path) -> None:
        """Missing file returns None."""
        path = temp_dir / "nonexistent.yaml"
        result = _load_yaml_phases(path)
        assert result is None

    def test_empty_yaml(self, temp_dir: Path) -> None:
        """Empty file returns None."""
        path = temp_dir / "phases.yaml"
        path.write_text("")
        result = _load_yaml_phases(path)
        assert result is None

    def test_missing_phases_key(self, temp_dir: Path) -> None:
        """YAML without 'phases' key returns None."""
        path = temp_dir / "phases.yaml"
        data = {"not_phases": []}
        with open(path, "w") as f:
            yaml.dump(data, f)
        result = _load_yaml_phases(path)
        assert result is None

    def test_empty_phases_list(self, temp_dir: Path) -> None:
        """Empty 'phases' list returns None."""
        path = temp_dir / "phases.yaml"
        data = {"phases": []}
        with open(path, "w") as f:
            yaml.dump(data, f)
        result = _load_yaml_phases(path)
        assert result is None

    def test_corrupt_yaml(self, temp_dir: Path) -> None:
        """Corrupt YAML returns None."""
        path = temp_dir / "phases.yaml"
        path.write_text("{{ invalid_yaml")
        result = _load_yaml_phases(path)
        assert result is None


# ── _convert_inline_step ─────────────────────────────────────────────────


class TestConvertInlineStep:
    """Tests for _convert_inline_step()."""

    def test_agents_step(self) -> None:
        """Step with agents list produces correct Step."""
        step = _convert_inline_step({
            "agents": ["architect", "reviewer"],
            "output": "design-doc",
            "parallel": True,
        })
        assert step.agents == ["architect", "reviewer"]
        assert step.output == ["design-doc"]
        assert step.parallel is True
        assert step.team is None
        assert step.loop is None
        assert step.phase is None

    def test_team_step(self) -> None:
        """Step with team reference produces correct Step."""
        step = _convert_inline_step({
            "team": "coding",
            "output": "implementation",
            "lead": "coding-agent",
        })
        assert step.team == "coding"
        assert step.output == ["implementation"]
        assert step.lead == "coding-agent"
        assert step.agents is None

    def test_loop_step(self) -> None:
        """Step with loop config produces correct Step."""
        step = _convert_inline_step({
            "loop": {
                "count": 3,
                "convergence": {
                    "strategy": "gate_judgment",
                    "max_iterations": 5,
                    "gate_agent": "architect",
                },
                "description": "Design iteration",
            },
            "output": "design-proposal",
        })
        assert step.loop is not None
        assert step.loop.count == 3
        assert step.loop.convergence is not None
        assert step.loop.convergence.strategy == "gate_judgment"
        assert step.loop.convergence.max_iterations == 5
        assert step.loop.convergence.gate_agent == "architect"
        assert step.loop.description == "Design iteration"
        assert step.output == ["design-proposal"]

    def test_loop_step_no_convergence(self) -> None:
        """Step with loop but no convergence uses defaults."""
        step = _convert_inline_step({
            "loop": {"count": 2},
        })
        assert step.loop is not None
        assert step.loop.count == 2
        assert step.loop.convergence is None

    def test_phase_step(self) -> None:
        """Step with phase jump produces correct Step."""
        step = _convert_inline_step({
            "phase": "design",
            "output": "design-review",
        })
        assert step.phase == "design"
        assert step.output == ["design-review"]
        assert step.agents is None
        assert step.team is None

    def test_input_as_string(self) -> None:
        """Input as string is converted to single-element list."""
        step = _convert_inline_step({
            "agents": ["tester"],
            "input": "implementation",
            "output": "test-results",
        })
        assert step.input == ["implementation"]

    def test_input_as_list(self) -> None:
        """Input as list preserves raw string values."""
        step = _convert_inline_step({
            "agents": ["tester"],
            "input": ["implementation", "spec"],
            "output": "test-results",
        })
        assert step.input == ["implementation", "spec"]

    def test_no_input(self) -> None:
        """Step without input leaves input as None."""
        step = _convert_inline_step({
            "agents": ["tester"],
            "output": "results",
        })
        assert step.input is None

    def test_mutual_exclusivity_violation_two(self) -> None:
        """Step with both agents and team raises error."""
        with pytest.raises(StepMutualExclusionError):
            _convert_inline_step({
                "agents": ["architect"],
                "team": "coding",
                "output": "output",
            })

    def test_mutual_exclusivity_violation_none(self) -> None:
        """Step with no agents/team/loop/phase raises error."""
        with pytest.raises(StepMutualExclusionError):
            _convert_inline_step({
                "output": "output",
            })

    def test_template_field_triggers_mutual_exclusivity(self) -> None:
        """Step with both template and agents raises error."""
        with pytest.raises(StepMutualExclusionError):
            _convert_inline_step({
                "template": "full-code-review",
                "agents": ["architect"],
            })

    def test_all_step_fields_preserved(self) -> None:
        """All optional step fields are preserved."""
        step = _convert_inline_step({
            "agents": ["agent"],
            "output": "result",
            "role": "critic",
            "action": "review",
            "auto": True,
            "max_retries": 3,
            "serial_lead": "lead-agent",
        })
        assert step.role == "critic"
        assert step.action == "review"
        assert step.auto is True
        assert step.max_retries == 3
        assert step.serial_lead == "lead-agent"


# ── _convert_template_step ────────────────────────────────────────────────


class TestConvertTemplateStep:
    """Tests for _convert_template_step()."""

    def test_expand_simple_template(self, template_registry: StepTemplateRegistry) -> None:
        """Template with agents is expanded correctly."""
        from harness.phase.template import StepTemplate
        template = StepTemplate(
            name="quick-scan",
            agents=["security-critic"],
            output="security-report",
        )
        template_registry.register(template)

        step = _convert_template_step(
            {"template": "quick-scan"},
            template_registry,
        )
        assert step.agents == ["security-critic"]
        assert step.output == ["security-report"]

    def test_expand_team_template(self, template_registry: StepTemplateRegistry) -> None:
        """Template with team is expanded correctly."""
        from harness.phase.template import StepTemplate
        template = StepTemplate(
            name="arch-review",
            team="architecture",
            output="consolidated-review",
        )
        template_registry.register(template)

        step = _convert_template_step(
            {"template": "arch-review"},
            template_registry,
        )
        assert step.team == "architecture"

    def test_no_registry_raises(self) -> None:
        """Template expansion without registry raises."""
        with pytest.raises(UnknownTemplateError):
            _convert_template_step({"template": "any"}, None)

    def test_unknown_template_raises(self) -> None:
        """Unknown template name raises."""
        registry = StepTemplateRegistry()
        with pytest.raises(UnknownTemplateError):
            _convert_template_step(
                {"template": "nonexistent"},
                registry,
            )


# ── _parse_phases_yaml ────────────────────────────────────────────────────


class TestParsePhasesYaml:
    """Tests for _parse_phases_yaml()."""

    def test_parse_single_phase(self) -> None:
        """Single phase with one step is parsed correctly."""
        raw = [
            {
                "name": "test-phase",
                "lead_agent": "lead",
                "chat_agent": "chat",
                "steps": [{"agents": ["architect"], "output": "result"}],
            }
        ]
        phases = _parse_phases_yaml(raw)
        assert len(phases) == 1
        assert phases[0].name == "test-phase"
        assert phases[0].lead_agent == "lead"
        assert phases[0].chat_agent == "chat"
        assert len(phases[0].steps) == 1

    def test_parse_default_chat_agent(self) -> None:
        """Phase without chat_agent uses default."""
        raw = [
            {
                "name": "test",
                "lead_agent": "lead",
                "steps": [{"agents": ["architect"]}],
            }
        ]
        phases = _parse_phases_yaml(raw)
        assert phases[0].chat_agent == "technical-conversationalist"

    def test_parse_reentry(self) -> None:
        """Phase with reentry field is parsed correctly."""
        raw = [
            {
                "name": "test",
                "lead_agent": "lead",
                "chat_agent": "chat",
                "reentry": "restart",
                "steps": [{"agents": ["architect"]}],
            }
        ]
        phases = _parse_phases_yaml(raw)
        assert phases[0].reentry == "restart"

    def test_parse_multiple_phases(self) -> None:
        """Multiple phases are parsed correctly."""
        raw = [
            {
                "name": "discover",
                "lead_agent": "agent-a",
                "chat_agent": "chat",
                "steps": [{"agents": ["a"]}],
            },
            {
                "name": "design",
                "lead_agent": "agent-b",
                "chat_agent": "chat",
                "steps": [{"agents": ["b"]}],
            },
        ]
        phases = _parse_phases_yaml(raw)
        assert len(phases) == 2
        assert phases[0].name == "discover"
        assert phases[1].name == "design"

    def test_parse_empty_steps(self) -> None:
        """Phase with no steps produces empty steps list."""
        raw = [
            {
                "name": "empty-phase",
                "lead_agent": "lead",
                "chat_agent": "chat",
                "steps": [],
            }
        ]
        phases = _parse_phases_yaml(raw)
        assert len(phases[0].steps) == 0

    def test_no_steps_key(self) -> None:
        """Phase without steps key uses empty list."""
        raw = [
            {
                "name": "no-steps",
                "lead_agent": "lead",
                "chat_agent": "chat",
            }
        ]
        phases = _parse_phases_yaml(raw)
        assert phases[0].steps == []

    def test_expand_templates(self, template_registry: StepTemplateRegistry) -> None:
        """Templates in steps are expanded when registry is provided."""
        from harness.phase.template import StepTemplate
        template_registry.register(
            StepTemplate(
                name="quick-scan",
                agents=["security-critic"],
                output="security-report",
            )
        )
        raw = [
            {
                "name": "security",
                "lead_agent": "lead",
                "chat_agent": "chat",
                "steps": [
                    {"template": "quick-scan"},
                    {"agents": ["architect"], "output": "final"},
                ],
            }
        ]
        phases = _parse_phases_yaml(raw, template_registry)
        assert len(phases[0].steps) == 2
        assert phases[0].steps[0].agents == ["security-critic"]
        assert phases[0].steps[1].agents == ["architect"]


# ── _load_templates_yaml ──────────────────────────────────────────────────


class TestLoadTemplatesYaml:
    """Tests for _load_templates_yaml()."""

    def test_load_valid_templates(self, temp_dir: Path) -> None:
        """Valid step_templates.yaml returns template objects."""
        path = temp_dir / "step_templates.yaml"
        data = {
            "step_templates": [
                {
                    "name": "test-tpl",
                    "agents": ["agent-a"],
                    "output": "result",
                }
            ]
        }
        with open(path, "w") as f:
            yaml.dump(data, f)
        result = _load_templates_yaml(path)
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "test-tpl"

    def test_file_not_found(self, temp_dir: Path) -> None:
        """Missing file returns None."""
        path = temp_dir / "nonexistent.yaml"
        result = _load_templates_yaml(path)
        assert result is None

    def test_empty_templates(self, temp_dir: Path) -> None:
        """File without step_templates key returns None."""
        path = temp_dir / "step_templates.yaml"
        with open(path, "w") as f:
            yaml.dump({"other": []}, f)
        result = _load_templates_yaml(path)
        assert result is None

    def test_non_list_templates(self, temp_dir: Path) -> None:
        """step_templates key that is not a list returns None."""
        path = temp_dir / "step_templates.yaml"
        with open(path, "w") as f:
            yaml.dump({"step_templates": "not_a_list"}, f)
        result = _load_templates_yaml(path)
        assert result is None

    def test_load_corrupt_yaml(self, temp_dir: Path) -> None:
        """Corrupt YAML returns None."""
        path = temp_dir / "step_templates.yaml"
        path.write_text("{{{{ invalid")
        result = _load_templates_yaml(path)
        assert result is None

    def test_template_with_input(self, temp_dir: Path) -> None:
        """Template with input field is parsed correctly."""
        path = temp_dir / "step_templates.yaml"
        data = {
            "step_templates": [
                {
                    "name": "input-test",
                    "agents": ["agent-a"],
                    "input": "implementation",
                    "output": "result",
                },
                {
                    "name": "input-list",
                    "agents": ["agent-b"],
                    "input": ["impl", "spec"],
                    "output": "result",
                },
            ]
        }
        with open(path, "w") as f:
            yaml.dump(data, f)
        result = _load_templates_yaml(path)
        assert result is not None
        assert len(result) == 2
        # First template: string input converted to list
        assert result[0].input == ["implementation"]
        # Second template: list input preserved
        assert result[1].input == ["impl", "spec"]

    def test_loop_templates(self, temp_dir: Path) -> None:
        """Critic loop template is parsed correctly."""
        path = temp_dir / "step_templates.yaml"
        data = {
            "step_templates": [
                {
                    "name": "review-loop",
                    "loop": {
                        "convergence": {
                            "strategy": "gate_judgment",
                            "max_iterations": 3,
                            "gate_agent": "reviewer",
                        },
                        "steps": [
                            {"agents": ["reviewer"], "role": "produce",
                             "output": "report"},
                            {"agents": ["critic"], "role": "critique",
                             "input": "report", "output": "review"},
                        ],
                    },
                }
            ]
        }
        with open(path, "w") as f:
            yaml.dump(data, f)
        result = _load_templates_yaml(path)
        assert result is not None
        assert len(result) == 1
        tpl = result[0]
        assert tpl.name == "review-loop"
        assert tpl.loop is not None
        assert tpl.loop.convergence is not None
        assert tpl.loop.convergence.strategy == "gate_judgment"
        assert len(tpl.steps) == 2
        assert tpl.steps[0].agents == ["reviewer"]


# ── bootstrap_phases (integration) ────────────────────────────────────────


class TestBootstrapPhases:
    """Integration tests for bootstrap_phases()."""

    def test_bootstrap_with_yaml(self, temp_dir: Path) -> None:
        """Loading phases from YAML returns correct Phase objects."""
        harness_dir = temp_dir / ".harness"
        harness_dir.mkdir()
        phases_path = harness_dir / "phases.yaml"
        data = {
            "phases": [
                {
                    "name": "custom",
                    "lead_agent": "custom-lead",
                    "chat_agent": "custom-chat",
                    "steps": [{"agents": ["custom-agent"], "output": "result"}],
                }
            ]
        }
        with open(phases_path, "w") as f:
            yaml.dump(data, f)

        old_cwd = Path.cwd()
        try:
            (temp_dir / "old_cwd")

            phases = bootstrap_phases(
                template_registry=None,
                phases_path=phases_path,
            )
        finally:
            pass

        assert len(phases) == 1
        assert phases[0].name == "custom"
        assert phases[0].lead_agent == "custom-lead"

    def test_bootstrap_default_fallback(self) -> None:
        """Bootstrap with no YAML falls back to built-in defaults."""
        # Use a nonexistent path to force fallback
        with tempfile.TemporaryDirectory() as d:
            nonexistent = Path(d) / "nope.yaml"
            phases = bootstrap_phases(
                template_registry=None,
                phases_path=nonexistent,
            )
            assert len(phases) > 0
            # Default phases should include discover, design, build, etc.
            names = [p.name for p in phases]
            assert "discover" in names
            assert "design" in names
            assert "build" in names

    def test_bootstrap_with_templates(
        self, team_registry: TeamRegistry, temp_dir: Path
    ) -> None:
        """Bootstrap loads templates from YAML and expands them."""
        harness_dir = temp_dir / ".harness"
        harness_dir.mkdir()

        # Write step_templates.yaml
        templates_path = harness_dir / "step_templates.yaml"
        tpl_data = {
            "step_templates": [
                {
                    "name": "quick-scan",
                    "agents": ["security-critic"],
                    "output": "security-report",
                }
            ]
        }
        with open(templates_path, "w") as f:
            yaml.dump(tpl_data, f)

        # Write phases.yaml that uses the template
        phases_path = harness_dir / "phases.yaml"
        phase_data = {
            "phases": [
                {
                    "name": "security-scan",
                    "lead_agent": "security-agent",
                    "chat_agent": "chat",
                    "steps": [
                        {"template": "quick-scan"},
                    ],
                }
            ]
        }
        with open(phases_path, "w") as f:
            yaml.dump(phase_data, f)

        template_registry = StepTemplateRegistry(team_registry=team_registry)

        phases = bootstrap_phases(
            template_registry=template_registry,
            phases_path=phases_path,
            templates_path=templates_path,
        )

        assert len(phases) == 1
        assert phases[0].name == "security-scan"
        assert len(phases[0].steps) == 1
        # Step should be expanded from template
        assert phases[0].steps[0].agents == ["security-critic"]

    def test_bootstrap_empty_phases_yaml(self, temp_dir: Path) -> None:
        """Empty phases.yaml falls back to defaults."""
        harness_dir = temp_dir / ".harness"
        harness_dir.mkdir()
        phases_path = harness_dir / "phases.yaml"
        phases_path.write_text("phases: []")

        phases = bootstrap_phases(phases_path=phases_path)
        # Falls back to defaults
        assert len(phases) > 0

    def test_bootstrap_default_phases_content(self) -> None:
        """Default phases have expected structure."""
        # Use nonexistent path to force default fallback
        with tempfile.TemporaryDirectory() as d:
            nonexistent = Path(d) / "nope.yaml"
            phases = bootstrap_phases(phases_path=nonexistent)
            assert len(phases) == 6
            for p in phases:
                assert p.name
                assert p.lead_agent
                assert p.chat_agent

    def test_bootstrap_with_non_existent_cwd_harness(
        self, temp_dir: Path
    ) -> None:
        """Bootstrap in dir without .harness/ falls back to defaults."""
        # This tests the default path resolution when no phases_path given
        # phases.yaml won't exist, so it falls back to defaults
        old_cwd = Path.cwd()
        try:
            phases = bootstrap_phases()
        finally:
            pass
        assert len(phases) > 0


# ── bootstrap_and_register ────────────────────────────────────────────────


class TestBootstrapAndRegister:
    """Tests for bootstrap_and_register()."""

    def test_register_on_orchestrator(
        self, mock_orchestrator: MagicMock
    ) -> None:
        """Phases are registered on the orchestrator."""
        with tempfile.TemporaryDirectory() as d:
            nonexistent = Path(d) / "nope.yaml"
            bootstrap_and_register(
                orchestrator=mock_orchestrator,
                phases_path=nonexistent,
            )
        # register_phases should have been called with a list
        mock_orchestrator.register_phases.assert_called_once()
        args = mock_orchestrator.register_phases.call_args[0]
        assert len(args) == 1
        assert isinstance(args[0], list)
        assert len(args[0]) > 0
        assert isinstance(args[0][0], Phase)

    def test_empty_orchestrator_raises(
        self, temp_dir: Path
    ) -> None:
        """bootstrap_and_register with no orchestrator raises."""
        with pytest.raises(Exception):
            bootstrap_and_register(
                orchestrator=None,  # type: ignore
                phases_path=temp_dir / "nope.yaml",
            )

    def test_template_duplicate_skip(
        self, temp_dir: Path, team_registry: TeamRegistry
    ) -> None:
        """Duplicate template registration logs debug and continues."""
        from harness.phase.template import StepTemplate

        harness_dir = temp_dir / ".harness"
        harness_dir.mkdir()

        # Write templates with duplicate names
        templates_path = harness_dir / "step_templates.yaml"
        with open(templates_path, "w") as f:
            yaml.dump({
                "step_templates": [
                    {"name": "dup", "agents": ["agent-a"],
                     "output": "x"},
                    {"name": "dup", "agents": ["agent-b"],
                     "output": "y"},
                ]
            }, f)

        # Write phases.yaml
        phases_path = harness_dir / "phases.yaml"
        with open(phases_path, "w") as f:
            yaml.dump({
                "phases": [
                    {"name": "test", "lead_agent": "lead",
                     "chat_agent": "chat",
                     "steps": [{"template": "dup"}]}
                ]
            }, f)

        template_registry = StepTemplateRegistry(
            team_registry=team_registry
        )
        mock_orch = MagicMock()

        # Should not raise — duplicate template is silently skipped
        bootstrap_and_register(
            orchestrator=mock_orch,
            template_registry=template_registry,
            phases_path=phases_path,
            templates_path=templates_path,
        )
        mock_orch.register_phases.assert_called_once()

    def test_template_auto_load(
        self, temp_dir: Path, team_registry: TeamRegistry
    ) -> None:
        """Templates are auto-loaded when templates_path is given."""
        harness_dir = temp_dir / ".harness"
        harness_dir.mkdir()

        # Write templates
        templates_path = harness_dir / "step_templates.yaml"
        with open(templates_path, "w") as f:
            yaml.dump({
                "step_templates": [
                    {"name": "simple", "agents": ["agent-a"],
                     "output": "result"}
                ]
            }, f)

        # Write phases referencing template
        phases_path = harness_dir / "phases.yaml"
        with open(phases_path, "w") as f:
            yaml.dump({
                "phases": [
                    {"name": "test", "lead_agent": "lead",
                     "chat_agent": "chat",
                     "steps": [{"template": "simple"}]}
                ]
            }, f)

        template_registry = StepTemplateRegistry(team_registry=team_registry)
        mock_orch = MagicMock()

        bootstrap_and_register(
            orchestrator=mock_orch,
            template_registry=template_registry,
            phases_path=phases_path,
            templates_path=templates_path,
        )

        mock_orch.register_phases.assert_called_once()
        args = mock_orch.register_phases.call_args[0]
        phases = args[0]
        assert len(phases) == 1
        assert phases[0].steps[0].agents == ["agent-a"]


# ── Integration with PhaseOrchestrator ────────────────────────────────────


class TestIntegrationWithOrchestrator:
    """End-to-end test: bootstrap → register → enter phase."""

    def test_bootstrap_register_and_list(self) -> None:
        """Phases are registered and listed on orchestrator."""
        from harness.phase.orchestrator import PhaseOrchestrator
        from harness.phase.strategy.runner import StrategyRunner
        from harness.phase.strategy.sequential import SequentialPhaseStrategy
        from harness.phase.dispatcher import StepDispatcher
        from harness.team.registry import TeamRegistry
        from harness.team.defaults import get_builtin_teams

        team_registry = TeamRegistry(builtin=get_builtin_teams())
        dispatcher = StepDispatcher(team_registry=team_registry)
        sequential = SequentialPhaseStrategy(dispatcher=dispatcher)
        strategy_runner = StrategyRunner(sequential=sequential)

        orchestrator = PhaseOrchestrator(strategy_runner=strategy_runner)

        # Bootstrap with nonexistent path (triggers default fallback)
        with tempfile.TemporaryDirectory() as d:
            nonexistent = Path(d) / "nope.yaml"
            bootstrap_and_register(
                orchestrator=orchestrator,
                phases_path=nonexistent,
            )

        registered = orchestrator.list_registered_phases()
        assert "discover" in registered
        assert "design" in registered
        assert "build" in registered

    def test_bootstrap_with_yaml_then_list(self, temp_dir: Path) -> None:
        """Phases from YAML are registered and listed."""
        from harness.phase.orchestrator import PhaseOrchestrator
        from harness.phase.strategy.runner import StrategyRunner
        from harness.phase.strategy.sequential import SequentialPhaseStrategy
        from harness.phase.dispatcher import StepDispatcher
        from harness.team.registry import TeamRegistry
        from harness.team.defaults import get_builtin_teams

        team_registry = TeamRegistry(builtin=get_builtin_teams())
        dispatcher = StepDispatcher(team_registry=team_registry)
        sequential = SequentialPhaseStrategy(dispatcher=dispatcher)
        strategy_runner = StrategyRunner(sequential=sequential)

        orchestrator = PhaseOrchestrator(strategy_runner=strategy_runner)

        # Write phases.yaml
        phases_path = temp_dir / "phases.yaml"
        with open(phases_path, "w") as f:
            yaml.dump({
                "phases": [
                    {"name": "custom-phase", "lead_agent": "lead",
                     "chat_agent": "chat",
                     "steps": [{"agents": ["a"], "output": "out"}]}
                ]
            }, f)

        bootstrap_and_register(
            orchestrator=orchestrator,
            phases_path=phases_path,
        )

        registered = orchestrator.list_registered_phases()
        assert "custom-phase" in registered
        phase = orchestrator._phases["custom-phase"]
        assert phase.lead_agent == "lead"

    def test_enter_phase_lookup(self, temp_dir: Path) -> None:
        """After bootstrap, enter_phase can find registered phases
        (or raise ValueError for missing ones)."""
        from harness.phase.orchestrator import PhaseOrchestrator
        from harness.phase.strategy.runner import StrategyRunner
        from harness.phase.strategy.sequential import SequentialPhaseStrategy
        from harness.phase.dispatcher import StepDispatcher
        from harness.team.registry import TeamRegistry
        from harness.team.defaults import get_builtin_teams
        from harness.phase.state_manager import PhaseStateManager
        from harness.phase.circuit_breaker import CircuitBreakerRegistry

        team_registry = TeamRegistry(builtin=get_builtin_teams())
        dispatcher = StepDispatcher(team_registry=team_registry)
        sequential = SequentialPhaseStrategy(dispatcher=dispatcher)

        mock_runner = AsyncMock(spec=StrategyRunner)
        mock_runner.run = AsyncMock(
            return_value=MagicMock(success=True)
        )

        orchestrator = PhaseOrchestrator(
            strategy_runner=mock_runner,
            state_manager=PhaseStateManager(),
            circuit_breaker_registry=CircuitBreakerRegistry(),
        )

        # Bootstrap with nonexistent path → defaults
        nonexistent = temp_dir / "nope.yaml"
        bootstrap_and_register(
            orchestrator=orchestrator,
            phases_path=nonexistent,
        )

        registered = orchestrator.list_registered_phases()
        assert "discover" in registered

        # Unknown phase should return result with error
        import asyncio
        result = asyncio.run(
            orchestrator.enter_phase(
                slug="test",
                phase_name="nonexistent-phase",
            )
        )
        assert not result.success
        assert result.error is not None

        # Registered phase can be found
        assert "discover" in orchestrator._phases


# ── Smoke / Import tests ──────────────────────────────────────────────────


def test_import_bootstrap() -> None:
    """bootstrap_phases is importable from the harness.phase namespace."""
    from harness.phase import bootstrap_phases
    assert callable(bootstrap_phases)


def test_import_bootstrap_and_register() -> None:
    """bootstrap_and_register is importable from the phase namespace."""
    from harness.phase import bootstrap_and_register
    assert callable(bootstrap_and_register)
