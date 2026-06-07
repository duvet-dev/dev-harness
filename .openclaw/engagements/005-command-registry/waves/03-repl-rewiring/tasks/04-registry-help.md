# Task 4 — Replace `/help` with REGISTRY-based generation

**Status:** 📋 Pending
**Wave:** 03-repl-rewiring
**Dependencies:** Task 3
**Effort:** 0.5h

## Description

Replace the current `/help` generation in `repl.py` (which walks `cli_main.main.commands` — the Click tree) with one that reads the `REGISTRY` directly. This eliminates the current bug where `/help` lists commands that fail at runtime.

**Crichton note #2:** Preserve group structure (── Engagement ──, ── Wave ──, etc.) by sorting REGISTRY entries by group prefix.
**Crichton note #3:** Short descriptions are fetched from the Click Command object (via `cli_main`) rather than from the registry — avoids duplicating help text.

Implementation approach:
```python
def _build_help_from_registry(self) -> list[str]:
    """Build help lines from REGISTRY, grouped by prefix."""
    from harness.command._registration import REGISTRY
    from harness.cli import main as cli_main

    lines = ["Available commands:\n"]

    # Build groups from REGISTRY
    groups = {
        "General": [],
        "Engagement": [],
        "Phase": [],
        "Wave": [],
        "Changelog": [],
        "Team/Agent": [],
        "Consult": [],
    }
    catch_all = []

    for name in sorted(REGISTRY):
        reg = REGISTRY[name]
        if reg.click_only:
            continue
        # Get group prefix
        prefix = name.split(" ")[0] if " " in name else "top"
        # Get brief description from Click Command
        brief = self._get_short_help(name)
        lines.append(f"  /{name:<20s} {brief}")

    # ... (reconstruct grouped display matching current style)
```

## Acceptance Criteria

- [ ] `/help` generation reads from `REGISTRY` instead of walking `cli_main.commands`
- [ ] `click_only=True` commands are excluded from REPL `/help`
- [ ] Group structure is preserved (── General ──, ── Engagement ──, ── Wave ──, etc.)
- [ ] Brief descriptions are fetched from Click Command objects via `cli_main`
- [ ] `_get_short_help(name)` is defined and pulls from `cli_main` commands/groups
- [ ] REPL built-ins (`/help`, `/exit`, `/version`, `/exec`, `/shell`, phase commands) appear under "── Special ──" and are hardcoded
- [ ] No command listed in `/help` can fail with "Unknown command" in the REPL
- [ ] The old Click-tree-based help generation code is deleted
- [ ] REPL `/help` output looks the same as current output (minus broken commands)

## Files Affected

- `src/harness/shell/repl.py`

## Verification

```bash
# Manual REPL test
echo "/help" | python -m harness shell
# → should show grouped commands, no broken entries

# Check no Click-only commands appear
harness shell --command "/help" 2>&1 | grep -i "engagement list" && echo "FAIL: click-only shown" || echo "OK: click-only hidden"

# Confirm no commands shown that would fail
harness shell --command "/engagement list" 2>&1 | grep -i "CLI only"
# → should show "CLI only" message (from Task 5)
```
