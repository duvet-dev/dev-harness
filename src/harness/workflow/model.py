"""Workflow data model.

Defines the Workflow dataclass — a named collection of phases
that make up a development session lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Workflow:
    """A named collection of phases forming a development workflow.

    Attributes:
        name: Unique workflow name (e.g. "standard", "quick-fix").
        phases: Ordered list of phase names in execution order.
            Referenced by Phase definitions in phase config.
    """

    name: str
    phases: list[str] = field(default_factory=list)
