"""WaveCycleRunner — orchestrates a single wave through implement→test→verify.

DEPRECATED (Wave 4, R33): WaveCycleRunner is replaced by LoopRunner.
All wave-cycle functionality is now in :class:`harness.loop.runner.LoopRunner`.

This module is retained for transitional compatibility and will be
removed entirely in the Cleanup Wave.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import warnings

from harness.agents.context import ContextPacket, OutputContract
from harness.agents.cycle import (
    CycleResult,
    CycleRunner,
    CycleRunnerDefinition,
    wave_cycle_definition,
)
from harness.agents.runner import AgentRunner, BackendResult
from harness.plan.plan_manager import PlanManager
from harness.plan.wave_model import Wave

# ── Cycle-based wave runner ─────────────────────────────────────────────────


async def run_wave_via_cycle(
    root: Path,
    engagement_slug: str,
    wave_id: str,
    definition: CycleRunnerDefinition | None = None,
) -> CycleResult:
    """Run a wave through the CycleRunner engine using the wave-cycle definition.

    This is the Phase 5 integration: the wave-cycle definition includes
    consult steps (architect, advisory) as ``CycleStep(type="consult")``,
    eliminating the need for a separate auto-consult API. The cycle may
    also return ``phase_jump:<target>`` status for architectural issues
    detected during consultation.

    Args:
        root: Project root directory.
        engagement_slug: Current engagement identifier.
        wave_id: The wave identifier (e.g. ``"wave-01"``).
        definition: Optional custom cycle definition. Defaults to
            ``wave_cycle_definition()``.

    Returns:
        A ``CycleResult`` with step results, final artifacts, and
        optional phase-jump status.
    """
    warnings.warn(
        "run_wave_via_cycle() is deprecated (Wave 4, R33). "
        "Use LoopRunner instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    from harness.plan.plan_manager import PlanManager

    cycle_def = definition or wave_cycle_definition()
    plan_mgr = PlanManager(root, engagement_slug)
    plan = plan_mgr.load()
    wave = plan.get_wave(wave_id) if plan else None
    wave_context = f"Wave {wave_id}: {wave.title if wave else wave_id}" if wave else f"Wave {wave_id}"

    runner = CycleRunner(root=root)
    result = await runner.run(
        definition=cycle_def,
        engagement_slug=engagement_slug,
        spec_content=wave_context,
        initial_artifacts={"plan.md": str(plan) if plan else ""},
    )
    return result

logger = logging.getLogger(__name__)


# ── Configuration ──────────────────────────────────────────────────────────


@dataclass
class WaveCycleConfig:
    """Configuration for per-wave code+test cycles.

    Attributes:
        backend_name: Agent backend to use for coder and tester invocations.
        max_fix_iterations: Max implement→fix cycles per wave.
        auto_test: If True, run the actual test suite after each implementation.
        test_command: Shell command to run the test suite.
        test_timeout_seconds: Timeout for test suite execution.
        agent_timeout_seconds: Timeout per agent invocation.
        run_boundary_first: If True, boundary tests run before the full suite.
        boundary_test_command: Shell command for boundary tests only.
    """

    backend_name: str = ""
    max_fix_iterations: int = 3
    auto_test: bool = True
    test_command: str = sys.executable + " -m pytest --tb=short -q"
    test_timeout_seconds: int = 120
    agent_timeout_seconds: int = 120
    run_boundary_first: bool = True
    boundary_test_command: str = (
        sys.executable
        + " -m pytest tests/test_refactor_boundaries.py "
          "tests/test_refactor_boundary_tests.py --tb=short -q -x"
    )

    @classmethod
    def defaults(cls) -> WaveCycleConfig:
        return cls()


# ── Result ─────────────────────────────────────────────────────────────────


@dataclass
class WaveCycleResult:
    """Result of running a single wave through its code+test cycle.

    Attributes:
        wave_id: The wave identifier (e.g. ``"wave-01"``).
        title: Human-readable wave title.
        success: True if all implementations passed and tests pass.
        iterations: Number of implement→test fix cycles used.
        test_results: Parsed test output summary.
        errors: Error messages from the cycle.
        committed: True if the wave was marked committed in the plan.
        coder_artifacts: Artifacts produced by the coder agent (per iteration).
    """

    wave_id: str = ""
    title: str = ""
    success: bool = False
    iterations: int = 0
    test_results: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    committed: bool = False
    coder_artifacts: list[dict[str, str]] = field(default_factory=list)


# ── Runner ──────────────────────────────────────────────────────────────────


class WaveCycleRunner:
    """Orchestrates the implement→test→verify cycle for a single wave.

    Typical flow::

        runner = WaveCycleRunner(root, slug)
        result = await runner.run_wave("wave-01")
        if result.success:
            # Wave is ready to commit/PR
    """

    def __init__(
        self,
        root: Path,
        engagement_slug: str,
        config: WaveCycleConfig | None = None,
    ) -> None:
        warnings.warn(
            "WaveCycleRunner is deprecated (Wave 4, R33). "
            "Use LoopRunner instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._root = root
        self._slug = engagement_slug
        self._config = config or WaveCycleConfig.defaults()
        self._plan_manager = PlanManager(root, engagement_slug)
        self._runner = AgentRunner()

    # ── Public API ─────────────────────────────────────────────────────────

    async def run_wave(self, wave_id: str) -> WaveCycleResult:
        """Run a wave through the full implement→test→verify→commit cycle.

        Args:
            wave_id: The wave identifier in the plan (e.g. ``"wave-01"``).

        Returns:
            A ``WaveCycleResult`` describing what happened.
        """
        wave = self._plan_manager.load().get_wave(wave_id)
        if wave is None:
            return WaveCycleResult(
                wave_id=wave_id,
                errors=[f"Wave '{wave_id}' not found in plan."],
            )

        # Mark in-progress
        self._plan_manager.set_wave_state(wave_id, "in_progress")
        logger.info("Wave %s: %s — starting cycle", wave_id, wave.title)

        result = WaveCycleResult(
            wave_id=wave_id,
            title=wave.title,
        )

        for iteration in range(1, self._config.max_fix_iterations + 1):
            result.iterations = iteration
            logger.info(
                "Wave %s iteration %d/%d",
                wave_id, iteration, self._config.max_fix_iterations,
            )

            # ── Step 1: Run the coder agent ──────────────────────────────
            coder_result = await self._run_coder(wave)
            result.coder_artifacts.append(coder_result.artifacts)

            if coder_result.status != "success":
                error = coder_result.errors[0] if coder_result.errors else "Coder agent failed"
                logger.warning("Wave %s coder iteration %d failed: %s", wave_id, iteration, error)
                result.errors.append(error)
                result.success = False
                return result

            # ── Step 2: Run the tester agent ─────────────────────────────
            tester_result = await self._run_tester(wave, coder_result)
            if tester_result.status != "success":
                error = tester_result.errors[0] if tester_result.errors else "Tester agent failed"
                logger.warning("Wave %s tester iteration %d failed: %s", wave_id, iteration, error)
                result.errors.append(error)
                result.success = False
                return result

            # ── Step 3: Run boundary tests first (if configured) ────────
            if self._config.auto_test and self._config.run_boundary_first:
                boundary_outcome = await self._run_boundary_tests()

                if boundary_outcome.get("exit_code", 1) != 0:
                    # Boundary tests failed — quicker feedback, skip full suite
                    summary = boundary_outcome.get(
                        "summary", "Boundary test failure"
                    )
                    logger.warning(
                        "Wave %s boundary tests failed on iteration %d: %s",
                        wave_id, iteration, summary,
                    )
                    result.test_results = boundary_outcome
                    result.errors.append(
                        f"Iteration {iteration}: Boundary tests failed — {summary}"
                    )
                    if iteration < self._config.max_fix_iterations:
                        continue
                    else:
                        result.errors.append(
                            f"Max iterations ({self._config.max_fix_iterations}) "
                            f"reached. Boundary tests still failing."
                        )
                        result.success = False
                        return result

            # ── Step 4: Run the full test suite ─────────────────────────
            if self._config.auto_test:
                test_outcome = await self._run_test_suite()
                result.test_results = test_outcome

                if test_outcome.get("exit_code", 1) == 0:
                    # Tests pass — we're done
                    logger.info(
                        "Wave %s tests passed on iteration %d",
                        wave_id, iteration,
                    )
                    result.success = True
                    break
                else:
                    # Tests failed — prepare feedback for next iteration
                    summary = test_outcome.get("summary", "Unknown test failure")
                    logger.warning(
                        "Wave %s tests failed on iteration %d: %s",
                        wave_id, iteration, summary,
                    )
                    if iteration < self._config.max_fix_iterations:
                        # Carry forward — next coder iteration gets test output
                        result.errors.append(
                            f"Iteration {iteration}: Tests failed — {summary}"
                        )
                        continue
                    else:
                        result.errors.append(
                            f"Max iterations ({self._config.max_fix_iterations}) "
                            f"reached. Last test output: {summary}"
                        )
                        result.success = False
                        return result
            else:
                # No auto-test — one pass is enough
                result.success = True
                break

        # ── Commit the wave ──────────────────────────────────────────────
        if result.success:
            self._plan_manager.commit_wave(wave_id)
            result.committed = True
            logger.info("Wave %s committed", wave_id)

        return result

    # ── Internal: Coder ────────────────────────────────────────────────────

    async def _run_coder(
        self,
        wave: Wave,
        test_feedback: str | None = None,
    ) -> BackendResult:
        """Invoke the coder agent to implement this wave's tasks."""
        tasks_text = "\n".join(f"- {t.description}" for t in wave.tasks)

        spec = (
            f"# Wave: {wave.id} — {wave.title}\n\n"
            f"## Tasks\n{tasks_text}\n\n"
            f"## Type\n{wave.type.value}\n\n"
        )

        if test_feedback:
            spec += (
                f"\n## Test Feedback (from previous run)\n"
                f"{test_feedback}\n\n"
                f"Please fix the failing tests while preserving existing functionality."
            )
        else:
            spec += (
                "## Instructions\n"
                "Implement the code and tests for this wave.\n"
                "Write well-structured, tested code.\n"
                "Use the RepoTool to write files directly.\n"
                "Ensure new tests can be run alongside existing tests.\n"
            )

        phase_name = f"implementation-{wave.id}"

        packet = ContextPacket(
            engagement_id=self._slug,
            phase_name=phase_name,
            task_id=f"coder-{wave.id}",
            spec_content=spec,
            target_directory=self._root,
            constraint_section={
                "agent_role": "coder",
                "backend": self._config.backend_name,
            },
            output_contract=OutputContract(
                required_files=[],
                file_rules=[],
            ),
        )

        return await self._runner.run(
            packet,
            backend_name=self._config.backend_name or None,
        )

    # ── Internal: Tester ───────────────────────────────────────────────────

    async def _run_tester(
        self,
        wave: Wave,
        coder_result: BackendResult,
    ) -> BackendResult:
        """Invoke the testing agent to validate and supplement tests."""
        tasks_text = "\n".join(f"- {t.description}" for t in wave.tasks)
        code_artifacts = "\n".join(
            f"- {k}: {v[:200]}..."
            for k, v in (coder_result.artifacts or {}).items()
        )

        spec = (
            f"# Wave: {wave.id} — {wave.title}\n\n"
            f"## Tasks\n{tasks_text}\n\n"
            f"## Code Written (by coder)\n{code_artifacts}\n\n"
            "## Instructions\n"
            "Review the implementation code written by the coder agent.\n"
            "Add tests to cover edge cases, error paths, and boundary conditions.\n"
            "Use the RepoTool to write test files.\n"
            "Do NOT change implementation code — only add/update tests.\n"
            "Ensure tests are compatible with the existing test framework.\n"
        )

        packet = ContextPacket(
            engagement_id=self._slug,
            phase_name=f"testing-{wave.id}",
            task_id=f"tester-{wave.id}",
            spec_content=spec,
            target_directory=self._root,
            constraint_section={
                "agent_role": "tester",
                "backend": self._config.backend_name,
            },
            output_contract=OutputContract(
                required_files=[],
                file_rules=[
                    {"rule": "only touch test files, not implementation code"},
                ],
            ),
        )

        return await self._runner.run(
            packet,
            backend_name=self._config.backend_name or None,
        )

    # ── Internal: Boundary tests (run before full suite) ────────────────

    async def _run_boundary_tests(self) -> dict[str, Any]:
        """Run boundary tests before the full test suite.

        Boundary tests focus on architecture integrity (layer violations,
        adapter boundaries, circular deps). Running them first provides
        quicker feedback when structural changes break the architecture.

        Returns same dict format as :meth:`_run_test_suite`.
        """
        try:
            proc = await asyncio.create_subprocess_shell(
                self._config.boundary_test_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._root),
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._config.test_timeout_seconds,
            )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            summary_line = self._extract_summary_line(
                stdout, stderr, proc.returncode or 0
            )

            return {
                "exit_code": proc.returncode or 0,
                "stdout": stdout,
                "stderr": stderr,
                "summary": summary_line,
                "boundary": True,
                "completed": True,
            }

        except asyncio.TimeoutError:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": "",
                "summary": (
                    f"Boundary tests timed out after "
                    f"{self._config.test_timeout_seconds}s"
                ),
                "boundary": True,
                "completed": False,
            }

    # ── Internal: Test suite execution ─────────────────────────────────────

    async def _run_test_suite(self) -> dict[str, Any]:
        """Run the actual test suite via the configured test command.

        Returns:
            A dict with keys:
            - ``exit_code``: 0 if all tests passed
            - ``stdout``: Captured stdout
            - ``stderr``: Captured stderr
            - ``summary``: Extracted summary line
        """
        try:
            proc = await asyncio.create_subprocess_shell(
                self._config.test_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._root),
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._config.test_timeout_seconds,
            )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            # Extract summary line
            summary_line = self._extract_summary_line(
                stdout, stderr, proc.returncode or 0
            )

            return {
                "exit_code": proc.returncode or 0,
                "stdout": stdout,
                "stderr": stderr,
                "summary": summary_line,
                "completed": True,
            }

        except asyncio.TimeoutError:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": "",
                "summary": f"Test suite timed out after "
                           f"{self._config.test_timeout_seconds}s",
                "completed": False,
            }

    @staticmethod
    def _extract_summary_line(
        stdout: str, stderr: str, exit_code: int,
    ) -> str:
        """Extract a meaningful summary from test output.

        Prefers the final ``pytest`` result line (``X passed in Ys``) for
        successful runs.  Falls back to last non-empty line.
        """
        # Try to find pytest summary line
        for line in stdout.splitlines():
            stripped = line.strip()
            if re.match(r"^\d+ passed", stripped) or re.match(
                r"^\d+ failed", stripped
            ):
                return stripped
            if "passed" in stripped and "failed" in stripped:
                return stripped

        # Try stderr for failure info
        for line in stderr.splitlines():
            stripped = line.strip()
            if stripped and "Error" in stripped:
                return stripped

        # Last non-empty line from stdout
        lines = [l.strip() for l in stdout.splitlines() if l.strip()]
        if lines:
            return lines[-1]

        # Last non-empty line from stderr
        lines = [l.strip() for l in stderr.splitlines() if l.strip()]
        if lines:
            return lines[-1]

        return f"Exit code {exit_code}"

    # ── Convenience: Run all planned (non-committed) waves ────────────────

    async def run_all_planned(self) -> list[WaveCycleResult]:
        """Run all waves from the plan that are not yet committed.

        Waves are executed in plan order.
        """
        plan = self._plan_manager.load()
        results: list[WaveCycleResult] = []

        for wave in plan.waves:
            if wave.is_committed():
                logger.info("Skipping already-committed wave %s", wave.id)
                continue

            result = await self.run_wave(wave.id)
            results.append(result)

            if not result.success:
                logger.warning(
                    "Stopping at wave %s due to failure", wave.id
                )
                break

        return results
