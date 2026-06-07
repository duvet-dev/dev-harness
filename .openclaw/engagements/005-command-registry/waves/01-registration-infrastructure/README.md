# Wave 01 — Registration Infrastructure + Sync Tests

**Milestone:** 1 — Foundation
**Effort:** 1.5h
**Status:** 📋 Pending
**Depends on:** None
**Blocks:** Wave 02

## Summary

Create the `_registration.py` module with the `@register` decorator, `REGISTRY` dict, `Registration` dataclass, and builder functions (`build_repl_command_map()`, `register_bus_handlers()`). Also create the sync test suite (`test_registration.py`) with 4 tests that will initially serve as a checklist of remaining work.

This wave is purely additive — nothing is deleted. All existing tests continue to pass.

**Crichton note #4 addressed:** builder functions emit a warning (or raise) when REGISTRY is empty, documenting the import ordering constraint.

## Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Create `_registration.py` — decorator + REGISTRY + builder functions | 📋 Pending | ~60 lines |
| 2 | Add empty-REGISTRY warning to builder functions | 📋 Pending | Crichton note #4, ~5 lines |
| 3 | Create `test_registration.py` — 4 sync tests | 📋 Pending | ~80 lines |

## Verification

- `_registration.py` exists at `src/harness/command/_registration.py`
- `@register` decorator can be imported and called
- `build_repl_command_map()` returns empty dict when REGISTRY is empty
- `register_bus_handlers(bus)` is no-op when REGISTRY is empty
- Builder functions raise/warn when REGISTRY is empty (Crichton note #4)
- Sync tests exist and clearly indicate which commands still need @register
- Existing test suite still passes: `python -m pytest tests/ -q`
