# Dev Harness

[![Tests](https://img.shields.io/badge/tests-1826%20%E2%9C%85-brightgreen)](#)
[![Coverage](https://img.shields.io/badge/coverage-74%25-yellowgreen)](#)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](#)
[![License](https://img.shields.io/badge/license-proprietary-lightgrey)](#)

**Agent orchestration for software development** — coordinates AI agents
to plan, implement, test, and review code through structured, gated workflows.

- **Multi-agent pipeline** — requirements → research → design → implement →
  test → review, with agents for each phase
- **Engagement model** — every task is a tracked engagement with state,
  checkpoints, feedback loops, and a full audit trail
- **Observer mode** — analyse any codebase without setup or state
- **Fleet orchestration** — agents grouped into domain teams with
  cross-fleet consultation, governance levels, and blocking/advisory mode
- **Temporal-backed durability** — workflow persistence for long-running
  agent sessions (auto-starts the dev server if available)
- **LLM-agnostic** — pluggable backends: DeepSeek, OpenAI, Anthropic, CLI, or
  custom
- **Self-testing** — agents write and run their own tests as part of the
  development cycle

---

## Quick Start

```bash
# 1. Install (creates .venv, installs deps, downloads Temporal CLI)
make install

# 2. Verify
.venv/bin/harness --help

# 3. Initialise a project
cd my-project
.venv/bin/harness init

# 4. Set your LLM API key
export DEEPSEEK_API_KEY="sk-..."

# 5. Create an engagement and run a session
.venv/bin/harness engagement create "Add user authentication"
.venv/bin/harness session
```

> Add `.venv/bin` to your `PATH` for convenience:
> `export PATH=".venv/bin:$PATH"`

### Without a project — observer mode

Analyse any repo instantly, no setup needed:

```bash
.venv/bin/harness observe /path/to/repo    # fast scan (15+ checks)
.venv/bin/harness assess /path/to/repo     # full deep analysis
```

---

## Installation

### From source (recommended)

```bash
git clone https://github.com/your-org/dev-harness.git
cd dev-harness

# Install (creates .venv, installs dev deps, downloads Temporal)
make install

# Add to PATH for convenience
export PATH=".venv/bin:$PATH"
```

`make install`:
- Creates a Python virtual environment in `.venv/`
- Upgrades pip inside it
- Installs dev-harness in editable mode with dev dependencies (pytest, ruff, etc.)
- Downloads the Temporal CLI dev server binary (if not already in PATH)

To download the Temporal binary explicitly:

```bash
make download-temporal
```

### Single executable (alpha)

```bash
make build-exe
# Output: dist/harness (Linux/macOS) or dist/harness.exe (Windows)
```

Bundles Temporal's dev server for a zero-install experience.

### Dependencies

| Dependency | Purpose |
|---|---|
| Python ≥3.9 | Runtime |
| Temporal CLI | Workflow engine (auto-downloaded) |
| LLM API key | At least one of: DeepSeek, OpenAI, Anthropic |
| Git | SCM integration |

---

## Testing

### Quick test run

```bash
make test           # 1826 tests, 0 failures, 0 warnings — ~10s
```

### Full CI pipeline (what CI runs)

```bash
make ci
# 1. Lint check (ruff)
# 2. Full test suite with coverage report + HTML output
# 3. Coverage threshold enforcement (≥70%)
```

### Other test targets

```bash
make test-coverage     # Tests + coverage report + HTML in coverage/
make coverage-html     # Same as above, then opens report path
make test-e2e          # On-demand end-to-end tests (LLM APIs, live services)
make test-verbose      # Tests with verbose output + slowest durations
make test-ci           # Alias for make ci
```

### Running specific tests

```bash
# Directly with pytest
pytest tests/                               # whole suite
pytest tests/analysis/                      # analysis module
pytest tests/test_cycle.py                  # single file
pytest tests/test_validator.py -k "interface"  # by keyword
pytest tests/ -W error::RuntimeWarning      # CI mode
pytest -m e2e                               # e2e-marked tests only
```

All 1826 functional tests run in under 10 seconds with **zero external
dependencies**. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full
developer guide.

---

## CLI Reference

### Workflows

```
harness init          Create a new harness project
harness work          Full auto-pilot engagement
harness session       Phase-by-phase interactive session
harness chat          Interactive LLM chat within an engagement
harness agent run     Run a single agent by name
```

### Engagement lifecycle

```
harness engagement create <name>   Start a new engagement
harness engagement list            List all engagements
harness engagement set-active      Set active engagement
harness engagement status          Show engagement details
harness engagement close           Close an engagement
harness engagement rename          Rename an engagement
harness review                     Review at a gate checkpoint
harness phase                      Manage phase state
harness finish                     Complete with final commit
```

### Analysis

```
harness summary        Project status with phase breakdown
harness observe        Analyse any codebase (no setup)
harness assess         Deep analysis with LLM assessment
```

### Fleet management

```
harness fleet list              List registered fleets
harness fleet show <name>       Fleet details
harness fleet add-agent         Add agent to fleet
harness fleet remove-agent      Remove agent from fleet
harness fleet consult           Show consultation capabilities
harness fleet set-governance    Set governance level
```

### Wave cycle

```
harness wave list      List plan waves
harness wave run       Run a wave through implement→test→verify→commit
harness wave status    Show detailed wave state
```

### State & sync

```
harness catchup        Reconcile state with git
harness absorb         Absorb external changes
```

### Utilities

```
harness shell          Interactive REPL
harness generate-docs  Auto-generate documentation
harness changelog      Manage changelogs
harness agent list     List registered agents
harness agent show     Agent details
```

Use `harness workflows` for workflow guidance, or `harness <command> --help`
for per-command options.

---

## Makefile targets

| Target | Description |
|---|---|
| `make install` | Create .venv, install deps, download Temporal |
| `make test` | Run full test suite (1826 tests, ~10s) |
| `make ci` | Full CI: lint → tests → coverage (≥70%) |
| `make test-coverage` | Tests + coverage report + HTML in coverage/ |
| `make coverage-html` | Generate coverage HTML report |
| `make lint` | Run ruff linter |
| `make version` | Show current version (e.g. 0.1.0.003) |
| `make version-full` | Show version, build number, and build date |
| `make version-bump` | Increment build number (run automatically by build) |
| `make test-e2e` | End-to-end tests (on-demand, live services) |
| `make build` | Bump build number + build Python wheel |
| `make build-exe` | Single executable binary (alpha) |
| `make download-temporal` | Download Temporal CLI binary |
| `make clean` | Remove build artifacts, reset build counter |
| `make publish` | Build and publish to registry |

---

## Architecture

```
src/harness/
├── agents/            Agent runner, backends, fleet, consultation
│   ├── backends/      LLM providers (API, CLI, editor)
│   ├── builtin/       Built-in agent implementations
│   ├── runner.py      Agent execution engine
│   ├── fleet.py       Fleet definitions and governance
│   ├── fleet_registry.py
│   ├── consultation.py
│   ├── cycle.py       Built-in cycle definitions
│   └── ...
├── analysis/          Code scanning, assessment, observer
│   ├── fast.py        Lightweight structural analysis
│   ├── deep.py        Architecture conformance, coverage, dead code
│   ├── summary.py     Report formatting
│   ├── assessment.py  LLM-based independent assessment (P1-P5)
│   └── observer.py    Stand-alone analysis entry point
├── config/            Provider configuration
├── constitution/      Development constitution, templates
├── context/           Context loading and caching
├── docs/              Documentation generation
├── engagement/        Engagement lifecycle, feedback, checkpoints
├── plan/              Wave planning
├── refactor/          Refactoring loop, debt detection
├── scm/               Git operations
├── session/           Interactive sessions
├── shell/             REPL
├── state/             Workflow state, Temporal server/worker
├── sync/              OpenClaw vault sync
├── templates/         Agent templates
├── tools/             Web search
├── workflows/         Temporal workflow definitions
├── cli.py             Click-based CLI
└── entry.py           PyInstaller entry point
```

### Layers

| Layer | Responsibility |
|---|---|
| **Agent** | Runner, backends, fleet orchestration, tool access |
| **Analysis** | Fast scan, deep analysis, LLM assessment |
| **Workflow** | Temporal-based engagement lifecycle orchestration |
| **Infrastructure** | SCM, state management, sync, config |

---

## Configuration

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `DEEPSEEK_API_KEY` | At least one | Primary LLM provider |
| `OPENAI_API_KEY` | Fallback | OpenAI fallback |
| `ANTHROPIC_API_KEY` | Fallback | Anthropic fallback |
| `TEMPORAL_ADDRESS` | No | Temporal server address (default: 127.0.0.1:7233) |

### Project configuration

After `harness init`, edit `.harness/providers.yaml` for provider-specific
settings and `constitution.yaml` for project constitution, gates, and rules.

---

## Project Standards

- **Test Isolation** — tests must work in any order with no shared mutable state
- **Zero Regression** — no test failures after any change (TDD red allowed
  only before implementation)
- **No External Dependencies In CI** — all functional tests mock/patch external
  services (LLM APIs, Temporal server, etc.)
- **Coverage Threshold** — CI enforces ≥70% line coverage; HTML report in
  `coverage/index.html`
- **Commit Conventions** — semantic prefixes: `feat:`, `fix:`, `refactor:`,
  `docs:`, `test:`, `chore:` — see CONTRIBUTING.md

---

## License

Proprietary — internal use only.
