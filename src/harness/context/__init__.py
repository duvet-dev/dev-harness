"""Engagement content context loading for agent awareness.

Provides :class:`~harness.context.loader.ContextLoader` which generates
compact, structured file inventories of the engagement space, giving
agents awareness of what files exist at session start.

Wave 5b adds :class:`~harness.context.delta_context.DeltaContext` for
tracking cumulative context changes across phase transitions, and
:class:`~harness.context.pass_through_context.PassThroughContext` for
recording unchanged context that can be skipped during artifact
passing.

Wave 14 — R23: Engagement File Context Loading.
"""

from harness.context.delta_context import DeltaContext
from harness.context.loader import ContextBundleBuilder, ContextLoader
from harness.context.pass_through_context import PassThroughContext

__all__ = [
    "ContextLoader",
    "ContextBundleBuilder",
    "DeltaContext",
    "PassThroughContext",
]
