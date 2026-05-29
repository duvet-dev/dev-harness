"""Tests for Boundary Test Enforcement (R20) — Wave 9.

Covers:
- BoundaryOverride
- ConfigValidator
- PromptEnforcer
- PlanValidator
- BoundaryTestEnforcer (integration)
"""

from __future__ import annotations

import pytest

from harness.errors import BoundaryTestViolationError
from harness.planning.boundary_enforcer import (
    BoundaryOverride,
    BoundaryTestEnforcer,
    ConfigValidator,
    OverrideMode,
    PlanValidator,
    PromptEnforcer,
    is_boundary_test_wave,
)


# ── Helper: is_boundary_test_wave ─────────────────────────────────────────


class TestIsBoundaryTestWave:
    """Tests for the is_boundary_test_wave helper."""

    def test_boundary_test_type(self):
        assert is_boundary_test_wave({"type": "boundary_test"}) is True

    def test_boundary_shorthand(self):
        assert is_boundary_test_wave({"type": "boundary"}) is True

    def test_standard_type(self):
        assert is_boundary_test_wave({"type": "standard"}) is False

    def test_missing_type(self):
        assert is_boundary_test_wave({}) is False

    def test_case_insensitive(self):
        assert is_boundary_test_wave({"type": "Boundary_Test"}) is True
        assert is_boundary_test_wave({"type": "BOUNDARY"}) is True

    def test_underscore_variants(self):
        assert is_boundary_test_wave({"type": "boundary test"}) is True


# ── BoundaryOverride ──────────────────────────────────────────────────────


class TestBoundaryOverride:
    """Tests for BoundaryOverride."""

    def test_default_is_enforcing(self):
        """Default mode is ENFORCE."""
        override = BoundaryOverride()
        assert override.is_enforcing is True
        assert override.is_advisory is False

    def test_override_mode_disables(self):
        """OVERRIDE mode disables enforcement."""
        override = BoundaryOverride(mode=OverrideMode.OVERRIDE)
        assert override.is_enforcing is False
        assert override.is_advisory is False

    def test_cli_flag_disables(self):
        """CLI flag disables enforcement."""
        override = BoundaryOverride(cli_flag=True)
        assert override.is_enforcing is False
        assert override.is_advisory is True

    def test_session_type_override_disables(self):
        """Session type override disables enforcement."""
        override = BoundaryOverride(session_type_override=True)
        assert override.is_enforcing is False
        assert override.is_advisory is True

    def test_cli_flag_and_mode_override(self):
        """Both CLI flag and mode override can be set."""
        override = BoundaryOverride(
            mode=OverrideMode.OVERRIDE,
            cli_flag=True,
            session_type_override=True,
        )
        assert override.is_enforcing is False

    def test_from_config_enforce_for_refactoring(self):
        """Refactoring with enforcement=True creates enforcing override."""
        override = BoundaryOverride.from_config(
            "refactoring",
            cli_flag=False,
            enforce_boundary_tests=True,
        )
        assert override.is_enforcing is True

    def test_from_config_override_via_cli_flag(self):
        """CLI flag creates override for refactoring."""
        override = BoundaryOverride.from_config(
            "refactoring",
            cli_flag=True,
            enforce_boundary_tests=True,
        )
        assert override.is_enforcing is False

    def test_from_config_override_via_config(self):
        """enforce_boundary_tests=False creates override."""
        override = BoundaryOverride.from_config(
            "refactoring",
            cli_flag=False,
            enforce_boundary_tests=False,
        )
        assert override.is_enforcing is False

    def test_from_config_greenfield_always_skips(self):
        """Greenfield always creates override regardless of config."""
        override = BoundaryOverride.from_config(
            "greenfield",
            cli_flag=False,
            enforce_boundary_tests=True,
        )
        assert override.is_enforcing is False

    def test_from_config_greenfield_cli_flag_ignored(self):
        """Greenfield with cli_flag is still overridden (already)."""
        override = BoundaryOverride.from_config(
            "greenfield",
            cli_flag=True,
            enforce_boundary_tests=False,
        )
        assert override.is_enforcing is False

    def test_to_dict_and_from_dict(self):
        """Serialisation round-trip."""
        original = BoundaryOverride(
            mode=OverrideMode.OVERRIDE,
            cli_flag=True,
            session_type_override=False,
        )
        data = original.to_dict()
        restored = BoundaryOverride.from_dict(data)
        assert restored.is_enforcing == original.is_enforcing
        assert restored.is_advisory == original.is_advisory


