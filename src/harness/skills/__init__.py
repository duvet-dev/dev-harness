"""Skills registry and built-in skills for the Dev Harness.

The skills subsystem manages static content blocks that are injected
into agent prompts. Skills can be project-wide (applied to all agents)
or agent-specific (applied only to named agents).

See V7 §5.22 for the WebSearchProvider protocol and §7 for the skills
config schema.
"""

from __future__ import annotations
