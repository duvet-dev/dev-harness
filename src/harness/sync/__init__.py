"""Sync module — OpenClaw-to-Harness release pipeline.

The sync package extracts agent configuration from OpenClaw source files,
maps them to harness template format, and applies them as release
templates. It is only used at release time.
"""

from harness.sync.applier import ApplyReport, SyncApplier
from harness.sync.mapper import AgentTemplates, MappedTemplates, SyncMapper
from harness.sync.openclaw_extractor import ExtractionResult, OpenClawExtractor
from harness.sync.pipeline import run_sync

__all__ = [
    "ExtractionResult",
    "OpenClawExtractor",
    "AgentTemplates",
    "MappedTemplates",
    "SyncMapper",
    "ApplyReport",
    "SyncApplier",
    "run_sync",
]
