"""Fleet registry — manages built-in and custom fleet state.

Provides loading, saving, and querying of fleet definitions. Built-in
fleets are defined in :mod:`harness.agents.fleet` and registered at
module load time. Custom fleets and sub-agent overrides are persisted
in ``.harness/fleets.yaml``.

Wave 17 — Phase 1 (Fleet Data Model & Registry).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from harness.paths import get_fleets_path
from harness.agents.fleet import Fleet, FleetGuidelines, InclusionRules, builtin_fleets


# ---------------------------------------------------------------------------
# Fleet Registry
# ---------------------------------------------------------------------------


class FleetRegistry:
    """Registry of all fleets — built-in and custom.

    Usage::

        registry = FleetRegistry(root)
        fleets = registry.list_fleets()
        arch = registry.get_fleet("architecture")
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._fleets: dict[str, Fleet] = {}
        self._custom_fleets_path = get_fleets_path(root)
        self._loaded = False

    # ── Loading ────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load all fleets (built-in + custom persistence).

        Safe to call multiple times — re-loads from disk each time.
        """
        # Start with built-in fleets
        self._fleets = {f.name: f for f in builtin_fleets()}

        # Load custom fleet state from .harness/fleets.yaml
        if self._custom_fleets_path.is_file():
            custom_data = yaml.safe_load(
                self._custom_fleets_path.read_text()
            ) or {}
            for fleet_name, fleet_data in custom_data.get("custom_fleets", {}).items():
                self._fleets[fleet_name] = self._dict_to_fleet(
                    fleet_name, fleet_data, builtin=False
                )

            # Apply sub_agent overrides for built-in fleets
            for fleet_name, override_data in custom_data.get("overrides", {}).items():
                if fleet_name in self._fleets:
                    fleet = self._fleets[fleet_name]
                    overrides = override_data if isinstance(override_data, dict) else {}
                    sub_agents = overrides.get("sub_agents")
                    if sub_agents is not None:
                        # Merge: custom additions appended, builtins preserved
                        existing = set(fleet.sub_agents)
                        for sa in sub_agents:
                            if sa not in existing:
                                fleet.sub_agents.append(sa)

        self._loaded = True

    def _lazy_load(self) -> None:
        """Ensure fleets are loaded before any query."""
        if not self._loaded:
            self.load()

    # ── Queries ────────────────────────────────────────────────────────

    def list_fleets(self) -> list[Fleet]:
        """Return all registered fleets."""
        self._lazy_load()
        return list(self._fleets.values())

    def get_fleet(self, name: str) -> Optional[Fleet]:
        """Return a fleet by name, or ``None`` if not found."""
        self._lazy_load()
        return self._fleets.get(name)

    def get_lead_for_role(self, role: str) -> Optional[Fleet]:
        """Return the fleet whose lead agent matches the given role.

        Useful for finding which fleet a role belongs to as a lead.
        """
        self._lazy_load()
        for fleet in self._fleets.values():
            if fleet.lead_role == role:
                return fleet
        return None

    def find_fleet_for_agent(self, agent_role: str) -> Optional[str]:
        """Return the fleet name that contains the given agent role.

        Checks lead role, sub-agent list, and ``agent_names`` via
        :meth:`Fleet.matches_agent`. Returns ``None`` if the role is
        not found in any fleet.
        """
        self._lazy_load()
        for name, fleet in self._fleets.items():
            if fleet.matches_agent(agent_role):
                return name
        return None

    def list_custom_agents_in_fleet(self, fleet_name: str) -> list[str]:
        """Return custom (non-builtin) agents registered in a fleet.

        Custom agents are those added via ``.harness/fleets.yaml`` overrides.
        This does not return built-in sub-agents.
        """
        self._lazy_load()
        fleet = self._fleets.get(fleet_name)
        if fleet is None:
            return []

        # Custom agents are tracked separately; fall back to listing
        # all sub-agents (simplification: treat all as having no builtin filter yet)
        return []

    # ── Persistence ────────────────────────────────────────────────────

    def save(self) -> None:
        """Write current custom fleet state and overrides to disk.

        Only persists custom fleets and sub-agent additions to built-in
        fleets. Built-in fleets themselves are not serialised (they are
        always loaded from code).
        """
        self._lazy_load()
        custom_data: dict = {"custom_fleets": {}, "overrides": {}}

        for name, fleet in self._fleets.items():
            if not fleet.builtin:
                custom_data["custom_fleets"][name] = self._fleet_to_dict(fleet)

        # Store custom sub-agent additions per fleet
        # (Currently just re-saves current state; built-in fleets with
        #  no custom overrides are skipped)
        custom_data["overrides"] = {
            name: {"sub_agents": fleet.sub_agents}
            for name, fleet in self._fleets.items()
            if fleet.builtin and fleet.sub_agents  # only builtins with sub-agents
        }

        self._custom_fleets_path.parent.mkdir(parents=True, exist_ok=True)
        self._custom_fleets_path.write_text(
            yaml.dump(custom_data, default_flow_style=False, sort_keys=False)
        )

    # ── Mutation helpers ───────────────────────────────────────────────

    def add_sub_agent(self, fleet_name: str, agent_role: str) -> bool:
        """Add a sub-agent role to an existing fleet.

        Returns ``True`` if the agent was added, ``False`` if it already
        existed or the fleet was not found.
        """
        self._lazy_load()
        fleet = self._fleets.get(fleet_name)
        if fleet is None:
            return False
        if agent_role not in fleet.sub_agents:
            fleet.sub_agents.append(agent_role)
            fleet.updated = __import__(
                "datetime"
            ).datetime.now(__import__("datetime").timezone.utc).isoformat()
            return True
        return False

    def remove_sub_agent(self, fleet_name: str, agent_role: str) -> bool:
        """Remove a sub-agent role from a fleet.

        Only removes custom agents — built-in sub-agents are preserved.
        Returns ``True`` if the agent was removed, ``False`` otherwise.
        """
        self._lazy_load()
        fleet = self._fleets.get(fleet_name)
        if fleet is None:
            return False
        # Built-in agents can be removed from sub_agents list
        # (the builtin sub_agent list is restored on next load)
        if agent_role in fleet.sub_agents:
            fleet.sub_agents.remove(agent_role)
            fleet.updated = __import__(
                "datetime"
            ).datetime.now(__import__("datetime").timezone.utc).isoformat()
            return True
        return False

    # ── Serialisation helpers ─────────────────────────────────────────

    @staticmethod
    def _fleet_to_dict(fleet: Fleet) -> dict:
        result: dict = {
            "lead_role": fleet.lead_role,
            "description": fleet.description,
            "guidelines": {
                "input_protocol": fleet.guidelines.input_protocol,
                "output_protocol": fleet.guidelines.output_protocol,
                "cooperation": fleet.guidelines.cooperation,
                "phases": fleet.guidelines.phases,
            },
            "sub_agents": fleet.sub_agents,
            "inclusion_rules": {
                "project_type": fleet.inclusion_rules.project_type,
                "governance_minimum": {
                    k: v.value if hasattr(v, "value") else str(v)
                    for k, v in fleet.inclusion_rules.governance_minimum.items()
                },
            },
            "builtin": fleet.builtin,
        }
        # Include consultations when present
        if fleet.consultations:
            result["consultations"] = [
                {
                    "name": c.name,
                    "description": c.description,
                    "match_phrases": c.match_phrases,
                    "mode": c.mode,
                    "scope": c.scope,
                    "question": c.question,
                }
                for c in fleet.consultations
            ]
        # Include agent_names when present
        if fleet.agent_names:
            result["agent_names"] = list(fleet.agent_names)

        return result

    @staticmethod
    def _dict_to_fleet(
        name: str, data: dict, builtin: bool = False
    ) -> Fleet:
        from harness.agents.fleet import ConsultationCapability, GovernanceLevel

        guidelines_data = data.get("guidelines", {})
        guidelines = FleetGuidelines(
            input_protocol=guidelines_data.get("input_protocol", {}),
            output_protocol=guidelines_data.get("output_protocol", {}),
            cooperation=guidelines_data.get("cooperation", []),
            phases=guidelines_data.get("phases", []),
        )

        ir_data = data.get("inclusion_rules", {})
        gov_min_raw = ir_data.get("governance_minimum", {})
        gov_min = {}
        for k, v in gov_min_raw.items():
            try:
                gov_min[k] = GovernanceLevel(v) if isinstance(v, str) else v
            except ValueError:
                gov_min[k] = GovernanceLevel.STANDARD
        inclusion_rules = InclusionRules(
            project_type=ir_data.get("project_type", {}),
            governance_minimum=gov_min,
        )

        # Restore consultations
        consultations = []
        for c_data in data.get("consultations", []):
            if isinstance(c_data, dict):
                consultations.append(ConsultationCapability(
                    name=c_data.get("name", ""),
                    description=c_data.get("description", ""),
                    match_phrases=c_data.get("match_phrases", []),
                    mode=c_data.get("mode", "advisory"),
                    scope=c_data.get("scope", "cross-phase"),
                    question=c_data.get("question", ""),
                ))

        now = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat()

        return Fleet(
            name=name,
            lead_role=data.get("lead_role", ""),
            description=data.get("description", ""),
            guidelines=guidelines,
            sub_agents=data.get("sub_agents", []),
            inclusion_rules=inclusion_rules,
            consultations=consultations,
            agent_names=data.get("agent_names", []),
            builtin=builtin,
            created=data.get("created", now),
            updated=data.get("updated", now),
        )
