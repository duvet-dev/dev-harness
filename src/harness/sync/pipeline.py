"""Sync pipeline — high-level orchestration of extract → map → apply."""

from __future__ import annotations

import logging
from pathlib import Path

from harness.sync.applier import ApplyReport, SyncApplier
from harness.sync.mapper import SyncMapper
from harness.sync.openclaw_extractor import OpenClawExtractor

logger = logging.getLogger(__name__)


def run_sync(
    output_dir: Path | None = None,
    preview: bool = False,
) -> ApplyReport | str:
    """Run the full sync pipeline: extract → map → apply.

    Args:
        output_dir: Target directory for template files. If None,
            defaults to ``SyncApplier`` default (``src/harness/templates/``).
        preview: If True, returns a preview string without writing.

    Returns:
        If *preview* is True, a human-readable preview string.
        Otherwise, an ``ApplyReport`` describing what was written.
    """
    logger.info("Starting sync pipeline (extract → map → apply)")

    # Step 1: Extract
    extractor = OpenClawExtractor()
    extraction = extractor.extract_all()
    logger.info(
        "Extracted %d identities, %d procedures, %d agent defs",
        len(extraction.identities),
        len(extraction.procedures),
        len(extraction.agent_definitions),
    )

    # Step 2: Map
    mapper = SyncMapper()
    templates = mapper.map(extraction)
    logger.info(
        "Mapped %d agent templates, %d registry entries",
        len(templates.agents),
        len(templates.agent_registry),
    )

    # Step 3: Apply
    applier = SyncApplier(output_dir=output_dir)

    if preview:
        report = applier.preview(templates)
        logger.info("Preview generated — no files written")
        return report

    report = applier.apply(templates)
    logger.info(
        "Sync complete: %d written, %d skipped, %d errors",
        len(report.written_files),
        len(report.skipped_files),
        len(report.errors),
    )
    return report
