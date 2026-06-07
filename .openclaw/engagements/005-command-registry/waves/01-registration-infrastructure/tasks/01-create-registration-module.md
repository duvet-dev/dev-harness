# Task 1 — Create `_registration.py`

**Status:** 📋 Pending
**Wave:** 01-registration-infrastructure
**Dependencies:** None
**Effort:** 0.75h

## Description

Create `src/harness/command/_registration.py` with the core infrastructure: `@register` decorator, `REGISTRY` module-level dict, `Registration` dataclass, and two builder functions.

## Acceptance Criteria

- [x] File exists at `src/harness/command/_registration.py`
- [x] `@register` decorator with signature:
  ```python
  def register(
      name: str,
      *,
      cmd_cls: Optional[type[TypedCommand]] = None,
      handler: Optional[TypedHandler] = None,
      arg_parser: Optional[Callable[[list[str]], dict[str, Any]]] = None,
      click_only: bool = False,
  ) -> Callable
  ```
- [x] `click_only=False` (default) requires `cmd_cls` and `handler` — raises `ValueError` if missing
- [x] Duplicate `name` raises `ValueError` at import time
- [x] Decorator returns the function unchanged — Click decorators still own the function
- [x] `Registration` dataclass with fields: `name`, `cmd_cls`, `handler`, `arg_parser`, `click_only`
- [x] `REGISTRY: dict[str, Registration]` — module-level mutable dict
- [x] `build_repl_command_map() -> dict[str, tuple[type, Callable]]` — same structure as current `COMMAND_TYPES`; excludes `click_only=True` entries
- [x] `register_bus_handlers(bus: CommandBus) -> None` — registers all handlers from REGISTRY; skips duplicates (checks `cmd_cls not in bus._type_handlers`)
- [x] Imports only abstract types (`TypedCommand`, `TypedHandler` from `harness.command.types`) + `typing` — no concrete command/handler imports

## Files Affected

- `src/harness/command/_registration.py` (new)

## Verification

```bash
# Import test
python -c "
from harness.command._registration import register, REGISTRY, Registration, build_repl_command_map, register_bus_handlers
print('Module loaded OK')
print(f'Empty REGISTRY: {REGISTRY}')
print(f'Empty REPL map: {build_repl_command_map()}')
print('All good')
"

# Decorator test
python -c "
from harness.command._registration import register, REGISTRY
@register(name='test.cmd', click_only=True)
def my_fn(): pass
print(f'REGISTRY has test.cmd: {\"test.cmd\" in REGISTRY}')
print(f'click_only: {REGISTRY[\"test.cmd\"].click_only}')
REGISTRY.clear()
"

# ValueError tests
python -c "
from harness.command._registration import register, REGISTRY

# Missing handler
try:
    @register(name='bad')
    def fn(): pass
except ValueError as e:
    print(f'Missing handler caught: {e}')

# Duplicate name
@register(name='dup', click_only=True)
def a(): pass
try:
    @register(name='dup', click_only=True)
    def b(): pass
except ValueError as e:
    print(f'Duplicate caught: {e}')
REGISTRY.clear()
"
```
