"""PhaseManager — manages per-phase agent execution with Temporal fan-out.

Supports iteration feedback: when ``feedback`` is provided and
``partial_approval`` is enabled, only artifacts referenced by
``blocker`` or ``major`` severity feedback items are re-processed.
Minor/suggestion items are passed as context but don't trigger
re-execution.
"""

import asyncio
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from harness.workflows.phases.run_single_agent import run_single_agent
    from harness.workflows.activities import (
        collect_outputs,
        aggregate_phase_outputs,
        check_phase_coverage,
        snapshot_state,
    )
    from harness.workflows.signals import FeedbackItem

# Severity levels that trigger re-execution
_REEXECUTION_SEVERITIES = frozenset({"blocker", "major"})


@workflow.defn
class PhaseManager:
    """Manages execution of all agents within a single phase.

    Each agent gets its own activity with independent retry,
    timeout, and heartbeat (architecture §2.6 fan-out pattern).
    """

    @workflow.run
    async def run(self, phase_config: dict) -> dict:
        """Run all agents for this phase in parallel.

        Accepts optional ``feedback`` list and ``partial_approval`` flag
        in *phase_config*. When feedback is present:
        - If partial_approval is True, only artifacts referenced by
          blocker/major feedback items are re-processed.
        - Minor/suggestion items are appended to agent spec_content as
          additional context but don't trigger re-execution.
        """
        engagement_id = phase_config["engagement_id"]
        phase_name = phase_config["phase_name"]
        agents = phase_config.get("agents", [])
        coverage_target = phase_config.get("coverage_target", 0.9)
        partial_approval = phase_config.get("partial_approval", True)

        # Process feedback if provided
        feedback_raw = phase_config.get("feedback", [])
        feedback_items = [
            FeedbackItem.from_dict(f) if isinstance(f, dict) else f
            for f in feedback_raw
        ]

        # Determine which agents to run based on feedback filtering
        agents_to_run = self._filter_agents(agents, feedback_items, partial_approval)

        # Build context for feedback context (minor/suggestion items)
        feedback_context_lines = self._build_feedback_context_lines(feedback_items)

        # Fan-out: run agents in parallel
        agent_futures = []
        for i, agent_def in enumerate(agents_to_run):
            spec_base = agent_def.get("spec_content", "")
            # Append feedback context to spec so agents can see what needs changing
            spec_with_feedback = spec_base
            if feedback_context_lines:
                if spec_with_feedback and not spec_with_feedback.endswith("\n"):
                    spec_with_feedback += "\n"
                spec_with_feedback += "\n".join(feedback_context_lines)

            context_packet = {
                "engagement_id": engagement_id,
                "phase_name": phase_name,
                "task_id": agent_def.get("task_id", f"task-{i}"),
                "spec_content": spec_with_feedback,
                "target_directory": agent_def.get(
                    "target_directory", f"artifacts/{phase_name}/"
                ),
            }

            future = workflow.execute_activity(
                run_single_agent,
                context_packet,
                start_to_close_timeout=timedelta(minutes=32),
                heartbeat_timeout=timedelta(seconds=15),
                retry=RetryPolicy(
                    maximum_attempts=5, backoff_coefficient=1.1
                ),
            )
            agent_futures.append(future)

        # Wait for all agents
        results = await asyncio.gather(*agent_futures, return_exceptions=True)

        successful = []
        failed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed.append({"agent_index": i, "error": str(result)})
            else:
                successful.append(result)

        if failed:
            workflow.logger.warning(
                f"Phase {phase_name}: {len(failed)}/{len(agents_to_run)} agents failed"
            )

        # Collect and aggregate outputs
        all_outputs = []
        for result in successful:
            outputs = await workflow.execute_activity(
                collect_outputs,
                {
                    "target_directory": result.get("output_files", [""])[0]
                    if result.get("output_files")
                    else "",
                    "required_files": ["*"],
                },
                start_to_close_timeout=timedelta(seconds=30),
            )
            all_outputs.append(outputs)

        aggregated = await workflow.execute_activity(
            aggregate_phase_outputs,
            {"agent_outputs": all_outputs},
            start_to_close_timeout=timedelta(seconds=10),
        )

        coverage_result = await workflow.execute_activity(
            check_phase_coverage,
            {"coverage_target": coverage_target},
            start_to_close_timeout=timedelta(seconds=10),
        )

        await workflow.execute_activity(
            snapshot_state,
            {
                "engagement_id": engagement_id,
                "status": "completed" if not failed else "completed_with_errors",
                "phase": phase_name,
                "project_path": ".",
            },
            start_to_close_timeout=timedelta(seconds=10),
        )

        return {
            "phase": phase_name,
            "status": "completed" if not failed else "completed_with_errors",
            "agents_total": len(agents_to_run),
            "agents_succeeded": len(successful),
            "agents_failed": len(failed),
            "artifacts": aggregated,
            "coverage": coverage_result,
        }

    # ------------------------------------------------------------------
    # Feedback filtering helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_agents(
        agents: list[dict],
        feedback_items: list[FeedbackItem],
        partial_approval: bool,
    ) -> list[dict]:
        """Filter agents based on feedback when in partial-approval mode.

        When *partial_approval* is True and there is feedback, only return
        agents whose artifacts are referenced by blocker/major feedback.
        When there's no feedback (first run), return all agents.
        """
        if not feedback_items or not partial_approval:
            return agents

        # Collect artifact refs that need re-execution
        reexecution_refs = {
            f.artifact_ref
            for f in feedback_items
            if f.severity in _REEXECUTION_SEVERITIES
        }

        if not reexecution_refs:
            # No blocker/major items — nothing to re-execute
            return []

        # Filter agents whose target_directory or task_id matches a ref.
        # Matching is bidirectional: the artifact_ref can be a parent or
        # child path of the agent's target directory.
        filtered = []
        for agent in agents:
            agent_ref = agent.get("target_directory", "") or agent.get("task_id", "")
            if any(
                ref in agent_ref or agent_ref in ref
                for ref in reexecution_refs
            ):
                filtered.append(agent)

        return filtered if filtered else agents

    @staticmethod
    def _build_feedback_context_lines(
        feedback_items: list[FeedbackItem],
    ) -> list[str]:
        """Build context lines from feedback items for agent spec injection.

        Minor/suggestion items are included as context; blocker/major items
        indicate what specifically needs fixing.
        """
        if not feedback_items:
            return []

        lines = []
        lines.append("---")
        lines.append("Feedback from previous iteration for your reference:")

        for item in feedback_items:
            if item.suggestion:
                lines.append(
                    f"  - [{item.severity}] {item.artifact_ref}: "
                    f"{item.finding} (suggestion: {item.suggestion})"
                )
            else:
                lines.append(
                    f"  - [{item.severity}] {item.artifact_ref}: {item.finding}"
                )

        lines.append("---")
        return lines
