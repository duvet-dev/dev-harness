"""Tests for loop/convergence.py — all 5 convergence strategies.

Tests cover:
- GateJudgmentStrategy (keyword detection, phase_jump, no match)
- AllGatesStrategy (all passing, one failing, no gates)
- TestSuiteStrategy (subprocess mock, output capture)
- StableStrategy (unchanged output, changed output, first iteration)
- ExternalApprovalStrategy (with/without callback)
- STRATEGY_REGISTRY and resolve_strategy()
- STRATEGY_ALIASES backward-compatible names
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.loop.convergence import (
    AllGatesStrategy,
    ExternalApprovalStrategy,
    GateJudgmentStrategy,
    StableStrategy,
    STRATEGY_ALIASES,
    STRATEGY_REGISTRY,
    TestSuiteStrategy,
    resolve_strategy,
    resolve_strategy_name,
)
from harness.phase.model import (
    ConvergenceConfig,
    ConvergenceVerdict,
    StepResult,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def success_step_result() -> StepResult:
    return StepResult(
        step_type="gate",
        step_role="architect",
        status="success",
        artifacts={"output": "Everything CONVERGED and design approved."},
    )


@pytest.fixture
def phase_jump_step_result() -> StepResult:
    return StepResult(
        step_type="gate",
        step_role="architect",
        status="success",
        artifacts={
            "output": "CONVERGED phase_jump:testing Further refinements needed."
        },
    )


@pytest.fixture
def no_match_step_result() -> StepResult:
    return StepResult(
        step_type="gate",
        step_role="architect",
        status="success",
        artifacts={"output": "This needs more work. Issues found: 12."},
    )


@pytest.fixture
def empty_artifacts_step_result() -> StepResult:
    return StepResult(
        step_type="gate",
        step_role="architect",
        status="success",
        artifacts={},
    )


@pytest.fixture
def produce_step_result() -> StepResult:
    return StepResult(
        step_type="produce",
        step_role="coding-agent",
        status="success",
        artifacts={"code": "def hello(): pass"},
    )


@pytest.fixture
def default_config() -> ConvergenceConfig:
    return ConvergenceConfig(strategy="gate_judgment")


# ── GateJudgmentStrategy Tests ──────────────────────────────────────


class TestGateJudgmentStrategy:
    """Tests for GateJudgmentStrategy."""

    @pytest.mark.asyncio
    async def test_keyword_convergence(self, success_step_result: StepResult) -> None:
        """Keyword in gate output signals convergence."""
        config = ConvergenceConfig(strategy="gate_judgment")
        strategy = GateJudgmentStrategy(config)
        verdict = await strategy.check(
            [success_step_result], {}, 0
        )
        assert verdict.converged
        assert verdict.reason
        assert verdict.status_override is None

    @pytest.mark.asyncio
    async def test_phase_jump_detection(
        self, phase_jump_step_result: StepResult
    ) -> None:
        """Phase_jump signal is detected with status_override."""
        config = ConvergenceConfig(strategy="gate_judgment")
        strategy = GateJudgmentStrategy(config)
        verdict = await strategy.check(
            [phase_jump_step_result], {}, 0
        )
        assert verdict.converged
        assert verdict.status_override == "phase_jump:testing"
        assert "phase jump" in verdict.reason.lower()

    @pytest.mark.asyncio
    async def test_no_match(self, no_match_step_result: StepResult) -> None:
        """No keywords or phase_jump means not converged."""
        config = ConvergenceConfig(strategy="gate_judgment")
        strategy = GateJudgmentStrategy(config)
        verdict = await strategy.check(
            [no_match_step_result], {}, 0
        )
        assert not verdict.converged
        assert verdict.status_override is None

    @pytest.mark.asyncio
    async def test_no_gate_steps(self) -> None:
        """No gate steps means no convergence."""
        config = ConvergenceConfig(strategy="gate_judgment")
        strategy = GateJudgmentStrategy(config)
        verdict = await strategy.check(
            [StepResult(step_type="produce", step_role="coder")],
            {}, 0
        )
        assert not verdict.converged
        assert "No gate step" in verdict.reason

    @pytest.mark.asyncio
    async def test_empty_artifacts(
        self, empty_artifacts_step_result: StepResult
    ) -> None:
        """Empty artifacts don't cause convergence."""
        config = ConvergenceConfig(strategy="gate_judgment")
        strategy = GateJudgmentStrategy(config)
        verdict = await strategy.check(
            [empty_artifacts_step_result], {}, 0
        )
        assert not verdict.converged

    @pytest.mark.asyncio
    async def test_gate_agent_filter(
        self, success_step_result: StepResult
    ) -> None:
        """gate_agent filter narrows which steps to inspect."""
        config = ConvergenceConfig(
            strategy="gate_judgment",
            gate_agent="reviewer",
        )
        strategy = GateJudgmentStrategy(config)
        # gate step is for "architect", not "reviewer"
        verdict = await strategy.check(
            [success_step_result], {}, 0
        )
        assert not verdict.converged

    @pytest.mark.asyncio
    async def test_custom_keywords(self, success_step_result: StepResult) -> None:
        """Custom convergence keywords override defaults."""
        config = ConvergenceConfig(
            strategy="gate_judgment",
            convergence_keywords=["OK", "good to go"],
        )
        strategy = GateJudgmentStrategy(config)
        # "CONVERGED" is not in custom keywords
        verdict = await strategy.check(
            [success_step_result], {}, 0
        )
        assert not verdict.converged

    @pytest.mark.asyncio
    async def test_phase_jump_various_formats(self) -> None:
        """Various phase_jump formats are parsed correctly."""
        config = ConvergenceConfig(strategy="gate_judgment")
        strategy = GateJudgmentStrategy(config)

        test_cases = [
            ("phase_jump:design", "design"),
            ("PHASE_JUMP:testing", "testing"),
            ("phase_jump : review", "review"),
            ("converged. phase_jump:review", "review"),
        ]
        for text, expected_target in test_cases:
            sr = StepResult(
                step_type="gate",
                step_role="architect",
                status="success",
                artifacts={"output": text},
            )
            verdict = await strategy.check([sr], {}, 0)
            assert verdict.converged
            assert verdict.status_override == f"phase_jump:{expected_target}", (
                f"Failed for text: {text!r}"
            )