# ── ConfigValidator ───────────────────────────────────────────────────────


class TestConfigValidator:
    """Tests for ConfigValidator (Mechanism 1)."""

    def test_validates_boundary_test_wave(self):
        """First wave as boundary_test passes validation."""
        validator = ConfigValidator(BoundaryOverride())
        # Should not raise
        validator.validate("refactoring", [{"type": "boundary_test"}])

    def test_validates_boundary_wave_shorthand(self):
        """First wave as 'boundary' also passes."""
        validator = ConfigValidator(BoundaryOverride())
        validator.validate("refactoring", [{"type": "boundary"}])

    def test_raises_on_non_boundary_first_wave(self):
        """Non-boundary-test first wave raises."""
        validator = ConfigValidator(BoundaryOverride())
        with pytest.raises(BoundaryTestViolationError) as exc:
            validator.validate("refactoring", [{"type": "standard"}])
        assert "first wave must be a boundary test" in str(exc.value)

    def test_raises_on_empty_waves(self):
        """Empty waves list raises."""
        validator = ConfigValidator(BoundaryOverride())
        with pytest.raises(BoundaryTestViolationError) as exc:
            validator.validate("refactoring", [])
        assert "waves list is empty" in str(exc.value)

    def test_skipped_when_override_active(self):
        """Override skips validation entirely."""
        override = BoundaryOverride.from_config(
            "refactoring",
            cli_flag=True,
            enforce_boundary_tests=True,
        )
        validator = ConfigValidator(override)
        # Should not raise despite first wave not being boundary test
        validator.validate("refactoring", [{"type": "standard"}])

    def test_skipped_for_greenfield(self):
        """Greenfield session skips validation."""
        override = BoundaryOverride.from_config("greenfield")
        validator = ConfigValidator(override)
        validator.validate("greenfield", [{"type": "standard"}])

    def test_default_override_is_enforcing(self):
        """Default override creates an enforcing validator."""
        validator = ConfigValidator()
        with pytest.raises(BoundaryTestViolationError):
            validator.validate("refactoring", [{"type": "standard"}])

    def test_multiple_waves_first_wave_correct(self):
        """Only first wave is checked; subsequent waves don't matter."""
        validator = ConfigValidator(BoundaryOverride())
        validator.validate(
            "refactoring",
            [
                {"type": "boundary_test"},
                {"type": "implementation"},
                {"type": "testing"},
            ],
        )


# ── PromptEnforcer ────────────────────────────────────────────────────────


class TestPromptEnforcer:
    """Tests for PromptEnforcer (Mechanism 2)."""

    def test_injects_mandatory_instruction(self):
        """Enforcement active injects mandatory instruction."""
        enforcer = PromptEnforcer(BoundaryOverride())
        result = enforcer.inject("Plan this.", "refactoring")
        assert "Plan this." in result
        assert "MANDATORY" in result
        assert "Boundary Test Requirement" in result

    def test_injects_advisory_when_override_active(self):
        """Override active injects advisory text."""
        override = BoundaryOverride.from_config(
            "refactoring",
            cli_flag=True,
            enforce_boundary_tests=True,
        )
        enforcer = PromptEnforcer(override)
        result = enforcer.inject("Plan this.", "refactoring")
        assert "Plan this." in result
        assert "MANDATORY" not in result
        assert "Guidance" in result or "guidance" in result.lower()
        assert "recommended" in result.lower()

    def test_no_injection_for_greenfield(self):
        """Greenfield gets no injection."""
        override = BoundaryOverride.from_config("greenfield")
        enforcer = PromptEnforcer(override)
        result = enforcer.inject("Plan this.", "greenfield")
        assert result == "Plan this."

    def test_no_injection_when_fully_disabled(self):
        """Fully disabled override with mode=OVERRIDE gives no injection."""
        override = BoundaryOverride(mode=OverrideMode.OVERRIDE)
        enforcer = PromptEnforcer(override)
        result = enforcer.inject("Plan this.", "refactoring")
        # Fully disabled: no advisory either
        assert result == "Plan this."

    def test_mandatory_instruction_content(self):
        """Mandatory instruction contains key phrases."""
        enforcer = PromptEnforcer(BoundaryOverride())
        result = enforcer.inject("", "refactoring")
        assert "first wave" in result.lower()
        assert "MUST" in result
        assert "boundary test" in result.lower()

    def test_advisory_instruction_content(self):
        """Advisory instruction contains recommendation language."""
        override = BoundaryOverride.from_config(
            "refactoring",
            cli_flag=True,
            enforce_boundary_tests=True,
        )
        enforcer = PromptEnforcer(override)
        result = enforcer.inject("", "refactoring")
        assert "consider" in result.lower()
        assert "recommended" in result.lower()
        assert "MANDATORY" not in result


