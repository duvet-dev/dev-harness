"""YAML-based PlanRepository implementation.

Provides plan persistence using YAML files as the backing store.
Implements the PlanRepository protocol from domain/interfaces.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from harness.domain.identifiers import WaveId
from harness.plan.wave_model import Wave, Plan
from harness.paths import get_engagement_plan_yaml


class YamlPlanRepository:
    """YAML-based plan persistence.

    Reads and writes plan YAML from the engagement directory structure.
    """

    def __init__(self) -> None:
        self._cache: dict[str, object] = {}

    def save(self, plan: object) -> None:
        """Persist a plan as YAML."""
        if isinstance(plan, Plan):
            plan._save()

    def get(self, engagement_slug: str, root: Path) -> Optional[object]:
        """Load a plan from disk."""
        path = get_engagement_plan_yaml(root, engagement_slug)
        if not path.is_file():
            return None
        return Plan.load(root, engagement_slug)

    def commit_wave(self, wave_id: WaveId) -> bool:
        """Mark a wave as committed."""
        from harness.plan.plan_manager import PlanManager
        # Requires root context — use PlanManager directly
        return False

    def set_wave_state(self, wave_id: WaveId, state: str) -> bool:
        """Update wave state."""
        return False