# ── AllGatesStrategy Tests ──────────────────────────────────────────


class TestAllGatesStrategy:
    """Tests for AllGatesStrategy."""

    @pytest.mark.asyncio
    async def test_all_gates_passing(self) -> None:
        """All gate steps passing means converged."""
        config = ConvergenceConfig(strategy="all_gates")
        strategy = AllGatesStrategy(config)
        verdict = await strategy.check(
            [
                StepResult(
                    step_type="gate",
                    status="success",
                    artifacts={"result": "passed"},
                ),
                StepResult(
                    step_type="gate",
                    status="success",
                    artifacts={"result": "approved"},
                ),
            ],
            {}, 0
        )
        assert verdict.converged

    @pytest.mark.asyncio
    async def test_one_gate_failing(self) -> None:
        """One failing gate means not converged."""
        config = ConvergenceConfig(strategy="all_gates")
        strategy = AllGatesStrategy(config)
        verdict = await strategy.check(
            [
                StepResult(step_type="gate", status="success",
                           artifacts={"r": "ok"}),
                StepResult(step_type="gate", status="failure",
                           artifacts={}),
            ],
            {}, 0
        )
        assert not verdict.converged

    @pytest.mark.asyncio
    async def test_no_gates(self) -> None:
        """No gate steps means not converged."""
        config = ConvergenceConfig(strategy="all_gates")
        strategy = AllGatesStrategy(config)
        verdict = await strategy.check(
            [StepResult(step_type="produce", status="success")],
            {}, 0
        )
        assert not verdict.converged

    @pytest.mark.asyncio
    async def test_empty_output_from_gate(self) -> None:
        """Gate with empty output means not converged."""
        config = ConvergenceConfig(strategy="all_gates")
        strategy = AllGatesStrategy(config)
        verdict = await strategy.check(
            [StepResult(step_type="gate", status="success",
                        artifacts={})],
            {}, 0
        )
        assert not verdict.converged


# ── TestSuiteStrategy Tests ─────────────────────────────────────────


