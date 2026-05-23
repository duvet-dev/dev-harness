"""Typed data structures for agent I/O.

Defines ContextPacket (the typed input contract for every agent invocation)
and OutputContract (the expected output specification). Architecture §2.3.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class ContextPacketError(Exception):
    """Raised when ContextPacket serialisation or validation fails."""


@dataclass
class OutputContract:
    """Defines what outputs an agent is expected to produce."""

    required_files: list[str] = field(default_factory=list)
    file_rules: list[dict] = field(default_factory=list)
    validate_interface: bool = False
    coverage_target: float = 0.9


@dataclass
class ContextPacket:
    """Typed input contract for every agent invocation."""

    engagement_id: str
    phase_name: str
    task_id: str
    spec_content: str
    architecture_rules: list[str] = field(default_factory=list)
    target_directory: Path = field(default_factory=lambda: Path("."))
    input_artifacts: dict[str, Path] = field(default_factory=dict)
    output_contract: OutputContract = field(default_factory=OutputContract)
    constraint_section: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """JSON serialisable for cross-process agent invocation."""
        try:
            d = asdict(self)
            d["target_directory"] = str(self.target_directory)
            d["input_artifacts"] = {
                k: str(v) for k, v in self.input_artifacts.items()
            }
            return json.dumps(d, sort_keys=True, indent=2)
        except (TypeError, ValueError) as exc:
            raise ContextPacketError(
                f"Failed to serialise ContextPacket: {exc}"
            ) from exc

    @classmethod
    def from_json(cls, data: str) -> ContextPacket:
        """Deserialise from JSON."""
        try:
            d = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ContextPacketError(
                f"Failed to parse ContextPacket JSON: {exc}"
            ) from exc

        return cls(
            engagement_id=d.get("engagement_id", ""),
            phase_name=d.get("phase_name", ""),
            task_id=d.get("task_id", ""),
            spec_content=d.get("spec_content", ""),
            architecture_rules=d.get("architecture_rules", []),
            target_directory=Path(d.get("target_directory", ".")),
            input_artifacts={
                k: Path(v) for k, v in d.get("input_artifacts", {}).items()
            },
            output_contract=OutputContract(
                required_files=d.get("output_contract", {}).get(
                    "required_files", []
                ),
                file_rules=d.get("output_contract", {}).get("file_rules", []),
                validate_interface=d.get("output_contract", {}).get(
                    "validate_interface", False
                ),
                coverage_target=d.get("output_contract", {}).get(
                    "coverage_target", 0.9
                ),
            ),
            constraint_section=d.get("constraint_section", {}),
        )
