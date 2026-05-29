"""Boundary Test Enforcement (R20) — V7 §11.

Three complementary mechanisms for enforcing that refactoring/get-well
sessions place boundary tests as the first wave.

1. **ConfigValidator** — validates ``waves[0].type == boundary_test`` at
   config load time.
2. **PromptEnforcer** — injects mandatory instruction into planning agent's
   system prompt.
3. **PlanValidator** — validates plan artifact after creation.

All three are disabled (or advisory) when ``BoundaryOverride`` is active.
"""

from __future__ import annotations

import enum
import logging
from typing import Any, Optional

from harness.errors import BoundaryTestViolationError

logger = logging.getLogger(__name__)


class OverrideMode(enum.Enum):
    """Whether boundary test enforcement is active or overridden."""

    ENFORCE = "enforce"
    OVERRIDE = "override"


# ── Helper ────────────────────────────────────────────────────────────────


def is_boundary_test_wave(wave: dict[str, Any]) -> bool:
    """Check if a wave dict represents a boundary test wave.

    Returns ``True`` if the wave's ``type`` is ``\"boundary_test\"``.
    Also accepts ``\"boundary\"`` as a shorthand.
    """
    wave_type = wave.get("type", "").lower().replace(" ", "_")
    return wave_type in ("boundary_test", "boundary")


# ── Override ──────────────────────────────────────────────────────────────


class BoundaryOverride:
    """Override mechanism for boundary test enforcement (R20 §11.2).

    When active, all three enforcement mechanisms are disabled or
    made advisory:
    - ConfigValidator: skipped
    - PromptEnforcer: advisory only (not mandatory)
    - PlanValidator: disabled

    Activation sources:
    - ``--allow-boundary-refactoring`` CLI flag
    - ``constitution.yaml`` ``enforce_boundary_tests: false`` (per session type)
    - Global ``boundary_test_enforcement_default: false``
    """

    def __init__(
        self,
        mode: OverrideMode = OverrideMode.ENFORCE,
        *,
        cli_flag: bool = False,
        session_type_override: bool = False,
    ) -> None:
        """Initialise with mode and optional override sources.

        Parameters
        ----------
        mode:
            Initial mode. Defaults to ENFORCE.
        cli_flag:
            ``True`` if ``--allow-boundary-refactoring`` CLI flag was set.
        session_type_override:
            ``True`` if the session type's config has
            ``enforce_boundary_tests: false``.
        """
        self._mode = mode
        self._cli_flag = cli_flag
        self._session_type_override = session_type_override

    @property
    def is_enforcing(self) -> bool:
        """``True`` when enforcement is active (i.e. not overridden)."""
        if self._mode == OverrideMode.OVERRIDE:
            return False
        if self._cli_flag or self._session_type_override:
            return False
        return True

    @property
    def is_advisory(self) -> bool:
        """``True`` when enforcement is advisory-only.

        This is ``True`` when override is active but the enforcer
        should still warn (``is_enforcing`` is ``False`` and at least
        one override source is active).
        """
        return not self.is_enforcing and (
            self._cli_flag or self._session_type_override
        )

    @classmethod
    def from_config(
        cls,
        session_type: str,
        *,
        cli_flag: bool = False,
        enforce_boundary_tests: bool = True,
    ) -> BoundaryOverride:
        """Create a ``BoundaryOverride`` from configuration.

        Parameters
        ----------
        session_type:
            The session type name.
        cli_flag:
            ``--allow-boundary-refactoring`` flag state.
        enforce_boundary_tests:
            The resolved ``enforce_boundary_tests`` value for this session
            type (with global default already applied).
        """
        # Greenfield is never subject to enforcement (V7 §11.5)
        if session_type == "greenfield":
            return cls(
                mode=OverrideMode.OVERRIDE,
                cli_flag=cli_flag,
                session_type_override=True,  # greenfield always skips
            )

        if cli_flag or not enforce_boundary_tests:
            return cls(
                mode=OverrideMode.OVERRIDE,
                cli_flag=cli_flag,
                session_type_override=not enforce_boundary_tests,
            )

        return cls(mode=OverrideMode.ENFORCE)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self._mode.value,
            "cli_flag": self._cli_flag,
            "session_type_override": self._session_type_override,
            "is_enforcing": self.is_enforcing,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BoundaryOverride:
        return cls(
            mode=OverrideMode(d.get("mode", "enforce")),
            cli_flag=d.get("cli_flag", False),
            session_type_override=d.get("session_type_override", False),
        )


# ── Mechanism 1: ConfigValidator ──────────────────────────────────────────


class ConfigValidator:
    """Mechanism 1: Schema validation at config load time (V7 §11.1).

    Validates that ``waves[0].type == \"boundary_test\"`` when enforcement
    is active. Skipped entirely when override is active.
    """

    def __init__(self, override: BoundaryOverride | None = None) -> None:
        self._override = override or BoundaryOverride()

    def validate(self, session_type: str, waves: list[dict[str, Any]]) -> None:
        """Validate that the first wave is a boundary test.

        Parameters
        ----------
        session_type:
            The session type name.
        waves:
            List of wave dicts from the plan config.

        Raises
        ------
        BoundaryTestViolationError
            If the first wave is not a boundary test and enforcement
            is active.
        """
        if not self._override.is_enforcing:
            logger.debug(
                "ConfigValidator: skipped (override active, session_type=%s)",
                session_type,
            )
            return

        if not waves:
            raise BoundaryTestViolationError(
                "ConfigValidator: waves list is empty — no waves to validate"
            )

        first_wave = waves[0]
        if not is_boundary_test_wave(first_wave):
            raise BoundaryTestViolationError(
                f"ConfigValidator: first wave must be a boundary test for "
                f"session type '{session_type}'. "
                f"Got type={first_wave.get('type', 'missing')!r}. "
                f"Use --allow-boundary-refactoring to override."
            )

        logger.debug(
            "ConfigValidator: passed (first wave is boundary test, "
            "session_type=%s)",
            session_type,
        )


