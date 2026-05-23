# Dev Harness

[![Tests](https://img.shields.io/badge/tests-1687%20%E2%9C%85-brightgreen)](#)
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
# 1. Install
pip install -e .

# 2. Initialise a project
cd my-project
harness init

# 3. Configure (or set env vars)
#     DEEPSEEK_API_KEY  — primary LLM provider
#     OPENAI_API_KEY    — fallback
#     ANTHROPIC_API_KEY — fallback

# 4. Create an engagement
harness engagement create "Add user authentication"

# 5. Run an interactive session
harness session
```

### Without a project — observer mode

Analyse any repo instantly, no setup needed:

```bash
harness observe /path/to/repo          # fast scan
harness assess /path/to/repo           # full deep analysis (LLM-based)
```

---

## Installation

### From source (recommended)

```bash
git clone https://github.com/your-org/dev-harness.git
cd dev-harness
pip install -e .
```

### Single executable (alpha)

```bash
make build
# Output: dist/harness (Linux/macOS) or dist/harness.exe (Windows)
```

The single executable bundles Temporal's dev server binary so you have
everything you need in one file.

### Dependencies

| Dependency | Purpose |
|---|---|
| Python ≥3.9 | Runtime |
| Temporal CLI | Workflow engine (auto-downloaded on first use if absent) |
| LLM API key | At least one of: DeepSeek, OpenAI, Anthropic |
| Git | SCM integration |

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

## Testing

```bash
# Core functional/feature tests (no external dependencies)
pytest tests/

# With coverage
pytest --cov=src/harness tests/

# Run specific area
pytest tests/analysis/
pytest tests/test_cycle.py

# End-to-end tests (LLM APIs, live services — run on demand)
pytest -m e2e

# Run everything including e2e
pytest -m ''
```

All 1687+ functional tests run in <10s with zero external dependencies.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the full developer guide.

---

## Project Standards

- **Test Isolation** — tests must work in any order with no shared mutable state
- **Zero Regression** — no test failures after any change (TDD red allowed
  only before implementation)
- **No External Dependencies In CI** — all functional tests mock/patch external
  services (LLM APIs, Temporal server, etc.)
- **Commit Conventions** — semantic prefixes: `feat:`, `fix:`, `refactor:`,
  `docs:`, `test:`, `chore:` — see CONTRIBUTING.md

---

## License

Proprietary — internal use only.
