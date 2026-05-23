"""Engagement content context loading for agent awareness.

Provides :class:`~harness.context.loader.ContextLoader` which generates
compact, structured file inventories of the engagement space, giving
agents awareness of what files exist at session start.

Wave 14 — R23: Engagement File Context Loading.
"""

from harness.context.loader import ContextBundleBuilder, ContextLoader

__all__ = ["ContextLoader", "ContextBundleBuilder"]
