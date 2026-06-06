"""PhaseSource — bridge between phases.yaml and session dict format.

Loads phase definitions from ``.harness/phases.yaml`` (via the existing
:func:`bootstrap_phases` infrastructure) and converts them to the dict
format expected by session orchestrators, commands, and helpers.

The dict format follows the original PHASES convention:
    name, title, agent (from lead_agent), teams (from step definitions),
    system_prompt (from Phase object), artifact (derived filename).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from harness.paths import get_harness_dir

logger = logging.getLogger(__name__)


# ── Phase-to-dict formats ──────────────────────────────────────────────────

# Mapping of phase name → display title
_DEFAULT_TITLES: dict[str, str] = {
    "discover": "Requirements Gathering",
    "design": "Architecture & Design",
    "build": "Implementation",
    "review": "Review & Polish",
    "test": "Testing & Validation",
    "validate": "Validation & Sign-Off",
    "deliver": "Delivery & Documentation",
    "assess": "Analyse & Understand",
    "refactor": "Refactoring",
    "fix": "Bug Fixing",
    "triage": "Assessment Triage & Prioritisation",
    "audit": "Audit & Compliance",
    "report": "Reporting",
}

# Mapping of phase name → artifact filename
_DEFAULT_ARTIFACTS: dict[str, str] = {
    "discover": "requirements.md",
    "design": "design.md",
    "build": "implementation.md",
    "review": "review.md",
    "test": "testing.md",
    "validate": "validation.md",
    "deliver": "delivery.md",
    "assess": "assessment.md",
    "refactor": "refactoring.md",
    "fix": "fix.md",
    "triage": "triage.md",
    "audit": "audit.md",
    "report": "report.md",
}

# Default teams per phase (extracted from step definitions in phases.yaml
# by scanning for team references — used as fallback if direct YAML
# reading is not possible)
_DEFAULT_TEAMS: dict[str, list[str]] = {
    "discover": ["discovery"],
    "design": ["architecture"],
    "build": ["coding", "testing"],
    "review": ["review", "architecture"],
    "test": ["testing", "coding"],
    "validate": ["validation", "architecture"],
    "deliver": [],
    "assess": ["review"],
    "refactor": ["coding", "testing"],
    "fix": ["coding", "testing"],
    "triage": [],
    "audit": ["discovery"],
    "report": ["validation"],
}


# ── Phase loading ──────────────────────────────────────────────────────────


def _extract_teams_from_steps(steps: list[dict]) -> list[str]:
    """Extract unique team names from a list of step dicts."""
    teams: list[str] = []
    seen: set[str] = set()
    for step in steps:
        team = step.get("team")
        if team and team not in seen:
            teams.append(team)
            seen.add(team)
    return teams


def _phase_to_dict(
    name: str,
    lead_agent: str = "coding-agent",
    chat_agent: str = "technical-conversationalist",
    title: str | None = None,
    teams: list[str] | None = None,
    system_prompt: str = "",
    artifact: str | None = None,
    reentry: bool = True,
) -> dict[str, Any]:
    """Convert phase metadata to the session dict format.

    The session code expects dicts with these keys:
        name, title, agent, teams, prompt, artifact
    """
    return {
        "name": name,
        "title": title or _DEFAULT_TITLES.get(name, name.title()),
        "agent": lead_agent,
        "chat_agent": chat_agent,
        "teams": teams or _DEFAULT_TEAMS.get(name, []),
        "prompt": system_prompt,
        "artifact": artifact or _DEFAULT_ARTIFACTS.get(name, f"{name}.md"),
        "reentry": reentry,
    }


def get_phases(root: Path | None = None) -> list[dict[str, Any]]:
    """Load phase definitions from ``phases.yaml`` and return session dicts.

    Uses the Phase model from :func:`harness.phase.bootstrap.bootstrap_phases`
    and converts each :class:`~harness.phase.model.Phase` to the dict format
    expected by session orchestrators.

    If ``phases.yaml`` is not found, falls back to a default set matching
    the old PHASES dict.

    Args:
        root: Project root directory. If provided, phases are loaded from
            ``root/.harness/phases.yaml``.

    Returns:
        List of phase definition dicts compatible with the session
        orchestrator format.
    """
    phases_root: Path | None = None
    if root is not None:
        phases_root = root
    else:
        # Try cwd
        try:
            phases_root = Path.cwd()
        except Exception:
            pass

    if phases_root is not None:
        harness_dir = get_harness_dir(phases_root)
        phases_yaml = harness_dir / "phases.yaml"
        if phases_yaml.is_file():
            try:
                return _load_phases_from_yaml(phases_yaml)
            except Exception as exc:
                logger.warning(
                    "get_phases — failed to load %s: %s, falling back",
                    phases_yaml,
                    exc,
                )

    # Fallback: use Phase model defaults (same as phases.yaml)
    return _load_default_phases()


def _load_phases_from_yaml(phases_yaml: Path) -> list[dict[str, Any]]:
    """Read phases.yaml and return session-compatible dicts.

    Uses low-level YAML parsing rather than the Phase model to avoid
    import tangles with the full phase orchestration machinery in
    session context.
    """
    import yaml

    raw = yaml.safe_load(phases_yaml.read_text())
    if not raw or "phases" not in raw:
        return _load_default_phases()

    raw_phases = raw["phases"]
    if not isinstance(raw_phases, list):
        return _load_default_phases()

    result: list[dict[str, Any]] = []
    for p in raw_phases:
        if not isinstance(p, dict) or "name" not in p:
            continue
        name = p["name"]
        steps = p.get("steps", [])
        teams = _extract_teams_from_steps(steps)

        system_prompt = p.get("system_prompt", "")
        title = p.get("title", _DEFAULT_TITLES.get(name, name.title()))
        reentry = p.get("reentry", False)

        d = _phase_to_dict(
            name=name,
            lead_agent=p.get("lead_agent", "coding-agent"),
            chat_agent=p.get("chat_agent", "technical-conversationalist"),
            title=title,
            teams=teams,
            system_prompt=system_prompt,
            artifact=steps[0].get("output", f"{name}.md") if steps else f"{name}.md",
            reentry=reentry,
        )
        result.append(d)

    return result


def _load_default_phases() -> list[dict[str, Any]]:
    """Return the built-in default phase list (matching phases.yaml defaults)."""
    return [
        _phase_to_dict(
            name="discover",
            lead_agent="discovery-agent",
            title="Requirements Gathering",
            teams=["discovery"],
            system_prompt=(
                "You are a Requirements Builder. Gather and document "
                "what needs to be built."
            ),
            artifact="requirements.md",
        ),
        _phase_to_dict(
            name="design",
            lead_agent="design-coordinator",
            title="Architecture & Design",
            teams=["architecture"],
            system_prompt=(
                "You are a Software Architect. Model the domain, "
                "define bounded contexts, select architectural patterns."
            ),
            artifact="design.md",
        ),
        _phase_to_dict(
            name="build",
            lead_agent="coding-agent",
            title="Implementation",
            teams=["coding", "testing"],
            system_prompt=(
                "You are a Coder. Implement features following "
                "the established architecture."
            ),
            artifact="implementation.md",
        ),
        _phase_to_dict(
            name="review",
            lead_agent="review-coordinator",
            title="Review & Polish",
            teams=["review", "architecture"],
            system_prompt=(
                "You are a Reviewer. Review current state against "
                "best practices."
            ),
            artifact="review.md",
        ),
        _phase_to_dict(
            name="test",
            lead_agent="testing-agent",
            title="Testing & Validation",
            teams=["testing", "coding"],
            system_prompt=(
                "You are a Tester. Validate implementations against "
                "acceptance criteria."
            ),
            artifact="testing.md",
        ),
        _phase_to_dict(
            name="validate",
            lead_agent="validation-agent",
            title="Validation & Sign-Off",
            teams=["validation", "architecture"],
            system_prompt=(
                "You are a Validation Agent. Verify implementation "
                "against all acceptance criteria."
            ),
            artifact="validation.md",
            reentry=False,
        ),
        _phase_to_dict(
            name="deliver",
            lead_agent="coding-agent",
            title="Delivery & Documentation",
            teams=[],
            system_prompt=(
                "You are a Delivery Agent. Prepare release notes "
                "and update documentation."
            ),
            artifact="delivery.md",
        ),
        _phase_to_dict(
            name="assess",
            lead_agent="refactoring-agent",
            title="Analyse & Understand",
            teams=["review"],
            system_prompt=(
                "You are an Analysis Agent. Understand the codebase "
                "structure and identify insertion points."
            ),
            artifact="assessment.md",
        ),
        _phase_to_dict(
            name="refactor",
            lead_agent="coding-agent",
            title="Refactoring",
            teams=["coding", "testing"],
            system_prompt=(
                "You are a Refactoring Agent. Restructure code to "
                "improve architecture and readability."
            ),
            artifact="refactoring.md",
        ),
        _phase_to_dict(
            name="fix",
            lead_agent="coding-agent",
            title="Bug Fixing",
            teams=["coding", "testing"],
            system_prompt=(
                "You are a Bug Fix Agent. Diagnose and fix defects."
            ),
            artifact="fix.md",
        ),
        _phase_to_dict(
            name="triage",
            lead_agent="critical-analyser",
            title="Assessment Triage & Prioritisation",
            teams=[],
            system_prompt=(
                "You are a Triage Agent. Analyse assessment findings "
                "and prioritise remediation."
            ),
            artifact="triage.md",
        ),
        _phase_to_dict(
            name="audit",
            lead_agent="critical-analyser",
            title="Audit & Compliance",
            teams=["discovery"],
            system_prompt=(
                "You are an Audit Agent. Conduct a comprehensive "
                "review of the codebase."
            ),
            artifact="audit.md",
        ),
        _phase_to_dict(
            name="report",
            lead_agent="documentation-agent",
            title="Reporting",
            teams=["validation"],
            system_prompt=(
                "You are a Reporting Agent. Compile findings into "
                "structured reports."
            ),
            artifact="report.md",
        ),
    ]


def get_phase_order(root: Path | None = None) -> list[str]:
    """Return the ordered list of phase names representing the default rail."""
    return [p["name"] for p in get_phases(root)]


def is_transition_allowed(
    source: str,
    destination: str,
    root: Path | None = None,
) -> tuple[bool, str]:
    """Check whether a source→destination phase transition is allowed.

    Returns a (allowed, reason) tuple. The default rail follows phase order:
    - Moving backward to any previous phase is always allowed (feedback flow)
    - Moving forward to any phase is allowed (navigate ahead)
    - Moving to the current phase is allowed (restart semantics)

    Args:
        source: Current phase name.
        destination: Target phase name.
        root: Optional project root for phase resolution.

    Returns:
        Tuple of (bool, str) where bool is whether the transition is
        allowed, and str is a human-readable reason.
    """
    phases = get_phase_order(root)
    if source not in phases:
        return False, f"Unknown source phase: {source}"
    if destination not in phases:
        return False, f"Unknown target phase: {destination}"

    source_idx = phases.index(source)
    dest_idx = phases.index(destination)
    phase_name = phases[dest_idx]

    # Allowed transitions:
    # 1. Same phase
    if source == destination:
        return True, f"Remaining in phase: {phase_name}"
    # 2. Moving backward (any previous phase)
    if dest_idx < source_idx:
        return True, f"Transition from {source} back to {phase_name}"
    # 3. Moving forward (any future phase)
    if dest_idx > source_idx:
        return True, f"Transition from {source} forward to {phase_name}"

    return False, f"Unknown transition: {source} → {destination}"


def get_phase_names(root: Path | None = None) -> list[str]:
    """Return the ordered list of phase names from phases.yaml."""
    return [p["name"] for p in get_phases(root)]


def find_phase(name: str, root: Path | None = None) -> dict[str, Any] | None:
    """Find a phase definition by name.

    Returns None if not found.
    """
    for p in get_phases(root):
        if p["name"] == name:
            return p
    return None
