# Dev Harness — Agent Guidelines

> **Purpose:** This file tells all agents (OpenClaw agents, harness agents, and any AI tooling) how to interact with this repository. Read this before making changes.
>
> **Location:** Project root. All agents should look for `AGENTS.md` in the project root directory as their first source of guidance.

---

## 1. Project Identity

- **Project:** Dev Harness — a development workflow orchestration tool
- **Language:** Python 3.9+
- **Package:** `harness` (src layout at `src/harness/`)
- **Test framework:** pytest
- **Build:** `make` (see Makefile for targets)

## 2. Quick Start

```bash
make install      # Set up virtualenv + install dependencies
make test         # Run full test suite
make test-smoke   # Run only smoke tests (fast, ~1s)
make test-e2e     # Run end-to-end tests
make ci           # Full CI: lint + test + coverage (--cov-fail-under=70)
make lint         # ruff check only
make clean        # Clean build artifacts
```

## 3. Core Rules

### 3.1 Alpha Mode — No Backward Compatibility

**NO shims, adapters, import aliases, compat markers, or config migrations.** If a change breaks consumers, consumers update in the same commit. Old inline code is removed immediately — not preserved, not commented out, not aliased. Legacy files are deleted.

### 3.2 CLI Is an API Layer

The CLI (`src/harness/cli/main.py`) is a thin dispatch layer. Business logic lives in CommandBus handlers (`src/harness/command/handlers.py`). CLI functions must:
- Keep their Click decorators and signatures (the CLI is the public API)
- Replace their body with `return dispatch_cli_command(cmd)` style dispatch
- Never contain inline business logic

### 3.3 Test Regression Principle

Zero failures after implementation. Tests may fail before implementation (TDD red) but never after. Commit fixes same commit as code change. Suite regression = priority fix before any other work.

### 3.4 Hard Rule: `make ci` Before Every Commit

**`make ci` is the non-negotiable gate.** Before every commit:
1. Run `make ci` — this runs ruff lint, pytest, and coverage (`--cov-fail-under=70`)
2. If it fails, fix it before committing
3. A `make test` pass is **NOT sufficient** — lint failures (F541, unused imports, formatting) break CI even if all tests pass

Common lint failures are auto-fixable: `python3 -m ruff check --fix src/harness/`

### 3.5 Test Order Independence

Tests must work in any order. Multi-tenant isolation for shared-database integration tests.

### 3.6 Coverage

- All new `src/` code must target 100% test coverage
- The `make ci` target enforces `--cov-fail-under=70`
- Run `make ci` before committing to verify the full suite (lint + test + coverage)

## 4. Project Structure

```
src/harness/
  cli/              # Click CLI definitions (thin — no business logic)
    main.py         # CLI entry point
    commands.py     # Command factory functions + dispatch helpers
  command/          # CommandBus architecture
    bus.py          # Command dispatcher
    handlers.py     # Delegation-thin handlers
    types.py        # Command, CommandResult, CommandHandler
    registry.py     # Handler registration
  session/          # Session orchestration
  agents/           # Agent orchestrator
  loop/             # Main loop runner
  phase/            # Phase orchestration
  ...
tests/
  command/          # Unit tests for command handlers
  smoke/            # Integration smoke tests (fast, marked @smoke)
  ...
```

## 5. Testing Conventions

- **Command handler tests** (`tests/command/`): Verify importability, registration, and CommandHandler interface compliance. Do NOT call `handler.handle()` directly — handlers delegate to real business components that may do I/O or LLM calls.
- **Smoke tests** (`tests/smoke/`): Fast (~1s), marked with `@smoke` decorator. Validate structure, importability, and wiring — not execution.
- **Unit tests**: Use mocks for external dependencies. Do not trigger actual LLM calls, git operations, or filesystem modifications in unit tests.

## 6. The `.harness/` Directory

> **DO NOT MODIFY `.harness/` AS PART OF BUILDING THIS PROJECT.**

`.harness/` is reserved for generic harness runtime configuration — the config and metadata that any project would have when using Dev Harness as a tool. The ONLY thing that creates or modifies files in `.harness/` is the harness application itself (via `harness init`, engagement operations, `harness refresh-agents`, etc.).

**Rules:**
- Do not edit `.harness/` files manually
- Do not add project-specific management config to `.harness/`
- The `.gitignore` already excludes transient runtime data (agent memory, cache, test artifacts)
- Config files (constitution.yaml, teams.yaml, phases.yaml) are tracked but should only change via harness operations

## 7. Current Architecture

### CommandBus Pattern (V7 §5.20)

All commands flow through:
1. Click CLI → parses args → builds `Command` via factory function
2. CommandBus → dispatches to `CommandHandler.handle()`
3. Handler → delegates to one business component → wraps result in `CommandResult`

### Handler Count

**Current: 30 handlers** (13 base + 17 Sprint 3 additions):
- Core lifecycle: create, resume, abort, finish, review, rename, fix, set-branch
- Phase management: enter-phase, next, manage-phase, init-project
- Session/chat: session, chat, run-wave
- Analysis: summary, inspect, assess
- Wave management: list-waves, wave-status, create-wave, create-waves-from-assessment, create-wave-from-finding
- Documentation: generate-docs, annotate-changelog
- Teams: refresh-agents, set-governance
- Status: query-status, query-whats-next, execute-step

## 8. Git Conventions

- Branch naming: `eng/<slug>` pattern
- Commit messages: descriptive, reference the wave/feature
- Detached HEAD is acceptable for build-coordinator runs
- No backward-compat commits — breaking changes are inlined

## 9. Related Documentation

- V6 Refactoring Plan: `Research/Dev Harness/build/comprehensive-refactoring-completion-plan.md` (in vault)
- V7 Architecture docs: inline in source code
- Community Standards: shared across all agents inheriting from main workspace
