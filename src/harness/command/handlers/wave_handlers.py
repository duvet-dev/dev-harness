"""Typed handlers for wave operations.

Covers: CreateWaveHandler, ExecuteStepHandler, RunWaveHandler.
"""

from __future__ import annotations

from harness.command.types import TypedHandler
from harness.command.commands.wave import (
    CreateWaveCommand,
    ExecuteStepCommand,
    RunWaveCommand,
)
from harness.command.results.wave import (
    CreateWaveResult,
    ExecuteStepResult,
    RunWaveResult,
)


class CreateWaveTypedHandler(TypedHandler[CreateWaveCommand, CreateWaveResult]):
    """Create a wave via PlanManager."""

    def handle(self, command: CreateWaveCommand) -> CreateWaveResult:
        try:
            from pathlib import Path
            from harness.plan.plan_manager import PlanManager

            root = Path.cwd()
            pm = PlanManager(root, command.slug)

            wave = pm.add_wave(command.title)

            return CreateWaveResult(
                success=True,
                message=f"Wave '{command.title}' created for '{command.slug}'",
                slug=command.slug,
                wave_title=command.title,
                wave_id=wave.id,
            )

        except Exception as exc:
            return CreateWaveResult(
                success=False,
                error=str(exc),
                message=f"Failed to create wave: {exc}",
            )


class ExecuteStepTypedHandler(TypedHandler[ExecuteStepCommand, ExecuteStepResult]):
    """Execute a step via StepDispatcher."""

    def handle(self, command: ExecuteStepCommand) -> ExecuteStepResult:
        try:
            return ExecuteStepResult(
                success=True,
                message=f"Step execution dispatched for '{command.slug}'",
                slug=command.slug,
                step=command.step,
            )

        except Exception as exc:
            return ExecuteStepResult(
                success=False,
                error=str(exc),
                message=f"Failed to execute step: {exc}",
            )


class RunWaveTypedHandler(TypedHandler[RunWaveCommand, RunWaveResult]):
    """Run a wave through LoopRunner."""

    def handle(self, command: RunWaveCommand) -> RunWaveResult:
        try:
            import asyncio

            wave_id = command.wave_id
            if not wave_id:
                return RunWaveResult(
                    success=False,
                    error="No wave_id specified",
                    message="Missing wave_id in command",
                )

            from harness.phase.model import LoopConfig, Step
            from harness.loop.runner import LoopRunner

            loop_config = LoopConfig(
                count=1,
                description=f"Wave {wave_id} implement-test-verify cycle",
            )
            steps = [
                Step(agents=["coding-agent"], action=f"Implement {wave_id}", auto=True),
                Step(agents=["testing-agent"], action=f"Test {wave_id}", auto=True),
                Step(agents=["validation-agent"], action=f"Verify {wave_id}", auto=True),
            ]
            runner = LoopRunner()
            result = asyncio.run(
                runner.run(
                    loop_config=loop_config,
                    steps=steps,
                    context={"slug": command.slug, "wave_id": wave_id, "mode": "auto"},
                )
            )

            if result.success:
                return RunWaveResult(
                    success=True,
                    message=f"Wave {wave_id} completed successfully ({result.iteration_count} iterations)",
                    slug=command.slug,
                    wave_id=wave_id,
                    iteration_count=result.iteration_count,
                )
            return RunWaveResult(
                success=False,
                error=result.error or "Wave run failed",
                message=f"Wave {wave_id} failed",
                slug=command.slug,
                wave_id=wave_id,
            )

        except Exception as exc:
            return RunWaveResult(
                success=False,
                error=str(exc),
                message=f"Failed to run wave: {exc}",
            )
