"""Tests for session type config and boundary config in Constitution models (Wave 9)."""

from __future__ import annotations

import pytest

from harness.constitution.models import (
    BoundaryConfig,
    Constitution,
    ConstitutionError,
    ProjectInfo,
    SessionTypeConfig,
    default_constitution,
)


class TestSessionTypeConfig:
    """Tests for SessionTypeConfig dataclass."""

    def test_default_values(self):
        """Default SessionTypeConfig has None enforce and empty guidance."""
        cfg = SessionTypeConfig()
        assert cfg.enforce_boundary_tests is None
        assert cfg.guidance == ""

    def test_with_values(self):
        """SessionTypeConfig stores provided values."""
        cfg = SessionTypeConfig(enforce_boundary_tests=True, guidance="Test guidance")
        assert cfg.enforce_boundary_tests is True
        assert cfg.guidance == "Test guidance"

    def test_enforce_boundary_tests_false(self):
        """SessionTypeConfig with enforce_boundary_tests=False."""
        cfg = SessionTypeConfig(enforce_boundary_tests=False)
        assert cfg.enforce_boundary_tests is False
        assert cfg.guidance == ""


class TestBoundaryConfig:
    """Tests for BoundaryConfig dataclass."""

    def test_default_values(self):
        """Default BoundaryConfig has enforcement_default=True and empty session_types."""
        cfg = BoundaryConfig()
        assert cfg.enforcement_default is True
        assert cfg.session_types == {}

    def test_with_values(self):
        """BoundaryConfig stores provided values."""
        cfg = BoundaryConfig(
            enforcement_default=False,
            session_types={
                "greenfield": SessionTypeConfig(enforce_boundary_tests=False),
            },
        )
        assert cfg.enforcement_default is False
        assert "greenfield" in cfg.session_types
        assert cfg.session_types["greenfield"].enforce_boundary_tests is False


class TestConstitutionWithSessionTypes:
    """Tests for Constitution with session_types and boundary fields."""

    def test_default_constitution_has_boundary_config(self):
        """Default constitution includes boundary config with session types."""
        c = default_constitution()
        assert isinstance(c.boundary, BoundaryConfig)
        assert c.boundary.enforcement_default is True
        assert "greenfield" in c.boundary.session_types
        assert "refactoring" in c.boundary.session_types
        assert "get-well" in c.boundary.session_types

    def test_default_constitution_session_type_guidance(self):
        """Default constitution has guidance for each session type."""
        c = default_constitution()
        assert "Build new features" in c.boundary.session_types["greenfield"].guidance
        assert "Preserve existing interfaces" in c.boundary.session_types["refactoring"].guidance
        assert "Fix broken tests" in c.boundary.session_types["get-well"].guidance

    def test_default_constitution_enforcement_values(self):
        """Default constitution has correct enforcement values."""
        c = default_constitution()
        assert c.boundary.session_types["greenfield"].enforce_boundary_tests is False
        assert c.boundary.session_types["refactoring"].enforce_boundary_tests is True
        assert c.boundary.session_types["get-well"].enforce_boundary_tests is True

    def test_legacy_session_types_top_level(self):
        """Constitution can have legacy top-level session_types."""
        c = Constitution(
            project=ProjectInfo(name="test", template="test"),
            session_types={
                "custom-type": SessionTypeConfig(
                    enforce_boundary_tests=False,
                    guidance="Custom",
                ),
            },
        )
        assert "custom-type" in c.session_types
        assert c.session_types["custom-type"].guidance == "Custom"

    def test_constitution_from_dict_with_legacy_top_level(self):
        """from_dict reads legacy top-level session_types."""
        data = {
            "project": {"name": "test", "template": "test"},
            "session_types": {
                "greenfield": {"enforce_boundary_tests": False, "guidance": "Go wild"},
            },
            "boundary_test_enforcement_default": False,
        }
        c = Constitution.from_dict(data)
        # Legacy top-level fields populate boundary
        assert c.boundary.enforcement_default is False
        assert "greenfield" in c.boundary.session_types
        assert c.boundary.session_types["greenfield"].guidance == "Go wild"
        assert c.boundary.session_types["greenfield"].enforce_boundary_tests is False

    def test_constitution_from_dict_with_new_style(self):
        """from_dict reads new-style boundary sub-object."""
        data = {
            "project": {"name": "test", "template": "test"},
            "boundary": {
                "enforcement_default": True,
                "session_types": {
                    "refactoring": {"enforce_boundary_tests": True},
                    "greenfield": {"enforce_boundary_tests": False},
                },
            },
        }
        c = Constitution.from_dict(data)
        assert c.boundary.enforcement_default is True
        assert "refactoring" in c.boundary.session_types
        assert c.boundary.session_types["refactoring"].enforce_boundary_tests is True
        assert c.boundary.session_types["greenfield"].enforce_boundary_tests is False

    def test_constitution_legacy_overrides_new(self):
        """Legacy top-level fields override boundary sub-object."""
        data = {
            "project": {"name": "test", "template": "test"},
            "boundary_test_enforcement_default": False,
            "boundary": {
                "enforcement_default": True,  # overridden by legacy
            },
        }
        c = Constitution.from_dict(data)
        assert c.boundary.enforcement_default is False

    def test_constitution_from_dict_shorthand_session_type(self):
        """from_dict handles bool shorthand for session types."""
        data = {
            "project": {"name": "test", "template": "test"},
            "session_types": {
                "greenfield": False,  # shorthand
                "refactoring": True,  # shorthand
            },
        }
        c = Constitution.from_dict(data)
        assert "greenfield" in c.boundary.session_types
        assert c.boundary.session_types["greenfield"].enforce_boundary_tests is False
        assert c.boundary.session_types["refactoring"].enforce_boundary_tests is True

    def test_round_trip(self):
        """Serialisation round-trip preserves boundary config."""
        original = default_constitution()
        data = original.to_dict()
        restored = Constitution.from_dict(data)
        assert restored.boundary.enforcement_default == original.boundary.enforcement_default
        assert (
            restored.boundary.session_types["refactoring"].enforce_boundary_tests
            == original.boundary.session_types["refactoring"].enforce_boundary_tests
        )
        assert (
            restored.boundary.session_types["greenfield"].guidance
            == original.boundary.session_types["greenfield"].guidance
        )

    def test_round_trip_no_session_types(self):
        """Round-trip with no session types produces valid constitution."""
        c = Constitution(project=ProjectInfo(name="test", template="test"))
        data = c.to_dict()
        restored = Constitution.from_dict(data)
        assert restored.boundary.enforcement_default is True
        assert restored.boundary.session_types == {}

    def test_constitution_no_boundary_key_in_yaml(self):
        """Constitution.from_dict handles missing boundary config."""
        data = {"project": {"name": "test", "template": "test"}}
        c = Constitution.from_dict(data)
        assert c.boundary.enforcement_default is True
        assert c.boundary.session_types == {}