# ── Mechanism 2: PromptEnforcer ──────────────────────────────────────────


class PromptEnforcer:
    """Mechanism 2: Inject boundary test instruction into planning agent prompt.

    When enforcement is active, a mandatory instruction is injected.
    When override is active, advisory-only text is injected.
    When greenfield, no injection occurs.
    """

    # Mandatory instruction (enforcement active)
    _MANDATORY_INSTRUCTION = (
        "### Boundary Test Requirement\n\n"
        "The first wave of any plan MUST be a boundary test phase. "
        "Boundary tests capture current behaviour without modifying it. "
        "All subsequent refactoring waves must preserve the interfaces "
        "defined by these boundary tests.\n\n"
        "This requirement is MANDATORY and cannot be skipped."
    )

    # Advisory instruction (override active)
    _ADVISORY_INSTRUCTION = (
        "### Boundary Test Guidance\n\n"
        "Consider starting with a boundary test phase. "
        "Boundary tests capture current behaviour and provide "
        "safety nets for subsequent refactoring. "
        "This is recommended but not enforced in this session."
    )

    def __init__(self, override: BoundaryOverride | None = None) -> None:
        self._override = override or BoundaryOverride()

    def inject(
        self,
        base_prompt: str,
        session_type: str,
    ) -> str:
        """Inject boundary test instruction into a base prompt.

        Parameters
        ----------
        base_prompt:
            The existing prompt text.
        session_type:
            The session type name.

        Returns
        -------
        str
            The prompt with the instruction appended (or unchanged).
        """
        # Greenfield: no injection
        if session_type == "greenfield":
            return base_prompt

        if self._override.is_enforcing:
            return f"{base_prompt}\n\n{self._MANDATORY_INSTRUCTION}"

        if self._override.is_advisory:
            return f"{base_prompt}\n\n{self._ADVISORY_INSTRUCTION}"

        return base_prompt


# ── Mechanism 3: PlanValidator ────────────────────────────────────────────


class PlanValidator:
    """Mechanism 3: Post-hoc plan artifact validation (V7 §11.1).

    Validates that the plan's first wave is a boundary test after the
    planning phase completes. Disabled entirely when override is active.
    """

    def __init__(self, override: BoundaryOverride | None = None) -> None:
        self._override = override or BoundaryOverride()

    def validate_plan(
        self,
        session_type: str,
        plan: dict[str, Any],
    ) -> None:
        """Validate a plan artifact after creation.

        Parameters
        ----------
        session_type:
            The session type name.
        plan:
            The plan dict with a ``waves`` list.

        Raises
        ------
        BoundaryTestViolationError
            If the first wave is not a boundary test and enforcement
            is active.
        """
        if not self._override.is_enforcing:
            logger.debug(
                "PlanValidator: skipped (override active, session_type=%s)",
                session_type,
            )
            return

        waves = plan.get("waves", [])
        if not waves:
            raise BoundaryTestViolationError(
                "PlanValidator: plan has no waves — no waves to validate"
            )

        first_wave = waves[0]
        # Support both dict-style and object-style waves
        if isinstance(first_wave, dict):
            if not is_boundary_test_wave(first_wave):
                raise BoundaryTestViolationError(
                    f"PlanValidator: first wave must be a boundary test for "
                    f"session type '{session_type}'. "
                    f"Got type={first_wave.get('type', 'missing')!r}. "
                    f"Use --allow-boundary-refactoring to override."
                )
        elif hasattr(first_wave, "type"):
            wave_type = str(getattr(first_wave, "type", "")).lower()
            if wave_type not in ("boundary_test", "boundary"):
                raise BoundaryTestViolationError(
                    f"PlanValidator: first wave must be a boundary test for "
                    f"session type '{session_type}'. "
                    f"Got type={wave_type!r}."
                )

        logger.debug(
            "PlanValidator: passed (first wave is boundary test, "
            "session_type=%s)",
            session_type,
        )


# ── Combined enforcer ────────────────────────────────────────────────────


class BoundaryTestEnforcer:
    """Three complementary mechanisms for R20 enforcement (V7 §11.4).

    Combines ``ConfigValidator``, ``PromptEnforcer``, and
    ``PlanValidator`` into a single interface.
    """

    def __init__(self, override: BoundaryOverride | None = None) -> None:
        self._override = override or BoundaryOverride()
        self.config = ConfigValidator(self._override)
        self.prompt = PromptEnforcer(self._override)
        self.plan = PlanValidator(self._override)

    @property
    def is_active(self) -> bool:
        """``True`` when enforcement mechanisms are active."""
        return self._override.is_enforcing

    @property
    def override(self) -> BoundaryOverride:
        return self._override

    @classmethod
    def from_session_config(
        cls,
        session_type: str,
        *,
        cli_flag: bool = False,
        enforce_boundary_tests: bool = True,
    ) -> BoundaryTestEnforcer:
        """Create a fully-configured enforcer from session type config.

        Parameters
        ----------
        session_type:
            The session type name.
        cli_flag:
            ``--allow-boundary-refactoring`` flag state.
        enforce_boundary_tests:
            The resolved enforcement flag for this session type.
        """
        override = BoundaryOverride.from_config(
            session_type=session_type,
            cli_flag=cli_flag,
            enforce_boundary_tests=enforce_boundary_tests,
        )
        return cls(override=override)
