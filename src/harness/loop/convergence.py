"""Convergence strategies for critic loops — v4 design, Option D naming.

Provides 5 convergence strategies (gate_judgment, all_gates, test_suite,
stable, external_approval) plus STRATEGY_REGISTRY and resolve_strategy().

Each strategy is a pure analysis of existing step results — no synthetic
steps are created. Convergence is a post-iteration analysis pass.

Language (Option D):
    - gate_judgment (was agent_judgment): inspect gate step outputs
    - all_gates (was all_gates_pass): all gate steps passed
    - test_suite (was test-gate): external test suite determines convergence
    - stable (was no-changes): produce output unchanged between iterations
    - external_approval (was approval): external callback

Usage::

    from harness.loop.convergence import resolve_strategy, ConvergenceConfig

    config = ConvergenceConfig(strategy="gate_judgment", gate_agent="architect")
    strategy = resolve_strategy(config)
    verdict = await strategy.check(step_results, artifacts, iteration)
"""

from __future__ import annotations

import abc
import re
import subprocess
from pathlib import Path

from harness.phase.model import ConvergenceConfig, ConvergenceVerdict, StepResult


# ── Strategy ABC ───────────────────────────────────────────────────────────


class ConvergenceStrategy(abc.ABC):
    """Abstract base for a convergence check strategy.

    Each strategy examines existing step results and artifacts to determine
    if the loop has converged. No strategy creates or executes new steps.
    """

    @abc.abstractmethod
    async def check(
        self,
        step_results: list[StepResult],
        artifacts: dict[str, str],
        iteration: int,
    ) -> ConvergenceVerdict:
        ...


# ── GateJudgmentStrategy ──────────────────────────────────────────────────


class GateJudgmentStrategy(ConvergenceStrategy):
    """Convergence is declared when a gate step's output contains keywords
    OR a phase-jump signal.

    PURE ANALYSIS: The gate step was already executed as part of the step
    sequence. This strategy simply inspects its output artifact text for:

      1. Convergence keywords (e.g. "CONVERGED", "no new issues")
      2. Phase-jump signals (e.g. "phase_jump:design")

    No synthetic steps are created. The gate agent's result was produced
    during the normal step execution. This is a post-hoc analysis pass.

    PHASE-JUMP DETECTION (v4 Fix 1):
    When a gate agent's output contains "phase_jump:<target>", the strategy
    returns a ConvergenceVerdict with status_override = "phase_jump:<target>".
    """

    DEFAULT_KEYWORDS = [
        "converged", "convergence", "no new issues",
        "design approved", "no issues found",
    ]

    PHASE_JUMP_PATTERN = re.compile(r"phase_jump\s*:\s*(\w+)", re.IGNORECASE)

    def __init__(self, config: ConvergenceConfig) -> None:
        self._gate_agent = config.gate_agent
        self._keywords = config.convergence_keywords or self.DEFAULT_KEYWORDS

    async def check(
        self,
        step_results: list[StepResult],
        artifacts: dict[str, str],
        iteration: int,
    ) -> ConvergenceVerdict:
        # Find relevant gate step results
        candidates = [
            r for r in step_results
            if r.step_type == "gate"
            and r.status == "success"
        ]

        if self._gate_agent:
            candidates = [
                r for r in candidates
                if r.step_role == self._gate_agent
            ]

        if not candidates:
            return ConvergenceVerdict(
                converged=False,
                reason="No gate step results to analyse",
            )

        # Phase-jump detection — scan ALL gate outputs first
        for result in candidates:
            text = " ".join(result.artifacts.values()).lower()
            phase_jump_match = self.PHASE_JUMP_PATTERN.search(text)
            if phase_jump_match:
                target = phase_jump_match.group(1).lower()
                return ConvergenceVerdict(
                    converged=True,
                    status_override=f"phase_jump:{target}",
                    reason=(
                        f"Gate step ({result.step_role}) signalled "
                        f"phase jump to '{target}'"
                    ),
                )

        # Keyword convergence check
        for result in candidates:
            text = " ".join(result.artifacts.values()).lower()
            if any(kw.lower() in text for kw in self._keywords):
                return ConvergenceVerdict(
                    converged=True,
                    reason=f"Gate step ({result.step_role}) converged",
                )

        return ConvergenceVerdict(
            converged=False,
            reason="No gate step output contained convergence keywords "
                    "or phase-jump signals",
        )


# ── AllGatesStrategy ──────────────────────────────────────────────────────


