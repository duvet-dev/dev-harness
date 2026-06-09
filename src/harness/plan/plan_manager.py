"""PlanManager — read/write plan YAML and manage waves.

The plan lives as ``plan.yaml`` (structured metadata) alongside
``plan.md`` (human-readable markdown) in the engagement directory.
"""

from pathlib import Path
from typing import Optional

import yaml

from harness.paths import get_engagement_plan_md, get_engagement_plan_yaml

from .wave_model import Plan, Wave, WaveProvenance, WaveState, WaveType


class PlanManager:
    """Manages the structured plan for an engagement.

    Typical usage::

        pm = PlanManager(root, engagement_slug)
        plan = pm.load()
        plan.add_wave(Wave(id="wave-03", title="Add auth"))
        pm.save(plan)
    """

    def __init__(self, root: Path, engagement_slug: str) -> None:
        self._root = root
        self._slug = engagement_slug
        self._yaml_path = get_engagement_plan_yaml(self._root, self._slug)

    def load(self) -> Plan:
        """Load the plan from ``plan.yaml``.

        Returns an empty ``Plan`` if the file doesn't exist or is empty.
        """
        if not self._yaml_path.is_file():
            return Plan()

        with open(self._yaml_path) as f:
            data = yaml.safe_load(f) or {}
        return Plan.from_dict(data)

    def save(self, plan: Plan) -> None:
        """Persist the plan to ``plan.yaml`` and sync to ``plan.md``."""
        self._yaml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._yaml_path, "w") as f:
            yaml.dump(
                plan.to_dict(),
                f,
                default_flow_style=False,
                sort_keys=False,
            )
        self.sync_to_md(plan=plan)

    def sync_to_md(self, plan: Optional[Plan] = None) -> None:
        """Synchronise structured plan back to ``plan.md`` as a
        human-readable summary.

        This overwrites plan.md with sections for each wave.
        Call after making plan edits via the manager.
        If *plan* is not provided, it is loaded from disk.
        """
        if plan is None:
            plan = self.load()
        lines: list[str] = [
            f"# Plan: {self._slug}",
            "",
        ]

        for wave in plan.waves:
            lines.append(f"## Wave / Iteration {wave.id}: {wave.title}")
            lines.append("")
            lines.append(f"- **Type:** {wave.type}")
            lines.append(f"- **State:** {wave.state}")

            if wave.provenance is not None:
                lines.append("- **Provenance:**")
                lines.append(
                    f"  - Trigger: {wave.provenance.trigger_phase}"
                    f" — {wave.provenance.trigger_reason}"
                )
                if wave.provenance.original_wave_id:
                    lines.append(
                        f"  - Original wave: {wave.provenance.original_wave_id}"
                    )

            if wave.tasks:
                lines.append("- **Tasks:**")
                for task in wave.tasks:
                    lines.append(f"  - {task.description}")

            if wave.committed_at:
                lines.append(f"- **Committed:** {wave.committed_at}")

            lines.append("")

        if plan.priorities:
            lines.append("## Priorities")
            lines.append("")
            for key, val in plan.priorities.items():
                lines.append(f"- **{key}:** {val}")
            lines.append("")

        if plan.constraints:
            lines.append("## Constraints")
            lines.append("")
            for key, val in plan.constraints.items():
                lines.append(f"- **{key}:** {val}")
            lines.append("")

        md_path = get_engagement_plan_md(self._root, self._slug)
        md_path.write_text("\n".join(lines))

    # ── Convenience wave operations ──────────────────────────────────────

    def add_wave(
        self,
        title: str,
        wave_type: str = "standard",
        trigger_phase: Optional[str] = None,
        trigger_reason: Optional[str] = None,
        original_wave_id: Optional[str] = None,
    ) -> Wave:
        """Create and add a new wave to the plan.

        Returns the newly created ``Wave``.
        """
        plan = self.load()

        # Generate next wave ID
        existing_ids = {
            int(w.id.split("-")[-1])
            for w in plan.waves
            if w.id.startswith("wave-")
        }
        next_num = 1
        while next_num in existing_ids:
            next_num += 1
        wave_id = f"wave-{next_num:02d}"

        provenance = None
        if trigger_phase:
            provenance = WaveProvenance(
                trigger_phase=trigger_phase,
                trigger_reason=trigger_reason or "",
                original_wave_id=original_wave_id,
            )

        wave = Wave(
            id=wave_id,
            title=title,
            type=WaveType(wave_type),
            provenance=provenance,
        )
        plan.add_wave(wave)
        self.save(plan)
        self.sync_to_md()
        return wave

    def commit_wave(self, wave_id: str) -> bool:
        """Mark a wave as committed.

        If the wave declares ``resolves``, those findings are
        auto-resolved in the Findings Registry.

        Returns True if the wave was found and updated, False otherwise.
        """
        plan = self.load()
        wave = plan.get_wave(wave_id)
        if wave is None:
            return False

        # Resolve findings declared by this wave
        if wave.resolves:
            self._resolve_findings(wave)

        wave.commit()
        self.save(plan)
        self.sync_to_md()
        return True

    def _resolve_findings(self, wave: Wave) -> None:
        """Auto-resolve findings listed in wave.resolves."""
        try:
            from harness.domain.engagement.findings import FindingsStore
            store = FindingsStore(self._root, self._slug)
            resolved = store.resolve_findings_by_wave(
                wave.resolves,
                wave_name=wave.id,
                notes=wave.title,
                mark_pending=True,
            )
            if resolved:
                store.save()
        except Exception:
            pass  # Non-fatal — registry is advisory during wave commit

    def get_status(self) -> list[dict]:
        """Return a summary list of all waves with their status.

        Each entry has: id, title, type, state, is_committed, is_modifiable.
        """
        plan = self.load()
        return [
            {
                "id": w.id,
                "title": w.title,
                "type": str(w.type),
                "state": str(w.state),
                "is_committed": w.is_committed(),
                "is_modifiable": w.is_modifiable(),
                "has_provenance": w.provenance is not None,
            }
            for w in plan.waves
        ]

    def set_wave_state(self, wave_id: str, state: str) -> bool:
        """Set a wave's lifecycle state.

        Valid states: planned, in_progress, committed.
        Returns True if the wave was found and updated.
        """
        plan = self.load()
        wave = plan.get_wave(wave_id)
        if wave is None:
            return False
        wave.state = WaveState(state)
        if state == "committed":
            wave.committed_at = wave.created_at  # will be overwritten by commit()
            wave.commit()  # sets proper timestamp
        self.save(plan)
        self.sync_to_md()
        return True

    def summary(self) -> str:
        """Render a compact text summary of the plan."""
        plan = self.load()
        if not plan.waves:
            return "No waves defined in plan."

        lines = [f"Plan: {len(plan.waves)} wave(s)"]
        for w in plan.waves:
            flags = []
            if w.type != WaveType.STANDARD:
                flags.append(str(w.type))
            if w.is_committed():
                flags.append("committed")
            elif w.state == WaveState.IN_PROGRESS:
                flags.append("in-progress")
            tag = f" [{', '.join(flags)}]" if flags else ""
            lines.append(f"  {w.id}: {w.title}{tag}")
        return "\n".join(lines)