# ── PlanValidator ─────────────────────────────────────────────────────────


class TestPlanValidator:
    """Tests for PlanValidator (Mechanism 3)."""

    def test_validates_boundary_test_wave(self):
        """First wave as boundary_test passes validation."""
        validator = PlanValidator(BoundaryOverride())
        validator.validate_plan("refactoring", {"waves": [{"type": "boundary_test"}]})

    def test_validates_boundary_shorthand(self):
        """First wave as 'boundary' passes."""
        validator = PlanValidator(BoundaryOverride())
        validator.validate_plan("refactoring", {"waves": [{"type": "boundary"}]})

    def test_raises_on_non_boundary_first_wave(self):
        """Non-boundary-test first wave raises."""
        validator = PlanValidator(BoundaryOverride())
        with pytest.raises(BoundaryTestViolationError) as exc:
            validator.validate_plan("refactoring", {"waves": [{"type": "standard"}]})
        assert "first wave must be a boundary test" in str(exc.value)

    def test_raises_on_empty_waves(self):
        """Empty waves list raises."""
        validator = PlanValidator(BoundaryOverride())
        with pytest.raises(BoundaryTestViolationError) as exc:
            validator.validate_plan("refactoring", {"waves": []})
        assert "plan has no waves" in str(exc.value)

    def test_raises_on_missing_waves_key(self):
        """Missing waves key raises."""
        validator = PlanValidator(BoundaryOverride())
        with pytest.raises(BoundaryTestViolationError) as exc:
            validator.validate_plan("refactoring", {})
        assert "no waves" in str(exc.value)

    def test_skipped_when_override_active(self):
        """Override skips validation entirely."""
        override = BoundaryOverride.from_config(
            "refactoring",
            cli_flag=True,
            enforce_boundary_tests=True,
        )
        validator = PlanValidator(override)
        # Should not raise
        validator.validate_plan("refactoring", {"waves": [{"type": "standard"}]})

    def test_skipped_for_greenfield(self):
        """Greenfield session skips validation."""
        override = BoundaryOverride.from_config("greenfield")
        validator = PlanValidator(override)
        validator.validate_plan("greenfield", {"waves": [{"type": "standard"}]})

    def test_object_style_waves(self):
        """Wave objects with 'type' attribute are checked."""
        validator = PlanValidator(BoundaryOverride())

        class WaveObj:
            type = "standard"  # not boundary_test

        with pytest.raises(BoundaryTestViolationError):
            validator.validate_plan("refactoring", {"waves": [WaveObj()]})


# ── BoundaryTestEnforcer (integration) ────────────────────────────────────


