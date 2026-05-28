"""Session type detection and handling.

Provides:
- ``SessionType`` enum (GREENFIELD, BROWNFIELD, REFACTORING)
- ``detect_session_type()`` — infer from a requirements prompt
- ``confirm_session_type()`` — interactive user confirmation
"""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Optional

from harness.paths import get_engagement_yaml


class SessionType(str, enum.Enum):
    """The type of development session to run.

    * **GREENFIELD** — Build from scratch. No existing-code constraints.
    * **BROWNFIELD** — Work within an existing codebase. Agents understand
      they are constrained by what already exists and document compromises.
    * **REFACTORING** — Restructure existing code toward an ideal architecture.
      Uses behaviour-preserving boundary tests as guard rails.
    * **GET_WELL** — Remediation-driven session: loads assessment findings,
      triages them, designs a cohesive remediation plan, then executes it
      through the standard phase pipeline.
    """

    GREENFIELD = "greenfield"
    BROWNFIELD = "brownfield"
    REFACTORING = "refactoring"
    GET_WELL = "get-well"


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


def confirm_session_type(suggested: SessionType) -> Optional[SessionType]:
    """Ask the user to confirm a suggested session type.

    Returns the confirmed type, or ``None`` if the user says no to all
    (caller should fall back to GREENFIELD or ask explicitly).
    """
    labels = {
        SessionType.REFACTORING: "refactoring (restructure code toward ideal architecture)",
        SessionType.BROWNFIELD: "brownfield (work within existing code, document compromises)",
    }

    label = labels.get(suggested, suggested.value)
    print(f"\nThis looks like a {label} task.")


    while True:
        choice = input(f"Start a {suggested.value} session? [Y/n] ").strip().lower()
        if choice in ("", "y", "yes"):
            return suggested
        if choice in ("n", "no"):
            other = _prompt_alternative(suggested)
            if other is not None:
                return other
            return None
        print("Please answer Y or n.")


def _prompt_alternative(rejected: SessionType) -> Optional[SessionType]:
    """Prompt for an alternative type when the user rejects the suggestion."""
    remaining = [t for t in SessionType if t != rejected]

    print("\nChoose a session type:")
    for i, t in enumerate(remaining, 1):
        print(f"  {i}. {t.value}")
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

    data["session_type"] = session_type.value
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
