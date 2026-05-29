"""CLI-to-CommandBus mapping layer.

Provides factory functions and a dispatch helper that translate
Click CLI argument patterns into CommandBus commands.

See V7 §12 Wave 8 for the design rationale.
"""

from harness.cli.commands import (
    abort_engagement_command,
    create_engagement_command,
    dispatch_cli_command,
    enter_phase_command,
    next_command,
    query_status_command,
    query_whats_next_command,
)

# Re-export the Click main group from the old monolithic cli.py
# for backward compatibility (repl.py imports from harness.cli.main).
# When both cli.py and cli/ exist, Python resolves harness.cli to
# the package, so we import the module via importlib and re-export.
from pathlib import Path
import importlib.util
import sys

_cli_py = Path(__file__).resolve().parent.parent / "cli.py"
if _cli_py.exists():
    _spec = importlib.util.spec_from_file_location(
        "harness._cli_monolith", str(_cli_py)
    )
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["harness._cli_monolith"] = _mod
        _spec.loader.exec_module(_mod)
        main = _mod.main
    else:
        from click import Group
        main = Group(name="harness", help="Dev Harness CLI")
else:
    from click import Group
    main = Group(name="harness", help="Dev Harness CLI")

__all__ = [
    "abort_engagement_command",
    "create_engagement_command",
    "dispatch_cli_command",
    "enter_phase_command",
    "next_command",
    "query_status_command",
    "query_whats_next_command",
    "main",
]
