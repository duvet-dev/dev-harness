"""Architecture ideal state configuration.

Defines the "ideal" architecture for a project — the pattern, layers,
and detection rules used to identify architecture debt.

Config is loaded from the project's architecture-goal file (inside
``.harness/``), with optional engagement-level overrides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from harness.paths import get_architecture_goal_path, get_engagement_dir


# ── Data model ─────────────────────────────────────────────────────────────


@dataclass
class LayerGoal:
    """A single layer in the ideal architecture.

    Attributes:
        name: Layer name (e.g. "domain", "application", "adapters").
        description: What this layer should contain.
        allowed_imports: Glob patterns for packages this layer may import.
            Empty list = no restriction.
    """

    name: str
    description: str = ""
    allowed_imports: list[str] = field(default_factory=list)


@dataclass
class DetectionRule:
    """A single rule for detecting architecture debt.

    Attributes:
        name: Machine-readable rule identifier.
        severity: ``error`` | ``warning`` | ``info``.
        description: Human-readable description of the violation.
        rule: Expression or pattern defining the violation.
    """

    name: str
    severity: str = "warning"
    description: str = ""
    rule: str = ""


@dataclass
class ArchitectureGoal:
    """Declared ideal architecture for a project.

    Attributes:
        pattern: Architecture pattern name — ``hexagonal``, ``layered``,
            ``event-driven``, ``microservices``, ``modular-monolith``.
        description: Free-text description of the ideal architecture.
        layers: Ordered list of layer definitions.
        detection_rules: Named detection rules for code scanning.
    """

    pattern: str = "layered"
    description: str = ""
    layers: list[LayerGoal] = field(default_factory=list)
    detection_rules: dict[str, DetectionRule] = field(default_factory=dict)

    @classmethod
    def default(cls) -> ArchitectureGoal:
        """Return a sensible default (layered architecture)."""
        return cls(
            pattern="layered",
            description=(
                "Standard layered architecture: domain logic is separated "
                "from application orchestration and infrastructure adapters. "
                "Each layer has clear responsibilities and dependencies flow inward."
            ),
            layers=[
                LayerGoal(
                    name="domain",
                    description="Pure business logic. Zero infrastructure imports.",
                    allowed_imports=[],
                ),
                LayerGoal(
                    name="application",
                    description="Orchestration layer. Imports domain only.",
                    allowed_imports=["domain.*"],
                ),
                LayerGoal(
                    name="adapters",
                    description="Infrastructure wrappers. Translate external → domain.",
                    allowed_imports=["domain.*", "application.*"],
                ),
            ],
        )

    def to_dict(self) -> dict:
        """Serialize to a YAML-serialisable dict."""
        return {
            "pattern": self.pattern,
            "description": self.description,
            "layers": [
                {
                    "name": l.name,
                    "description": l.description,
                    "allowed_imports": l.allowed_imports,
                }
                for l in self.layers
            ],
            "detection_rules": {
                name: {
                    "name": rule.name,
                    "severity": rule.severity,
                    "description": rule.description,
                    "rule": rule.rule,
                }
                for name, rule in self.detection_rules.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> ArchitectureGoal:
        """Deserialise from a dict loaded from YAML."""
        layers_data = data.get("layers", [])
        layers = [
            LayerGoal(
                name=l.get("name", ""),
                description=l.get("description", ""),
                allowed_imports=l.get("allowed_imports", []),
            )
            for l in layers_data
        ]

        rules_data = data.get("detection_rules", {})
        rules = {}
        for name, rule_data in rules_data.items():
            if isinstance(rule_data, dict):
                rules[name] = DetectionRule(
                    name=rule_data.get("name", name),
                    severity=rule_data.get("severity", "warning"),
                    description=rule_data.get("description", ""),
                    rule=rule_data.get("rule", ""),
                )
            elif isinstance(rule_data, str):
                rules[name] = DetectionRule(
                    name=name, description=rule_data, rule=rule_data
                )

        return cls(
            pattern=data.get("pattern", "layered"),
            description=data.get("description", ""),
            layers=layers,
            detection_rules=rules,
        )


# ── File paths ─────────────────────────────────────────────────────────────

_PROJECT_GOAL_FILENAME = "architecture-goal.yaml"
_GOAL_FILE_NAME = "architecture-goal.yaml"


# ── Load helpers ───────────────────────────────────────────────────────────


def load_architecture_goal(
    root: Path,
    engagement_slug: Optional[str] = None,
) -> ArchitectureGoal:
    """Load the architecture ideal state for a project.

    Resolution order:
    1. Engagement-level override (if ``engagement_slug`` is provided)
    2. Project-level architecture goal file
    3. Default (layered architecture)

    Args:
        root: Project root directory.
        engagement_slug: Optional engagement slug for per-engagement override.

    Returns:
        An ``ArchitectureGoal`` instance.
    """
    # 1. Engagement-level override
    if engagement_slug is not None:
        eng_path = get_engagement_dir(root, engagement_slug) / _GOAL_FILE_NAME
        if eng_path.is_file():
            with open(eng_path) as f:
                data = yaml.safe_load(f) or {}
            return ArchitectureGoal.from_dict(data)

    # 2. Project-level config
    project_path = get_architecture_goal_path(root)
    if project_path.is_file():
        with open(project_path) as f:
            data = yaml.safe_load(f) or {}
        return ArchitectureGoal.from_dict(data)

    # 3. Default
    return ArchitectureGoal.default()


def save_architecture_goal(
    root: Path,
    goal: ArchitectureGoal,
    engagement_slug: Optional[str] = None,
) -> Path:
    """Save an architecture goal to disk.

    Args:
        root: Project root directory.
        goal: The architecture goal to save.
        engagement_slug: If provided, saves as an engagement-level override.

    Returns:
        The path to the saved file.
    """
    if engagement_slug is not None:
        target = get_engagement_dir(root, engagement_slug) / _GOAL_FILE_NAME
    else:
        target = get_architecture_goal_path(root)

    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w") as f:
        yaml.dump(goal.to_dict(), f, default_flow_style=False, sort_keys=False)

    return target
