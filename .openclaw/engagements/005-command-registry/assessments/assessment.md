# Dev Harness — Assessment (REPL Command Wiring)

> **Purpose:** Single view of all codebase assessments, analysis runs, and review findings.
> **Engagement:** 005-command-registry
> **Updated:** 2026-06-07

---

## 1. Codebase Overview

The harness REPL (`src/harness/shell/repl.py`) provides a slash-command interface (`/engagement list`, `/session`, `/work`, etc.) backed by a `COMMAND_TYPES` dict that must be manually kept in sync with the Click CLI tree (`src/harness/cli/main.py`) and the handler registry (`src/harness/command/setup.py`).

**Scale:**
- 39 Click CLI commands across 7 groups (engagement, agent, team, wave, changelog, and top-level)
- `COMMAND_TYPES` dict (~200 lines) with 30 entries
- 5 exclusive REPL commands (`/help`, `/exit`, `/shell`, etc.) handled before COMMAND_TYPES
- 16 per-command arg parsers

## 2. Observer Analysis Runs

### Run 1: Crichton Command Wiring Gap Analysis (2026-06-07)

Crichton performed a full gap analysis comparing the Click CLI, `COMMAND_TYPES` dict, handler registry, and test coverage.

**Key Findings:**
- 12 CLI commands show up in `/help` but fail in the REPL with "Unknown command"
- 3 handlers are registered on the bus but wired to no UI (dead code)
- 10 "pure Click" commands implement logic directly in Click function bodies outside the CommandBus
- Only 15 of 30 REPL-accessible commands have test coverage

**Full analysis:** `artifacts/crichton-command-wiring-analysis.md`

### Run 2: Crichton Registry Design Review (2026-06-07)

Crichton reviewed the original 1,732-line `CommandDef` registry design.

**Key Findings — 5 Major Issues:**
1. Multi-phase migration would temporarily add a 4th registration, not eliminate any
2. Registry key naming conflicted with REPL dispatch prefix-matching
3. `/help` generation was unaddressed (would still show broken commands)
4. Auto-arg-parser had 6 failure modes
5. Click-param to TypedCommand-field mapping was assumed 1:1 with no transformation

**Full review:** `artifacts/crichton-registry-design-review.md`

### Run 3: Crichton Decorator Design Final Review (2026-06-07)

Crichton reviewed the leaner decorator-based design.

**Verdict: APPROVED.** All 5 prior issues resolved. 8 of 10 edge cases eliminated by simpler scope. 4 minor implementation notes (sub-15 lines each).

**Full review:** `artifacts/crichton-decorator-final-review.md`

## 3. Review Findings (by dimension)

### 3.1 Architecture & Coupling
- **Three-registration anti-pattern**: Every REPL-dispatchable command must be registered in the Click CLI, `COMMAND_TYPES` dict, and handler registry independently. No single source of truth.
- **Help text lies to users**: `/help` is auto-generated from the Click tree, so it truthfully lists commands that fail at runtime in the REPL.
- **No guardrails**: No CI gate, test, or lint check detects registration drift.

### 3.2 Code Quality
- `COMMAND_TYPES` dict is a manually-maintained 200-line module-level constant.
- Arg parsers (`_single_arg`, `_engagement_create_args`, etc.) are 16 independent functions with no shared contract.
- Some Click-only commands contain complex I/O logic (file reads, table formatting) outside the CommandBus.

### 3.3 Testing
- Only one test exercises REPL → COMMAND_TYPES → CommandBus dispatch (and it mocks the bus).
- No test validates the command map against the CLI definition.
- No test verifies every registered command is dispatchable.

### 3.4 Security
- No security concerns identified — this is a routing fidelity issue, not a trust boundary.

### 3.5 Documentation
- `AGENTS.md` documents the `make ci` workflow but not the three-registration requirement.
- Engagement `CONVENTIONS.md` documents document formats but not the registration pattern.

## 4. Prioritised Recommendations

### Fix Immediately
1. Add `@register` decorator to all 39 click commands (task)
2. Create `_registration.py` with core infrastructure (task)
3. Replace `COMMAND_TYPES` with `build_repl_command_map()` (task)
4. Replace `setup.py` handler registration with `register_bus_handlers(bus)` (task)
5. Make `/help` registry-aware (task)
6. Add sync tests (task)

### Fix Next
7. Remove dead handler registrations (cleanup)
8. Document import ordering constraint (documentation)

### Address Later
9. Refactor Click-only commands into CommandBus pattern (scope: separate engagement)