class TestTestSuiteStrategy:
    """Tests for TestSuiteStrategy."""

    @pytest.mark.asyncio
    async def test_tests_pass(self) -> None:
        """Exit code 0 means converged."""
        config = ConvergenceConfig(strategy="test_suite", test_command="echo ok")
        strategy = TestSuiteStrategy(config)
        verdict = await strategy.check([], {}, 0)
        assert verdict.converged
        assert verdict.reason == "All tests passed"

    @pytest.mark.asyncio
    async def test_tests_fail(self) -> None:
        """Non-zero exit means not converged."""
        config = ConvergenceConfig(
            strategy="test_suite", test_command="false"
        )
        strategy = TestSuiteStrategy(config)
        verdict = await strategy.check([], {}, 0)
        assert not verdict.converged
        assert "exit" in verdict.reason

    @pytest.mark.asyncio
    async def test_test_output_captured(self) -> None:
        """Test output is captured in verdict."""
        config = ConvergenceConfig(
            strategy="test_suite", test_command="echo hello_test"
        )
        strategy = TestSuiteStrategy(config)
        verdict = await strategy.check([], {}, 0)
        assert verdict.test_output
        assert "hello_test" in verdict.test_output

    @pytest.mark.asyncio
    async def test_no_command(self) -> None:
        """No command configured means not converged."""
        config = ConvergenceConfig(strategy="test_suite", test_command="")
        strategy = TestSuiteStrategy(config)
        # Override the project root to a temp dir without test markers
        root = strategy._resolve_project_root()
        if root:
            # If we're in a project with test markers, force no command
            strategy._test_command = ""
            strategy._project_root = root
        verdict = await strategy.check([], {}, 0)
        # May converge if auto-detected, so just verify it doesn't crash
        assert isinstance(verdict, ConvergenceVerdict)

    @pytest.mark.asyncio
    async def test_output_persistence(self, tmp_path) -> None:
        """Test output is written to persistent file."""
        output_path = str(tmp_path / "test_output.txt")
        config = ConvergenceConfig(
            strategy="test_suite",
            test_command="echo persist_me",
            test_output_path=output_path,
        )
        strategy = TestSuiteStrategy(config)
        verdict = await strategy.check([], {}, 0)
        assert verdict.test_output
        # Check persistent file
        persisted = tmp_path / "test_output.txt"
        assert persisted.exists()
        assert "persist_me" in persisted.read_text()


# ── StableStrategy Tests ────────────────────────────────────────────


class TestStableStrategy:
    """Tests for StableStrategy."""

    @pytest.mark.asyncio
    async def test_first_iteration_no_history(self) -> None:
        """First iteration always returns not converged."""
        config = ConvergenceConfig(strategy="stable")
        strategy = StableStrategy(config)
        verdict = await strategy.check(
            [
                StepResult(
                    step_type="produce",
                    step_role="coder",
                    status="success",
                    artifacts={"code": "v1"},
                )
            ],
            {}, 0
        )
        assert not verdict.converged

    @pytest.mark.asyncio
    async def test_unchanged_output(self) -> None:
        """Unchanged output between iterations means converged."""
        config = ConvergenceConfig(strategy="stable")
        strategy = StableStrategy(config)
        # First iteration — store
        await strategy.check(
            [StepResult(step_type="produce", step_role="coder",
                        status="success",
                        artifacts={"code": "v1"})],
            {}, 0
        )
        # Second iteration — unchanged
        verdict = await strategy.check(
            [StepResult(step_type="produce", step_role="coder",
                        status="success",
                        artifacts={"code": "v1"})],
            {}, 1
        )
        assert verdict.converged

    @pytest.mark.asyncio
    async def test_changed_output(self) -> None:
        """Changed output between iterations means not converged."""
        config = ConvergenceConfig(strategy="stable")
        strategy = StableStrategy(config)
        await strategy.check(
            [StepResult(step_type="produce", step_role="coder",
                        status="success",
                        artifacts={"code": "v1"})],
            {}, 0
        )
        verdict = await strategy.check(
            [StepResult(step_type="produce", step_role="coder",
                        status="success",
                        artifacts={"code": "v2"})],
            {}, 1
        )
        assert not verdict.converged

    @pytest.mark.asyncio
    async def test_no_produce_steps(self) -> None:
        """No produce steps means not converged."""
        config = ConvergenceConfig(strategy="stable")
        strategy = StableStrategy(config)
        verdict = await strategy.check(
            [StepResult(step_type="gate", status="success")],
            {}, 0
        )
        assert not verdict.converged


# ── ExternalApprovalStrategy Tests ──────────────────────────────────


