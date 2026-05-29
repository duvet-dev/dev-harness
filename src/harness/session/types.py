"""Session type detection and handling.

Provides:
- ``SessionType`` enum (GREENFIELD, BROWNFIELD, REFACTORING)
- ``detect_session_type()`` — infer from a requirements prompt
- ``confirm_session_type()`` — interactive user confirmation
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from harness.paths import get_engagement_yaml


# ── SessionType — backward-compatible shim ────────────────────────────────
# SessionType was formerly a ``(str, enum.Enum)``. Session types are now
# config-driven from constitution.yaml. The class below provides backward-
# compatible attribute access so that existing code like
# ``SessionType.REFACTORING`` continues to resolve to ``"refactoring"``.


class _SessionType(str):
    """Backward-compatible shim replacing the former SessionType enum.

    Provides the same attribute access (``SessionType.REFACTORING`` →
    ``"refactoring"``). No longer an enum — use string values for new code.
    """

    GREENFIELD = "greenfield"
    BROWNFIELD = "brownfield"
    REFACTORING = "refactoring"
    GET_WELL = "get-well"

    _VALID = frozenset({"greenfield", "brownfield", "refactoring", "get-well"})

    def __new__(cls, value: str) -> str:
        """Allow ``SessionType("greenfield")`` style construction."""
        if value in cls._VALID:
            return value
        raise ValueError(f"'{value}' is not a valid SessionType")


# Export under the original name for backward compatibility
SessionType = _SessionType


# ── Detection constants ────────────────────────────────────────────────────

_REFACTORING_KEYWORDS = {
    "refactor", "restructure", "migrate", "migration",
    "rewrite", "extract", "decouple", "untangle",
    "clean up", "cleanup", "modernise", "modernize",
    "pay down debt", "technical debt", "tech debt",
}

_BROWNFIELD_KEYWORDS = {
    "existing", "legacy", "current", "old code",
    "modify", "update", "extend", "enhance",
    "already written", "on top of", "within",
    "add to", "change", "fix", "patch",
}


def detect_session_type(prompt: str) -> Optional[SessionType]:
    """Infer the likely session type from a requirements prompt.

    Returns ``None`` when the signal is too weak to make a suggestion
    (caller should default to GREENFIELD).

    Detection heuristic (rough priority order):
    1. If strong refactoring keywords present → REFACTORING
    2. If talk of existing/legacy code → BROWNFIELD
    3. Otherwise → ``None`` (caller picks GREENFIELD)
    """
    lower = prompt.lower()

    # Strong signal: refactoring language
    if any(kw in lower for kw in _REFACTORING_KEYWORDS):
        return SessionType.REFACTORING

    # Moderate signal: existing-code language
    if any(kw in lower for kw in _BROWNFIELD_KEYWORDS):
        return SessionType.BROWNFIELD

    return None


_SESSION_TYPE_VALUES = ["greenfield", "brownfield", "refactoring", "get-well"]


def confirm_session_type(suggested: str) -> Optional[str]:
    """Ask the user to confirm a suggested session type.

    Returns the confirmed type, or ``None`` if the user says no to all
    (caller should fall back to GREENFIELD or ask explicitly).
    """
    labels = {
        SessionType.REFACTORING: "refactoring (restructure code toward ideal architecture)",
        SessionType.BROWNFIELD: "brownfield (work within existing code, document compromises)",
    }

    label = labels.get(suggested, suggested)
    print(f"\nThis looks like a {label} task.")


    while True:
        choice = input(f"Start a {suggested} session? [Y/n] ").strip().lower()
        if choice in ("", "y", "yes"):
            return suggested
        if choice in ("n", "no"):
            other = _prompt_alternative(suggested)
            if other is not None:
                return other
            return None
        print("Please answer Y or n.")


def _prompt_alternative(rejected: str) -> Optional[str]:
    """Prompt for an alternative type when the user rejects the suggestion."""
    remaining = [t for t in _SESSION_TYPE_VALUES if t != rejected]

    print("\nChoose a session type:")
    for i, t in enumerate(remaining, 1):
        print(f"  {i}. {t}")
    print(f"  {len(remaining) + 1}. Cancel (use greenfield)")

    try:
        n = int(input("Enter number: ").strip())
        if 1 <= n <= len(remaining):
            return remaining[n - 1]
    except (ValueError, EOFError):
        pass

    return None  # fall back to greenfield


def store_session_type(
    root: Path,
    slug: str,
    session_type: SessionType,
) -> None:
    """Write session type into the engagement's ``engagement.yaml``.

    Creates or updates ``.harness/engagements/<slug>/engagement.yaml``
    with the ``session_type`` field.
    """
    import yaml

    eng_yaml = get_engagement_yaml(root, slug)
    if eng_yaml.is_file():
        with open(eng_yaml) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    data["session_type"] = session_type
    eng_yaml.parent.mkdir(parents=True, exist_ok=True)
    with open(eng_yaml, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def read_session_type(root: Path, slug: str) -> Optional[SessionType]:
    """Read session type from the engagement's ``engagement.yaml``.

    Returns ``None`` if not yet set (defaults to GREENFIELD downstream).
    """
    import yaml


    eng_yaml = get_engagement_yaml(root, slug)
    if not eng_yaml.is_file():
        return None

    with open(eng_yaml) as f:
        data = yaml.safe_load(f) or {}

    raw = data.get("session_type")
    if raw is not None:
        try:
            return SessionType(raw)
        except ValueError:
            return None
    return None