class AllGatesStrategy(ConvergenceStrategy):
    """Convergence when ALL gate steps produced non-empty success output."""

    def __init__(self, config: ConvergenceConfig) -> None:
        pass

    async def check(
        self,
        step_results: list[StepResult],
        artifacts: dict[str, str],
        iteration: int,
    ) -> ConvergenceVerdict:
        gate_results = [r for r in step_results if r.step_type == "gate"]
        if not gate_results:
            return ConvergenceVerdict(converged=False, reason="No gate steps")

        all_passing = all(
            r.status == "success"
            and bool(r.artifacts)
            and any(v.strip() for v in r.artifacts.values())
            for r in gate_results
        )

        return ConvergenceVerdict(
            converged=all_passing,
            reason="All gates passed" if all_passing else "Not all gates passing",
        )


# ── TestSuiteStrategy ─────────────────────────────────────────────────────


class TestSuiteStrategy(ConvergenceStrategy):
    """Convergence when the project test suite passes.

    On failure, test output is captured and fed back.

    TEST OUTPUT FEED-THROUGH (v4 Fix 2):
    Test output is captured via TWO mechanisms for robustness:

    1. IN-MEMORY: verdict.test_output — carried in the ConvergenceVerdict
       for injection into accumulated_context (after _update_context).

    2. PERSISTENT DISK FILE: Written to config.test_output_path
       (default: .harness/test_output/latest.txt). This file survives
       any context model strategy, including aggressive context replacement.

    Together, these guarantee test output is never lost between iterations.
    """

    def __init__(self, config: ConvergenceConfig) -> None:
        self._test_command = config.test_command
        self._test_output_path = (
            config.test_output_path or ".harness/test_output/latest.txt"
        )
        self._project_root: Path | None = None

    async def check(
        self,
        step_results: list[StepResult],
        artifacts: dict[str, str],
        iteration: int,
    ) -> ConvergenceVerdict:
        repo_root = self._resolve_project_root()
        command = self._resolve_command(repo_root)

        if command is None:
            return ConvergenceVerdict(
                converged=False,
                reason="No test command configured or auto-detected",
            )

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(repo_root) if repo_root else None,
            )
            test_output = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            test_output = "Test suite timed out (120s)."
            return ConvergenceVerdict(
                converged=False,
                reason="Test suite timed out (120s)",
                test_output=test_output,
            )
        except FileNotFoundError as exc:
            test_output = f"Test runner not found: {exc}"
            return ConvergenceVerdict(
                converged=False,
                reason=f"Test runner not found: {exc}",
                test_output=test_output,
            )

        # Write test output to persistent artifact file.
        # This survives context rebuilds.
        self._persist_test_output(test_output, repo_root)

        if result.returncode == 0:
            return ConvergenceVerdict(
                converged=True,
                reason="All tests passed",
                test_output=test_output,
            )

        return ConvergenceVerdict(
            converged=False,
            reason=f"Tests failed (exit {result.returncode})",
            test_output=test_output,
        )

    def _persist_test_output(
        self, test_output: str, repo_root: Path | None
    ) -> None:
        """Write test output to a persistent artifact file.

        Read back by LoopRunner when injecting context for the next
        iteration, ensuring test_output survives context replacement.
        """
        try:
            path = Path(repo_root or ".") / self._test_output_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(test_output)
        except OSError:
            pass  # Non-fatal; in-memory path still works

    def _resolve_project_root(self) -> Path | None:
        """Walk up from CWD to find .git marker."""
        if self._project_root:
            return self._project_root
        start = Path.cwd()
        for parent in [start] + list(start.parents):
            if (parent / ".git").exists():
                self._project_root = parent
                return parent
        self._project_root = start
        return start

    def _resolve_command(self, repo_root: Path | None) -> list[str] | None:
        """Resolve test command from explicit config or auto-detect."""
        if self._test_command.strip():
            import shlex
            return shlex.split(self._test_command)
        return self._detect_test_command(repo_root)

    @staticmethod
    def _detect_test_command(repo_root: Path | None) -> list[str] | None:
        """Auto-detect test command from project root markers."""
        if repo_root is None:
            return None

        markers: list[tuple[str, list[str]]] = [
            ("pyproject.toml", ["pytest"]),
            ("pytest.ini", ["pytest"]),
            ("setup.cfg", ["pytest"]),
            ("Makefile", ["make", "test"]),
            ("Cargo.toml", ["cargo", "test"]),
            ("go.mod", ["go", "test", "./..."]),
            ("package.json", ["npm", "test"]),
        ]
        for marker, cmd in markers:
            if (repo_root / marker).exists():
                return cmd
        return None


