"""Tests for harness.agents.fleet_registry — FleetRegistry.

Tests fleet loading, lookup, find_fleet_for_agent, and persistence.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness.agents.fleet import Fleet, FleetGuidelines
from harness.agents.fleet_registry import FleetRegistry


class TestFleetRegistry:
    """Tests for FleetRegistry."""

    def test_initialization_loads_builtins(self, tmp_path):
        registry = FleetRegistry(tmp_path)
        registry.load()
        assert len(registry.list_fleets()) == 7

    def test_get_fleet_by_name(self, tmp_path):
        registry = FleetRegistry(tmp_path)
        registry.load()
        fleet = registry.get_fleet("architecture")
        assert fleet is not None
        assert fleet.name == "architecture"

    def test_get_fleet_nonexistent(self, tmp_path):
        registry = FleetRegistry(tmp_path)
        registry.load()
        fleet = registry.get_fleet("nonexistent")
        assert fleet is None

    def test_find_fleet_for_agent(self, tmp_path):
        registry = FleetRegistry(tmp_path)
        registry.load()
        fleet_name = registry.find_fleet_for_agent("coding-agent")
        assert fleet_name == "coding"

    def test_find_fleet_for_agent_nonexistent(self, tmp_path):
        registry = FleetRegistry(tmp_path)
        registry.load()
        fleet_name = registry.find_fleet_for_agent("unknown-agent")
        assert fleet_name is None

    def test_find_fleet_by_agent_names(self, tmp_path):
        registry = FleetRegistry(tmp_path)
        registry.load()
        # Discovery fleet has agent_names=["researcher"]
        fleet_name = registry.find_fleet_for_agent("researcher")
        assert fleet_name == "discovery"

    def test_add_custom_fleet_via_persistence(self, tmp_path):
        """Write a custom fleet via the fleets.yaml file and reload."""
        fleets_dir = tmp_path / ".harness"
        fleets_dir.mkdir(parents=True)
        fleets_file = fleets_dir / "fleets.yaml"

        custom_fleet = Fleet(
            name="custom-fleet",
            lead_role="custom-agent",
            description="Custom test fleet",
        )
        yaml_data = {
            "custom_fleets": {
                "custom-fleet": {
                    "lead_role": "custom-agent",
                    "description": "Custom test fleet",
                    "guidelines": {},
                    "sub_agents": [],
                    "inclusion_rules": {},
                    "builtin": False,
                }
            }
        }
        fleets_file.write_text(yaml.dump(yaml_data))

        registry = FleetRegistry(tmp_path)
        registry.load()
        fleet = registry.get_fleet("custom-fleet")
        assert fleet is not None
        assert fleet.name == "custom-fleet"
        assert fleet.lead_role == "custom-agent"
        # Should have 7 builtins + 1 custom = 8
        assert len(registry.list_fleets()) == 8

    def test_list_fleets_returns_all(self, tmp_path):
        registry = FleetRegistry(tmp_path)
        registry.load()
        fleets = registry.list_fleets()
        assert len(fleets) == 7

    def test_fleet_names_available(self, tmp_path):
        registry = FleetRegistry(tmp_path)
        registry.load()
        names = {f.name for f in registry.list_fleets()}
        assert "architecture" in names
        assert "coding" in names
        assert "testing" in names
        assert "review" in names
        assert "discovery" in names
        assert "planning" in names
        assert "validation" in names

    def test_get_nonexistent_empty(self, tmp_path):
        registry = FleetRegistry(tmp_path)
        registry.load()
        assert registry.get_fleet("ghost") is None

    def test_add_sub_agent(self, tmp_path):
        registry = FleetRegistry(tmp_path)
        registry.load()
        result = registry.add_sub_agent("architecture", "new-arch-agent")
        assert result is True
        fleet = registry.get_fleet("architecture")
        assert "new-arch-agent" in fleet.sub_agents

    def test_add_sub_agent_already_exists(self, tmp_path):
        registry = FleetRegistry(tmp_path)
        registry.load()
        fleet = registry.get_fleet("architecture")
        existing = list(fleet.sub_agents)
        if existing:
            result = registry.add_sub_agent("architecture", existing[0])
            assert result is False

    def test_remove_sub_agent(self, tmp_path):
        registry = FleetRegistry(tmp_path)
        registry.load()
        fleet = registry.get_fleet("architecture")
        if fleet.sub_agents:
            agent = fleet.sub_agents[0]
            result = registry.remove_sub_agent("architecture", agent)
            assert result is True
            assert agent not in fleet.sub_agents

    def test_remove_sub_agent_not_found(self, tmp_path):
        registry = FleetRegistry(tmp_path)
        registry.load()
        result = registry.remove_sub_agent("architecture", "nonexistent-agent")
        assert result is False

    def test_get_lead_for_role(self, tmp_path):
        registry = FleetRegistry(tmp_path)
        registry.load()
        fleet = registry.get_lead_for_role("coding-agent")
        assert fleet is not None
        assert fleet.name == "coding"
