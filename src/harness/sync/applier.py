"""Applier — writes template files to a release package directory.

Uses atomic writes (write to temp file, then rename) to prevent
partial writes. Respects the NEVER-overwrite rule for tools-template.md.
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from harness.sync.mapper import MappedTemplates

logger = logging.getLogger(__name__)


@dataclass
class ApplyReport:
    """Result of applying templates to the output directory."""

    written_files: list[Path] = field(default_factory=list)
    skipped_files: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class SyncApplier:
    """Writes template files to the release package directory.

    The output directory structure is::

        <output_dir>/
            agents/<role>/identity.md
            agents/<role>/procedures.md
            standards/community-standards.md
            tools-template.md
    """

    NEVER_OVERWRITE = {"tools-template.md"}

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = (
            output_dir
            if output_dir is not None
            else Path.cwd() / "src/harness/templates/"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply(self, templates: MappedTemplates) -> ApplyReport:
        """Write all template files to the output directory.

        Creates the directory structure as needed. Returns a report
        of what was written, skipped, or errored.
        """
        report = ApplyReport()

        # Write agent templates
        for role, agent_templates in templates.agents.items():
            # identity.md
            identity_path = (
                self.output_dir / "agents" / role / "identity.md"
            )
            self._atomic_write(
                identity_path,
                agent_templates.identity,
                report,
            )

            # procedures.md
            procedures_path = (
                self.output_dir / "agents" / role / "procedures.md"
            )
            self._atomic_write(
                procedures_path,
                agent_templates.procedures,
                report,
            )

        # Write community standards
        if templates.community_standards:
            standards_path = (
                self.output_dir / "standards" / "community-standards.md"
            )
            self._atomic_write(
                standards_path,
                templates.community_standards,
                report,
            )

        # Write tools template (NEVER overwrite)
        tools_path = self.output_dir / "tools-template.md"
        self._write_tools_template(tools_path, templates.tools, report)

        return report

    def preview(self, templates: MappedTemplates) -> str:
        """Return a diff-style report without writing anything.

        Returns a human-readable description of what would change.
        """
        lines: list[str] = ["Preview: Sync Release Templates"]
        lines.append("=" * 40)

        for role in templates.agents:
            identity_exists = (
                self.output_dir / "agents" / role / "identity.md"
            ).is_file()
            procedures_exists = (
                self.output_dir / "agents" / role / "procedures.md"
            ).is_file()

            lines.append(f"\nAgent: {role}")
            lines.append(
                f"  identity.md  {'OVERWRITE' if identity_exists else 'CREATE'}"
            )
            lines.append(
                f"  procedures.md  {'OVERWRITE' if procedures_exists else 'CREATE'}"
            )

        if templates.community_standards:
            cs_exists = (
                self.output_dir / "standards" / "community-standards.md"
            ).is_file()
            lines.append(
                f"\n  community-standards.md  "
                f"{'OVERWRITE' if cs_exists else 'CREATE'}"
            )

        tools_path = self.output_dir / "tools-template.md"
        if tools_path.is_file():
            lines.append("\n  tools-template.md  SKIP (already exists)")
        else:
            lines.append("\n  tools-template.md  CREATE")

        lines.append("\n" + "=" * 40)
        lines.append(
            f"Total agents: {len(templates.agents)} | "
            f"Change records: {len(templates.changes_from_previous)}"
        )

        if templates.changes_from_previous:
            lines.append("\nChanges from previous release:")
            for agent, change in templates.changes_from_previous.items():
                lines.append(f"  {agent}: {change}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _atomic_write(
        self,
        dest: Path,
        content: str,
        report: ApplyReport,
    ) -> None:
        """Write *content* to *dest* atomically.

        Writes to a temporary file on the same filesystem, then
        renames to the target path. This prevents partial writes even
        on crash or interruption.
        """
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)

            fd, tmp_path = tempfile.mkstemp(
                dir=dest.parent,
                prefix=".tmp_",
                suffix=dest.suffix or ".md",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                    tmp_file.write(content)
                    tmp_file.flush()
                    os.fsync(tmp_file.fileno())

                os.replace(tmp_path, dest)
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            report.written_files.append(dest)

        except OSError as exc:
            report.errors.append(f"Failed to write {dest}: {exc}")

    def _write_tools_template(
        self,
        dest: Path,
        content: str | None,
        report: ApplyReport,
    ) -> None:
        """Write tools-template.md, but NEVER overwrite if it exists."""
        if dest.is_file():
            report.skipped_files.append(dest)
            logger.debug("Skipping %s — already exists (never overwrite)", dest)
            return

        if content:
            self._atomic_write(dest, content, report)
        else:
            report.skipped_files.append(dest)