# ── StableStrategy ────────────────────────────────────────────────────────


class StableStrategy(ConvergenceStrategy):
    """Convergence when produce output is identical between iterations.

    Tracks previous iteration's produce output via internal state.
    """

    def __init__(self, config: ConvergenceConfig) -> None:
        self._previous_outputs: dict[str, str] = {}

    async def check(
        self,
        step_results: list[StepResult],
        artifacts: dict[str, str],
        iteration: int,
    ) -> ConvergenceVerdict:
        produce_results = [r for r in step_results if r.step_type == "produce"]
        if not produce_results:
            return ConvergenceVerdict(converged=False, reason="No produce steps")

        all_unchanged = True
        for pr in produce_results:
            for key, content in pr.artifacts.items():
                prev = self._previous_outputs.get(key, "")
                if prev and prev.strip() == content.strip():
                    continue
                elif prev:
                    self._previous_outputs[key] = content
                    all_unchanged = False
                else:
                    self._previous_outputs[key] = content
                    all_unchanged = False

        if all_unchanged and produce_results:
            return ConvergenceVerdict(
                converged=True,
                reason="All produce outputs unchanged",
            )

        return ConvergenceVerdict(
            converged=False,
            reason="Produce outputs changed or no history yet",
        )


# ── ExternalApprovalStrategy ──────────────────────────────────────────────


class ExternalApprovalStrategy(ConvergenceStrategy):
    """Convergence when an external callback or API confirms.

    Stub implementation — requires a callback to be set via set_callback().
    """

    def __init__(self, config: ConvergenceConfig) -> None:
        self._callback: callable | None = None

    def set_callback(self, callback: callable) -> None:
        """Set the external approval callback.

        Args:
            callback: Async callable taking (step_results, artifacts, iteration)
                and returning a ConvergenceVerdict.
        """
        self._callback = callback

    async def check(
        self,
        step_results: list[StepResult],
        artifacts: dict[str, str],
        iteration: int,
    ) -> ConvergenceVerdict:
        if self._callback:
            return await self._callback(step_results, artifacts, iteration)
        return ConvergenceVerdict(
            converged=False,
            reason="No approval callback configured",
        )


# ── Strategy Registry ─────────────────────────────────────────────────────


STRATEGY_REGISTRY: dict[str, type[ConvergenceStrategy]] = {
    "gate_judgment": GateJudgmentStrategy,
    "all_gates": AllGatesStrategy,
    "test_suite": TestSuiteStrategy,
    "stable": StableStrategy,
    "external_approval": ExternalApprovalStrategy,
}

# Backward-compatible aliases for old strategy names.
# These allow old configs/persisted templates to resolve during migration.
STRATEGY_ALIASES: dict[str, str] = {
    "agent_judgment": "gate_judgment",
    "all_gates_pass": "all_gates",
    "test-gate": "test_suite",
    "no-changes": "stable",
    "approval": "external_approval",
}


def resolve_strategy_name(name: str) -> str:
    """Resolve a strategy name through alias mapping.

    Args:
        name: Raw strategy name (new or old).

    Returns:
        Canonical strategy name.
    """
    return STRATEGY_ALIASES.get(name, name)


def resolve_strategy(config: ConvergenceConfig) -> ConvergenceStrategy:
    """Resolve a ConvergenceConfig to a ConvergenceStrategy instance.

    Args:
        config: The convergence configuration.

    Returns:
        An instantiated ConvergenceStrategy.

    Raises:
        ValueError: If the strategy name is unknown.
    """
    canonical = resolve_strategy_name(config.strategy)
    cls = STRATEGY_REGISTRY.get(canonical)
    if cls is None:
        raise ValueError(
            f"Unknown convergence strategy: '{config.strategy}'. "
            f"Available: {list(STRATEGY_REGISTRY.keys())}"
        )
    # Create a copy of the config with the canonical strategy name
    resolved_config = ConvergenceConfig(
        strategy=canonical,
        max_iterations=config.max_iterations,
        on_timeout=config.on_timeout,
        gate_agent=config.gate_agent,
        test_command=config.test_command,
        convergence_keywords=config.convergence_keywords,
        test_output_path=config.test_output_path,
    )
    return cls(resolved_config)
