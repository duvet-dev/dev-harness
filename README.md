# Dev Harness

[![Tests](https://img.shields.io/badge/tests-3262%20%E2%9C%85-brightgreen)](#)
[![Coverage](https://img.shields.io/badge/coverage-79%25-yellowgreen)](#)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](#)
[![License](https://img.shields.io/badge/license-proprietary-lightgrey)](#)

**Agent orchestration for software development** — coordinates AI agents
to plan, implement, test, and review code through structured, gated workflows.

- **Multi-agent pipeline** — requirements → research → design → implement →
  test → review, with agents for each phase
- **Engagement model** — every task is a tracked engagement with state,
  checkpoints, feedback loops, and a full audit trail
- **CommandBus architecture** — all operations dispatched through a unified
  command bus with delegation-thin handlers
- **Team orchestration** — agents grouped into domain teams with
  cross-team consultation, governance levels, and blocking/advisory mode
- **Temporal-backed durability** — workflow persistence for long-running
  agent sessions (auto-starts the dev server if available)
- **LLM-agnostic** — pluggable backends: DeepSeek, OpenAI, Anthropic, CLI, or
  custom
- **Self-testing** — agents write and run their own tests as part of the
  development cycle
- **Interactive REPL** — tab-complete shell with command history

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
.venv/bin/harness assess /path/to/repo     # full deep analysis
.venv/bin/harness status                   # quick project status
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
make test           # 3262 tests, 0 failures, 0 warnings — ~17s
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
make test-e2e          # On-demand end-to-end tests (LLM APIs, live services)
make test-verbose      # Tests with verbose output + slowest durations
make test-smoke        # Fast smoke tests (~1s)
```

---

## CLI Reference

### Workflows

```
harness init          Create a new harness project
harness work          Full auto-pilot engagement
harness session       Phase-by-phase interactive session
harness chat          Interactive LLM chat within an engagement
harness shell         Launch interactive REPL
harness health        Run configuration and state validation checks
```

### Engagement lifecycle

```
harness engagement create <name>   Start a new engagement
harness engagement list            List all engagements
harness engagement set-active      Set active engagement
harness engagement status          Show engagement details
harness engagement close           Close an engagement
harness engagement rename          Rename an engagement
harness engagement set-branch      Set the branch for an engagement
harness phase                      Manage phase state (list, navigate, resume)
harness review                     Review at a gate checkpoint
harness finish                     Complete with final commit
harness enter-phase                Enter a specific phase
harness whatsnext                  Show available next actions
```

### Analysis

```
harness summary        Project status with phase breakdown
harness assess         Deep analysis with LLM assessment
```

### Team management

```
harness fleet list              List registered teams
harness fleet show <name>       Team details with agents and guidelines
harness fleet consult           Show consultation capabilities
harness fleet set-governance    Set governance level
harness consult                 Ask a cross-team consultation question
```

### Wave cycle

```
harness wave list           List plan waves
harness wave run <id>       Run a wave through implement→test→verify→commit
harness wave status         Show detailed wave state
harness wave create-from-assessment   Create waves from assessment findings
harness wave create-from-finding      Create a wave from a specific finding
```

### Agent management

```
harness agent list     List registered agent roles
harness agent show     Show agent details
harness agent run      Run an agent by name
harness refresh-agents Refresh agent profiles from registry
```

### Utilities

```
harness generate-docs  Auto-generate documentation
harness changelog annotate  Append annotation to changelog
harness version        Show version (--version, --version-full)
```

Use `harness workflows` for workflow guidance, or `harness <command> --help`
for per-command options.

---

## Makefile targets

| Target | Description |
|---|---|
| `make install` | Create .venv, install deps, download Temporal |
| `make test` | Run full test suite (3262 tests, ~17s) |
| `make ci` | Full CI: lint → tests → coverage (≥70%) |
| `make test-coverage` | Tests + coverage report + HTML in coverage/ |
| `make test-smoke` | Fast smoke tests (~1s) |
| `make lint` | Run ruff linter |
| `make version` | Show current version (e.g. 0.1.0.003) |
| `make version-full` | Show version, build number, and build date |
| `make version-bump` | Increment build number |
| `make build` | Bump version + build Python wheel |
| `make build-exe` | Single executable binary (alpha) |
| `make clean` | Remove build artifacts, coverage/ |

---

## Architecture

```
src/harness/
├── agents/            Agent runner, backends, teams, consultation
│   ├── consultation.py    Cross-team consultation routing
│   ├── orchestrator.py    Agent orchestration engine
│   ├── agent_registry.py  Agent role catalog
│   ├── plugin_registry.py Backend plugin discovery
│   └── builtin/           Built-in agent implementations
├── cli/               Click CLI definitions (thin dispatching layer)
│   ├── main.py            CLI entry point
│   ├── commands.py        Command factory functions
│   └── helpers.py         CLI utility functions
├── command/           CommandBus architecture (V7 §5.20)
│   ├── bus.py             Command dispatcher
│   ├── handlers.py        30 delegation-thin handlers
│   ├── types.py           Command, CommandResult, CommandHandler
│   └── registry.py        Handler registration
├── session/           Interactive session loops
│   ├── session_orchestrator.py  Session entry points + InteractiveSession
│   ├── commands.py           Session command routing
│   └── helpers.py            Session UI helpers
├── shell/             Interactive REPL with CommandBus dispatch
├── team/              Team registry and model
│   ├── model.py           AgentTeam dataclass
│   ├── registry.py        TeamRegistry with layered merge semantics
│   └── defaults.py        Built-in team definitions
├── engagement/        Engagement lifecycle, checkpoints, feedback
├── plan/              Wave planning and management
├── analysis/          Code scanning, assessment, observer
├── skills/            Skills registry for agent prompt injection
├── config/            LLM provider configuration
├── constitution/      Development constitution and templates
├── phase/             Phase templates and orchestration
├── scm/               Git operations
├── state/             Workflow state, Temporal server/worker
├── workflows/         Temporal workflow definitions
└── skills/            Skills registry for agent prompt injection
```

### Key Patterns

| Pattern | Responsibility |
|---|---|
| **CommandBus** | Unified dispatch: Click → Command → Handler → Business component |
| **TeamRegistry** | Agent team management with built-in < project < user merge |
| **SkillsRegistry** | Static skill content injection into agent prompts |
| **PhaseOrchestrator** | Multi-phase session orchestration |
| **ConsultationOrchestrator** | Cross-team question routing |

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
- **Alpha Mode** — no backward compatibility: old code is removed, not preserved
- **Commit Conventions** — semantic prefixes: `feat:`, `fix:`, `refactor:`,
  `docs:`, `test:`, `chore:` — see CONTRIBUTING.md

---

## License

Proprietary — internal use only.