class TestBoundaryTestEnforcer:
    """Integration tests for the combined BoundaryTestEnforcer."""

    def test_creates_three_mechanisms(self):
        """BoundaryTestEnforcer creates all three mechanisms."""
        enforcer = BoundaryTestEnforcer()
        assert isinstance(enforcer.config, ConfigValidator)
        assert isinstance(enforcer.prompt, PromptEnforcer)
        assert isinstance(enforcer.plan, PlanValidator)

    def test_is_active_with_default(self):
        """Default enforcer is active."""
        enforcer = BoundaryTestEnforcer()
        assert enforcer.is_active is True

    def test_is_inactive_with_override(self):
        """Override enforcer is inactive."""
        override = BoundaryOverride.from_config(
            "refactoring",
            cli_flag=True,
            enforce_boundary_tests=True,
        )
        enforcer = BoundaryTestEnforcer(override=override)
        assert enforcer.is_active is False

    def test_from_session_config_enforce_refactoring(self):
        """Session config creates active enforcer for refactoring."""
        enforcer = BoundaryTestEnforcer.from_session_config(
            "refactoring",
            cli_flag=False,
            enforce_boundary_tests=True,
        )
        assert enforcer.is_active is True

        # All three mechanisms work
        enforcer.config.validate("refactoring", [{"type": "boundary_test"}])
        prompt = enforcer.prompt.inject("Plan.", "refactoring")
        assert "MANDATORY" in prompt
        enforcer.plan.validate_plan("refactoring", {"waves": [{"type": "boundary_test"}]})

    def test_from_session_config_override_refactoring(self):
        """CLI flag creates inactive enforcer for refactoring."""
        enforcer = BoundaryTestEnforcer.from_session_config(
            "refactoring",
            cli_flag=True,
            enforce_boundary_tests=True,
        )
        assert enforcer.is_active is False

        # Mechanisms skip/are advisory
        enforcer.config.validate("refactoring", [{"type": "standard"}])  # no raise
        prompt = enforcer.prompt.inject("Plan.", "refactoring")
        assert "MANDATORY" not in prompt
        enforcer.plan.validate_plan("refactoring", {"waves": [{"type": "standard"}]})  # no raise

    def test_from_session_config_greenfield(self):
        """Greenfield creates inactive enforcer."""
        enforcer = BoundaryTestEnforcer.from_session_config(
            "greenfield",
            cli_flag=False,
            enforce_boundary_tests=True,
        )
        assert enforcer.is_active is False

    def test_override_property(self):
        """Override property returns the stored override."""
        override = BoundaryOverride.from_config(
            "refactoring",
            cli_flag=True,
            enforce_boundary_tests=True,
        )
        enforcer = BoundaryTestEnforcer(override=override)
        assert enforcer.override is override

    def test_scenario_enforce_refactoring_blocked(self):
        """Refactoring + enforcement ON => blocked if violation."""
        enforcer = BoundaryTestEnforcer.from_session_config(
            "refactoring",
            cli_flag=False,
            enforce_boundary_tests=True,
        )
        with pytest.raises(BoundaryTestViolationError):
            enforcer.config.validate("refactoring", [{"type": "implementation"}])

        with pytest.raises(BoundaryTestViolationError):
            enforcer.plan.validate_plan("refactoring", {"waves": [{"type": "implementation"}]})

    def test_scenario_enforce_refactoring_override(self):
        """Refactoring + override => no constraint."""
        enforcer = BoundaryTestEnforcer.from_session_config(
            "refactoring",
            cli_flag=True,
            enforce_boundary_tests=True,
        )
        # None of these should raise
        enforcer.config.validate("refactoring", [{"type": "implementation"}])
        prompt = enforcer.prompt.inject("Plan.", "refactoring")
        assert "MANDATORY" not in prompt
        enforcer.plan.validate_plan("refactoring", {"waves": [{"type": "implementation"}]})

    def test_scenario_enforce_get_well_blocked(self):
        """Get-well + enforcement ON => blocked if violation."""
        enforcer = BoundaryTestEnforcer.from_session_config(
            "get-well",
            cli_flag=False,
            enforce_boundary_tests=True,
        )
        with pytest.raises(BoundaryTestViolationError):
            enforcer.config.validate("get-well", [{"type": "standard"}])

    def test_scenario_enforce_get_well_override(self):
        """Get-well + override => no constraint."""
        enforcer = BoundaryTestEnforcer.from_session_config(
            "get-well",
            cli_flag=True,
            enforce_boundary_tests=True,
        )
        enforcer.config.validate("get-well", [{"type": "standard"}])  # no raise

    def test_scenario_greenfield_no_enforcement(self):
        """Greenfield always skips enforcement."""
        enforcer = BoundaryTestEnforcer.from_session_config(
            "greenfield",
            cli_flag=False,
            enforce_boundary_tests=True,
        )
        enforcer.config.validate("greenfield", [{"type": "standard"}])  # no raise
        assert enforcer.is_active is False
