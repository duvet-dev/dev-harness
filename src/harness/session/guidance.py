"""Session type guidance injection — V7 §12 (Wave 9).

Provides:
- ``get_guidance(session_type, constitution)`` —  get guidance text for a
  session type from the constitution
- ``SessionGuidanceInjector`` —  injects guidance into planning agent prompts
"""

from __future__ import annotations

import logging
from typing import Optional

from harness.constitution.models import BoundaryConfig, Constitution, SessionTypeConfig

logger = logging.getLogger(__name__)

# ── Default guidance texts ────────────────────────────────────────────────

_DEFAULT_GUIDANCE: dict[str, str] = {
    "greenfield": (
        "Build new features without backward compatibility constraints. "
        "You are creating a fresh codebase from scratch."
    ),
    "refactoring": (
        "Preserve existing interfaces. The first wave must be boundary tests "
        "to establish behaviour-preserving guard rails."
    ),
    "get-well": (
        "Fix broken tests first. Boundaries may be restructured with explicit "
        "override only (--allow-boundary-refactoring)."
    ),
    "brownfield": (
        "Work within an existing codebase. Document compromises and maintain "
        "backward compatibility for public interfaces."
    ),
}


def get_guidance(
    session_type: str,
    constitution: Optional[Constitution] = None,
) -> str:
    """Return guidance text for a given session type.

    Resolution order:
    1. ``constitution.session_types[name].guidance`` (legacy top-level)
    2. ``constitution.boundary.session_types[name].guidance`` (new-style)
    3. Built-in default for known session types
    4. Empty string if nothing is configured

    Parameters
    ----------
    session_type:
        The session type name (e.g. ``\"refactoring\"``, ``\"greenfield\"``).
    constitution:
        Optional ``Constitution`` instance. If provided, constitution
        guidance takes precedence over built-in defaults.

    Returns
    -------
    str
        Guidance text, possibly empty.
    """
    # 1. Check constitution.session_types (legacy top-level)
    if constitution is not None:
        st = constitution.session_types.get(session_type)
        if st is not None and st.guidance:
            return st.guidance

    # 2. Check constitution.boundary.session_types (new-style)
    if constitution is not None:
        st = constitution.boundary.session_types.get(session_type)
        if st is not None and st.guidance:
            return st.guidance

    # 3. Built-in default
    return _DEFAULT_GUIDANCE.get(session_type, "")


class SessionGuidanceInjector:
    """Injects session-type guidance text into planning agent prompts.

    Usage::
        injector = SessionGuidanceInjector(constitution)
        full_prompt = injector.inject(base_prompt, "refactoring")
    """

    def __init__(self, constitution: Optional[Constitution] = None) -> None:
        self._constitution = constitution

    def inject(
        self,
        base_prompt: str,
        session_type: str,
    ) -> str:
        """Append session-type guidance to a base prompt.

        Parameters
        ----------
        base_prompt:
            The existing prompt text to extend.
        session_type:
            The session type name.

        Returns
        -------
        str
            ``base_prompt`` with guidance appended (as a new section).
        """
        guidance = get_guidance(session_type, self._constitution)
        if not guidance:
            return base_prompt

        return f"{base_prompt}\n\n## Session Guidance ({session_type})\n\n{guidance}"


def should_enforce_boundary_tests(
    session_type: str,
    constitution: Optional[Constitution] = None,
) -> bool:
    """Determine whether boundary tests should be enforced for a session type.

    Resolution order:
    1. ``constitution.session_types[name].enforce_boundary_tests`` (legacy)
    2. ``constitution.boundary.session_types[name].enforce_boundary_tests`` (new)
    3. ``constitution.boundary.enforcement_default`` (global default)
    4. ``True`` (fallback)

    Parameters
    ----------
    session_type:
        The session type name.
    constitution:
        Optional ``Constitution`` instance.

    Returns
    -------
    bool
    """
    if constitution is not None:
        # 1. Legacy top-level session_types
        st = constitution.session_types.get(session_type)
        if st is not None and st.enforce_boundary_tests is not None:
            return st.enforce_boundary_tests

        # 2. New-style boundary.session_types
        st = constitution.boundary.session_types.get(session_type)
        if st is not None and st.enforce_boundary_tests is not None:
            return st.enforce_boundary_tests

        # 3. Global default
        return constitution.boundary.enforcement_default

    return True  # 4. Fallback