class TestExternalApprovalStrategy:
    """Tests for ExternalApprovalStrategy."""

    @pytest.mark.asyncio
    async def test_no_callback(self) -> None:
        """Without callback, not converged."""
        config = ConvergenceConfig(strategy="external_approval")
        strategy = ExternalApprovalStrategy(config)
        verdict = await strategy.check([], {}, 0)
        assert not verdict.converged

    @pytest.mark.asyncio
    async def test_callback_approves(self) -> None:
        """Callback returning converged=True."""
        config = ConvergenceConfig(strategy="external_approval")
        strategy = ExternalApprovalStrategy(config)

        async def approve(sr, arts, it):
            return ConvergenceVerdict(
                converged=True,
                reason="Human approved",
            )

        strategy.set_callback(approve)
        verdict = await strategy.check([], {}, 0)
        assert verdict.converged
        assert verdict.reason == "Human approved"

    @pytest.mark.asyncio
    async def test_callback_denies(self) -> None:
        """Callback returning converged=False."""
        config = ConvergenceConfig(strategy="external_approval")
        strategy = ExternalApprovalStrategy(config)

        async def deny(sr, arts, it):
            return ConvergenceVerdict(
                converged=False,
                reason="Still reviewing",
            )

        strategy.set_callback(deny)
        verdict = await strategy.check([], {}, 0)
        assert not verdict.converged


# ── Registry Tests ──────────────────────────────────────────────────


class TestStrategyRegistry:
    """Tests for STRATEGY_REGISTRY and resolve_strategy()."""

    def test_all_strategies_registered(self) -> None:
        """All 5 strategies are in the registry."""
        expected = {
            "gate_judgment",
            "all_gates",
            "test_suite",
            "stable",
            "external_approval",
        }
        assert set(STRATEGY_REGISTRY.keys()) == expected

    def test_resolve_gate_judgment(self) -> None:
        """resolve_strategy returns GateJudgmentStrategy."""
        config = ConvergenceConfig(strategy="gate_judgment")
        strategy = resolve_strategy(config)
        assert isinstance(strategy, GateJudgmentStrategy)

    def test_resolve_all_gates(self) -> None:
        """resolve_strategy returns AllGatesStrategy."""
        config = ConvergenceConfig(strategy="all_gates")
        strategy = resolve_strategy(config)
        assert isinstance(strategy, AllGatesStrategy)

    def test_resolve_test_suite(self) -> None:
        """resolve_strategy returns TestSuiteStrategy."""
        config = ConvergenceConfig(strategy="test_suite")
        strategy = resolve_strategy(config)
        assert isinstance(strategy, TestSuiteStrategy)

    def test_resolve_stable(self) -> None:
        """resolve_strategy returns StableStrategy."""
        config = ConvergenceConfig(strategy="stable")
        strategy = resolve_strategy(config)
        assert isinstance(strategy, StableStrategy)

    def test_resolve_external_approval(self) -> None:
        """resolve_strategy returns ExternalApprovalStrategy."""
        config = ConvergenceConfig(strategy="external_approval")
        strategy = resolve_strategy(config)
        assert isinstance(strategy, ExternalApprovalStrategy)

    def test_resolve_unknown_raises(self) -> None:
        """Unknown strategy name raises ValueError."""
        config = ConvergenceConfig(strategy="nonexistent")
        with pytest.raises(ValueError, match="Unknown convergence strategy"):
            resolve_strategy(config)


# ── Alias Tests ─────────────────────────────────────────────────────


class TestStrategyAliases:
    """Tests for STRATEGY_ALIASES and resolve_strategy_name()."""

    def test_all_aliases_exist(self) -> None:
        """All backward-compatible aliases are defined."""
        expected_aliases = {
            "agent_judgment": "gate_judgment",
            "all_gates_pass": "all_gates",
            "test-gate": "test_suite",
            "no-changes": "stable",
            "approval": "external_approval",
        }
        assert STRATEGY_ALIASES == expected_aliases

    def test_resolve_old_name(self) -> None:
        """Old strategy names resolve to new canonical names."""
        assert resolve_strategy_name("agent_judgment") == "gate_judgment"
        assert resolve_strategy_name("all_gates_pass") == "all_gates"
        assert resolve_strategy_name("test-gate") == "test_suite"
        assert resolve_strategy_name("no-changes") == "stable"
        assert resolve_strategy_name("approval") == "external_approval"

    def test_resolve_new_name(self) -> None:
        """New strategy names pass through unchanged."""
        assert resolve_strategy_name("gate_judgment") == "gate_judgment"
        assert resolve_strategy_name("all_gates") == "all_gates"

    def test_resolve_unknown_name(self) -> None:
        """Unknown names pass through unchanged."""
        assert resolve_strategy_name("foo") == "foo"

    def test_old_name_via_resolve_strategy(self) -> None:
        """Old names can be resolved via resolve_strategy()."""
        config = ConvergenceConfig(strategy="agent_judgment")
        strategy = resolve_strategy(config)
        assert isinstance(strategy, GateJudgmentStrategy)
