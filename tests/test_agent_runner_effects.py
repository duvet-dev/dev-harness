"""Tests for pure logic functions in harness.agents.runner.

The AgentRunner class mixes async IO (backend calls, Temporal) with
pure business logic. This file tests the pure parts in isolation:

- _check_critic_convergence() — text analysis
- _build_fallback_chain() — config-based fallback construction
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from harness.agents.runner import RunnerConfig, CriticLoopError
from harness.agents.agent_registry import CriticLoopConfig
from harness.agents.backends.base import BackendResult


class TestCheckCriticConvergence:
    """Tests for _check_critic_convergence() — pure text analysis."""

    def make_result(self, artifacts: dict[str, str]) -> BackendResult:
        return BackendResult(status="success", artifacts=artifacts)

    def make_config(self, keywords: list[str]) -> CriticLoopConfig:
        return CriticLoopConfig(convergence_keywords=keywords)

    def test_converges_when_keyword_in_artifact(self):
        runner = object.__new__(type("AgentRunner", (), {}))
        # Add the method to the mock instance
        import harness.agents.runner as r
        runner.__class__ = r.AgentRunner
        runner._config = RunnerConfig()

        result = self.make_result({"report": "The system has converged."})
        config = self.make_config(["converged"])
        assert runner._check_critic_convergence(result, config) is True

    def test_no_convergence_when_keyword_absent(self):
        runner = object.__new__(type("AgentRunner", (), {}))
        import harness.agents.runner as r
        runner.__class__ = r.AgentRunner
        runner._config = RunnerConfig()

        result = self.make_result({"report": "Everything looks fine."})
        config = self.make_config(["converged", "done"])
        assert runner._check_critic_convergence(result, config) is False

    def test_case_insensitive(self):
        runner = object.__new__(type("AgentRunner", (), {}))
        import harness.agents.runner as r
        runner.__class__ = r.AgentRunner
        runner._config = RunnerConfig()

        result = self.make_result({"note": "CONVERGED"})
        config = self.make_config(["Converged"])
        assert runner._check_critic_convergence(result, config) is True

    def test_keyword_in_any_artifact(self):
        runner = object.__new__(type("AgentRunner", (), {}))
        import harness.agents.runner as r
        runner.__class__ = r.AgentRunner
        runner._config = RunnerConfig()

        result = self.make_result({"a": "foo", "b": "converged here", "c": "bar"})
        config = self.make_config(["converged"])
        assert runner._check_critic_convergence(result, config) is True

    def test_empty_artifacts(self):
        runner = object.__new__(type("AgentRunner", (), {}))
        import harness.agents.runner as r
        runner.__class__ = r.AgentRunner
        runner._config = RunnerConfig()

        result = self.make_result({})
        config = self.make_config(["converged"])
        assert runner._check_critic_convergence(result, config) is False

    def test_multiple_keywords_any_match(self):
        runner = object.__new__(type("AgentRunner", (), {}))
        import harness.agents.runner as r
        runner.__class__ = r.AgentRunner
        runner._config = RunnerConfig()

        result = self.make_result({"output": "All issues resolved"})
        config = self.make_config(["converged", "resolved", "approved"])
        assert runner._check_critic_convergence(result, config) is True


class TestBuildFallbackChain:
    """Tests for _build_fallback_chain() — pure config parsing."""

    def make_packet(self, fallbacks=None):
        from harness.agents.context import ContextPacket, OutputContract
        return ContextPacket(
            engagement_id="test",
            phase_name="test",
            task_id="test",
            spec_content="test",
            architecture_rules=[],
            target_directory=None,
            output_contract=OutputContract(),
            constraint_section={"fallbacks": fallbacks} if fallbacks else {},
        )

    def test_no_fallbacks_in_packet(self):
        runner = object.__new__(type("AgentRunner", (), {}))
        import harness.agents.runner as r
        runner.__class__ = r.AgentRunner
        runner._config = RunnerConfig()

        packet = self.make_packet()
        chain = runner._build_fallback_chain("api", "", packet)
        assert chain == []

    def test_single_fallback(self):
        runner = object.__new__(type("AgentRunner", (), {}))
        import harness.agents.runner as r
        runner.__class__ = r.AgentRunner
        runner._config = RunnerConfig()

        packet = self.make_packet([
            {"backend": "cli", "model": "claude-3"},
        ])
        chain = runner._build_fallback_chain("api", "", packet)
        assert len(chain) == 1
        assert chain[0]["backend"] == "cli"
        assert chain[0]["model"] == "claude-3"

    def test_multiple_fallbacks(self):
        runner = object.__new__(type("AgentRunner", (), {}))
        import harness.agents.runner as r
        runner.__class__ = r.AgentRunner
        runner._config = RunnerConfig()

        packet = self.make_packet([
            {"backend": "cli"},
            {"backend": "editor", "model": "gpt-4"},
        ])
        chain = runner._build_fallback_chain("api", "", packet)
        assert len(chain) == 2
        assert chain[0]["backend"] == "cli"
        assert chain[1]["backend"] == "editor"
        assert chain[1]["model"] == "gpt-4"

    def test_fallback_without_backend_skipped(self):
        runner = object.__new__(type("AgentRunner", (), {}))
        import harness.agents.runner as r
        runner.__class__ = r.AgentRunner
        runner._config = RunnerConfig()

        packet = self.make_packet([
            {"model": "deepseek"},  # no backend key
            {"backend": "cli"},
        ])
        chain = runner._build_fallback_chain("api", "", packet)
        assert len(chain) == 1
        assert chain[0]["backend"] == "cli"

    def test_fallbacks_is_not_a_list(self):
        runner = object.__new__(type("AgentRunner", (), {}))
        import harness.agents.runner as r
        runner.__class__ = r.AgentRunner
        runner._config = RunnerConfig()

        packet = self.make_packet("not a list")
        chain = runner._build_fallback_chain("api", "", packet)
        assert chain == []

    def test_default_model_when_not_specified(self):
        runner = object.__new__(type("AgentRunner", (), {}))
        import harness.agents.runner as r
        runner.__class__ = r.AgentRunner
        runner._config = RunnerConfig()

        packet = self.make_packet([
            {"backend": "cli"},  # no model
        ])
        chain = runner._build_fallback_chain("api", "", packet)
        assert chain[0]["model"] == "default"


class TestCriticLoopError:
    """Tests for CriticLoopError — simple exception."""

    def test_message(self):
        err = CriticLoopError("Too many iterations")
        assert str(err) == "Too many iterations"
        assert isinstance(err, Exception)


class TestRunnerConfigFromDict:
    """Tests for RunnerConfig.from_dict — pure config parsing."""

    def test_empty_dict(self):
        c = RunnerConfig.from_dict({})
        assert isinstance(c, RunnerConfig)

    def test_timeout_override(self):
        c = RunnerConfig.from_dict({"timeout_seconds": "300"})
        assert c.timeout_seconds == 300

    def test_partial_override(self):
        c = RunnerConfig.from_dict({"default_backend": "cli"})
        assert c.default_backend == "cli"
        assert c.timeout_seconds == 600  # unchanged default
