"""Editor backend — writes spec files for editor-based tools.

Produces context files (`.cursorrules`, `CONTEXT.md`, `CLAUDE.md`, etc.)
for editor agents (Cursor, Copilot, Claude Code editor mode). No
subprocess execution — writes structured markdown specs that editors
scan and use as context.

Backend name: 'editor'
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from harness.agents.backends.base import (
    AbstractBackend,
    BackendResult,
    Invocation,
)
from harness.agents.context import ContextPacket


@dataclass
class EditorBackendConfig:
    """Configuration for the editor backend."""

    output_formats: list[str] = field(default_factory=lambda: [
        "context.md",
        ".cursorrules",
    ])
    include_architecture: bool = True
    include_spec: bool = True
    include_contract: bool = True

    @classmethod
    def from_dict(cls, config: dict) -> EditorBackendConfig:
        c = cls()
        if "output_formats" in config:
            c.output_formats = config["output_formats"]
        if "include_architecture" in config:
            c.include_architecture = bool(config["include_architecture"])
        if "include_spec" in config:
            c.include_spec = bool(config["include_spec"])
        if "include_contract" in config:
            c.include_contract = bool(config["include_contract"])
        return c


class EditorBackend(AbstractBackend):
    """Backend that writes editor context files."""

    name = "editor"

    def __init__(self, config: dict | None = None):
        self._config = EditorBackendConfig.from_dict(config or {})

    async def prepare(self, packet: ContextPacket) -> Invocation:
        """Prepare an invocation — this backend is plan + execute in one.

        The editor backend doesn't have a separate run step — all work
        happens in prepare() since it's just writing files.
        """
        return Invocation(
            command="write_files",
            work_dir=str(packet.target_directory),
            input_packet=packet,
            timeout_seconds=30,
        )

    async def run(self, invocation: Invocation) -> BackendResult:
        """Write editor context files to the target directory."""
        start_time = time.monotonic()
        packet = invocation.input_packet
        if not packet:
            return BackendResult(
                status="failure",
                errors=["No context packet provided"],
                metrics={"duration_ms": 0},
            )

        work_dir = Path(invocation.work_dir or packet.target_directory)
        work_dir.mkdir(parents=True, exist_ok=True)

        artifacts: dict[str, str] = {}

        for fmt in self._config.output_formats:
            content = self._build_context(packet, fmt)
            artifacts[fmt] = content
            file_path = work_dir / fmt
            file_path.write_text(content)

        duration_ms = int((time.monotonic() - start_time) * 1000)

        return BackendResult(
            status="success",
            output_dir=str(work_dir),
            artifacts=artifacts,
            metrics={
                "duration_ms": duration_ms,
                "files_written": len(artifacts),
                "formats": self._config.output_formats,
            },
        )

    def validate_config(self, config: dict) -> list[str]:
        """Validate editor backend configuration."""
        errors: list[str] = []
        bc = EditorBackendConfig.from_dict(config)
        if not bc.output_formats:
            errors.append("output_formats must not be empty")
        return errors

    def _build_context(self, packet: ContextPacket, fmt: str) -> str:
        """Build the context file content for a given format."""
        lines: list[str] = []

        if self._config.include_spec:
            lines.extend([
                f"# Task: {packet.task_id}",
                f"## Phase: {packet.phase_name}",
                f"## Engagement: {packet.engagement_id}",
                "",
                "## Specification",
                packet.spec_content,
                "",
            ])

        if self._config.include_architecture and packet.architecture_rules:
            lines.append("## Architecture Rules")
            lines.extend(f"- {r}" for r in packet.architecture_rules)
            lines.append("")

        if self._config.include_contract:
            contract = packet.output_contract
            lines.append("## Output Contract")
            if contract.required_files:
                lines.append("### Required Files")
                lines.extend(f"- {f}" for f in contract.required_files)
                lines.append("")
            if contract.file_rules:
                lines.append("### File Rules")
                for rule in contract.file_rules:
                    lines.append(f"- Pattern: {rule.get('pattern', '?')}")
                    must = rule.get("must_contain", "")
                    if must:
                        lines.append(f"  Must contain: {must}")
                lines.append("")
            if contract.coverage_target > 0:
                lines.append(
                    f"### Coverage Target: {contract.coverage_target:.0%}"
                )
                lines.append("")

        # Add constraints section
        if packet.constraint_section:
            lines.append("## Constraints")
            for key, value in packet.constraint_section.items():
                lines.append(f"- {key}: {value}")
            lines.append("")

        return "\n".join(lines)
