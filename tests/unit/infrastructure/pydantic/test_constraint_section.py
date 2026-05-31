"""Tests for infrastructure/pydantic/constraint_section.py."""

from __future__ import annotations

import pytest

from harness.infrastructure.pydantic.constraint_section import ConstraintSection


class TestConstraintSection:
    def test_defaults(self):
        cs = ConstraintSection()
        assert cs.backend == ""
        assert cs.model == ""
        assert cs.agent_role == ""
        assert cs.temperature is None
        assert cs.max_tokens is None
        assert cs.available_tools == []
        assert cs.budget == {}
        assert cs.fallbacks == []

    def test_typed_fields(self):
        cs = ConstraintSection(
            model="gpt-4o",
            temperature=0.7,
            max_tokens=4096,
        )
        assert cs.model == "gpt-4o"
        assert cs.temperature == 0.7
        assert cs.max_tokens == 4096

    def test_typed_backend_and_agent_role(self):
        cs = ConstraintSection(backend="api", agent_role="critical-analyser")
        assert cs.backend == "api"
        assert cs.agent_role == "critical-analyser"

    def test_get_method(self):
        cs = ConstraintSection(model="gpt-4", temperature=0.5)
        assert cs.get("model") == "gpt-4"
        assert cs.get("temperature") == 0.5
        assert cs.get("nonexistent") is None
        assert cs.get("nonexistent", "default") == "default"

    def test_get_returns_backend_field(self):
        cs = ConstraintSection(backend="api")
        assert cs.get("backend") == "api"

    def test_getitem_for_typed_field(self):
        cs = ConstraintSection(model="claude-3")
        assert cs["model"] == "claude-3"

    def test_getitem_raises_for_missing(self):
        cs = ConstraintSection()
        with pytest.raises(KeyError):
            _ = cs["nonexistent"]

    def test_available_tools_defaults_to_empty_list(self):
        cs = ConstraintSection()
        assert cs.available_tools == []

    def test_budget_defaults_to_empty_dict(self):
        cs = ConstraintSection()
        assert cs.budget == {}

    def test_tools_and_budget_with_values(self):
        cs = ConstraintSection(
            available_tools=[{"function": {"name": "test"}}],
            budget={"max_cost": 0.01},
        )
        assert len(cs.available_tools) == 1
        assert cs.budget["max_cost"] == 0.01
