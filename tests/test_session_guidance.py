"""Tests for session guidance injection (Wave 9)."""

from __future__ import annotations

import pytest

from harness.constitution.models import (
    BoundaryConfig,
    Constitution,
    ProjectInfo,
    SessionTypeConfig,
)
from harness.session.guidance import (
    SessionGuidanceInjector,
    get_guidance,
    should_enforce_boundary_tests,
)


class TestGetGuidance:
    """Tests for the get_guidance() function."""

    def test_guidance_returns_default_for_unknown_type(self):
        """Unknown session type returns empty string."""
        guidance = get_guidance("unknown-type")
        assert guidance == ""

    def test_guidance_returns_default_for_greenfield(self):
        """Greenfield gets built-in default guidance."""
        guidance = get_guidance("greenfield")
        assert "Build new features" in guidance
        assert "backward compatibility" in guidance

    def test_guidance_returns_default_for_refactoring(self):
        """Refactoring gets built-in default guidance."""
        guidance = get_guidance("refactoring")
        assert "Preserve existing interfaces" in guidance
        assert "boundary tests" in guidance

    def test_guidance_from_constitution_session_types(self):
        """Constitution.session_types takes priority over built-in default."""
        c = Constitution(
            project=ProjectInfo(name="test", template="test"),
            session_types={
                "refactoring": SessionTypeConfig(
                    guidance="Custom refactoring guidance"
                ),
            },
        )
        guidance = get_guidance("refactoring", constitution=c)
        assert guidance == "Custom refactoring guidance"

    def test_guidance_from_boundary_session_types(self):
        """Constitution.boundary.session_types is checked second."""
        c = Constitution(
            project=ProjectInfo(name="test", template="test"),
            boundary=BoundaryConfig(
                session_types={
                    "refactoring": SessionTypeConfig(
                        guidance="Boundary sub-object guidance"
                    ),
                },
            ),
        )
        guidance = get_guidance("refactoring", constitution=c)
        assert guidance == "Boundary sub-object guidance"

    def test_guidance_session_types_overrides_boundary(self):
        """Legacy constitution.session_types overrides boundary.session_types."""
        c = Constitution(
            project=ProjectInfo(name="test", template="test"),
            session_types={
                "refactoring": SessionTypeConfig(
                    guidance="Legacy top-level guidance"
                ),
            },
            boundary=BoundaryConfig(
                session_types={
                    "refactoring": SessionTypeConfig(
                        guidance="Boundary sub-object guidance (ignored)"
                    ),
                },
            ),
        )
        guidance = get_guidance("refactoring", constitution=c)
        assert guidance == "Legacy top-level guidance"

    def test_guidance_falls_back_to_builtin_when_empty_in_config(self):
        """Configured but empty guidance falls back to built-in default."""
        c = Constitution(
            project=ProjectInfo(name="test", template="test"),
            session_types={
                "refactoring": SessionTypeConfig(guidance=""),
            },
        )
        guidance = get_guidance("refactoring", constitution=c)
        assert "Preserve existing interfaces" in guidance

    def test_brownfield_has_default_guidance(self):
        """BROWNFIELD has built-in default guidance."""
        guidance = get_guidance("brownfield")
        assert "existing codebase" in guidance

    def test_get_well_has_default_guidance(self):
        """GET-WELL has built-in default guidance."""
        guidance = get_guidance("get-well")
        assert "broken tests" in guidance or "Fix broken" in guidance


class TestShouldEnforceBoundaryTests:
    """Tests for should_enforce_boundary_tests()."""

    def test_default_enforcement(self):
        """Default is True (enforcement ON)."""
        assert should_enforce_boundary_tests("refactoring") is True

    def test_greenfield_defaults_to_true_but_not_relevant(self):
        """Greenfield defaults to True (overridden by BoundaryOverride logic)."""
        # The should_enforce_boundary_tests function returns the config value
        # it's BoundaryOverride.from_config that makes greenfield skip
        assert should_enforce_boundary_tests("greenfield") is True

    def test_session_type_overrides_global_default(self):
        """Session type enforce_boundary_tests overrides global default."""
        c = Constitution(
            project=ProjectInfo(name="test", template="test"),
            boundary=BoundaryConfig(
                enforcement_default=False,
                session_types={
                    "refactoring": SessionTypeConfig(enforce_boundary_tests=True),
                },
            ),
        )
        assert should_enforce_boundary_tests("refactoring", constitution=c) is True

    def test_global_default_applies_when_no_session_type_config(self):
        """Global enforcement_default applies when session type has no override."""
        c = Constitution(
            project=ProjectInfo(name="test", template="test"),
            boundary=BoundaryConfig(enforcement_default=False),
        )
        assert should_enforce_boundary_tests("refactoring", constitution=c) is False

    def test_legacy_session_types_take_priority(self):
        """Legacy session_types takes priority over boundary.session_types."""
        c = Constitution(
            project=ProjectInfo(name="test", template="test"),
            session_types={
                "refactoring": SessionTypeConfig(enforce_boundary_tests=False),
            },
            boundary=BoundaryConfig(
                enforcement_default=True,
                session_types={
                    "refactoring": SessionTypeConfig(enforce_boundary_tests=True),
                },
            ),
        )
        assert should_enforce_boundary_tests("refactoring", constitution=c) is False

    def test_none_config_falls_back_to_builtin(self):
        """When enforce_boundary_tests is None, falls through."""
        c = Constitution(
            project=ProjectInfo(name="test", template="test"),
            session_types={
                "refactoring": SessionTypeConfig(enforce_boundary_tests=None),
            },
        )
        # Falls through to built-in default (True)
        assert should_enforce_boundary_tests("refactoring", constitution=c) is True


class TestSessionGuidanceInjector:
    """Tests for SessionGuidanceInjector."""

    def test_inject_appends_guidance(self):
        """Inject appends guidance as a new section."""
        injector = SessionGuidanceInjector()
        base = "Plan this project."
        result = injector.inject(base, "refactoring")
        assert result.startswith("Plan this project.")
        assert "Session Guidance (refactoring)" in result
        assert "Preserve existing interfaces" in result

    def test_inject_with_no_guidance_returns_base(self):
        """Inject returns base prompt unchanged when no guidance."""
        injector = SessionGuidanceInjector()
        base = "Plan this project."
        result = injector.inject(base, "unknown-type")
        assert result == base

    def test_inject_with_constitution(self):
        """Inject uses constitution guidance."""
        c = Constitution(
            project=ProjectInfo(name="test", template="test"),
            session_types={
                "refactoring": SessionTypeConfig(
                    guidance="Custom constitution guidance"
                ),
            },
        )
        injector = SessionGuidanceInjector(constitution=c)
        result = injector.inject("Plan.", "refactoring")
        assert "Custom constitution guidance" in result
