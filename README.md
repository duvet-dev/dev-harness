# Dev Harness

Agent orchestration system for software development — coordinates
multiple AI agents to plan, implement, test, and review code changes
through structured engagement workflows.

## Overview

Dev Harness manages agent-driven software development via:

- **Engagements** — multi-phase development sessions with gates between phases
- **Agents** — pluggable AI backends with tool access (read/write files, web search)
- **Analysis** — code scanning, architecture conformance, dead code detection
- **Workflows** — Temporal-based orchestration for parallel agent execution
- **State** — workflow state persistence, freshness tracking, reconciliation
- **Sync** — bidirectional sync between OpenClaw vault and codebase

## Quick Start

```bash
# Install
pip install -e .

# Configure providers
cp .harness/providers.yaml.example .harness/providers.yaml
# Edit with your API keys (or set env vars DEEPSEEK_API_KEY, OPENAI_API_KEY)

# Run the CLI
harness --help
```

## Project Structure

```
.harness/            — Project configuration (agents, providers, fleets)
build/               — Architecture decisions, changelogs, design docs
docs/                — Auto-generated documentation
src/harness/
  agents/            — Agent runner, backends, fleet, consultation
  analysis/          — Code scanning, assessment, observer
  config/            — Provider config, architecture rules
  constitution/      — Development constitution models
  context/           — Bundle loading, caching
  docs/              — Changelog generator, doc generator
  engagement/        — Phase lifecycle, feedback, checkpoint
  plan/              — Wave planning and management
  refactor/          — Refactoring loop, debt detection
  scm/               — Git operations, .gitignore management
  session/           — Interactive session loop, client
  shell/             — REPL interface
  state/             — Workflow state, freshness, reconciliation
  sync/              — OpenClaw vault sync pipeline
  templates/         — Agent template definitions
  tools/             — Web search tool
  workflows/         — Temporal workflow definitions
    phases/          — Phase manager, run_single_agent

tests/               — pytest test suite (~1700+ tests)
```

## Configuration

See `.harness/config.yaml` for project defaults and
`.harness/providers.yaml` for LLM provider setup.

Provider API keys are read from environment variables:
- `DEEPSEEK_API_KEY` — DeepSeek (default provider)
- `OPENAI_API_KEY` — OpenAI (fallback)

## Testing

```bash
# Run full suite
pytest

# Run with coverage
pytest --cov=src/harness

# Run specific module
pytest tests/test_paths.py
pytest tests/analysis/
```

## Architecture

The system follows a layered architecture:

1. **Agent Layer** — runner, backends, fleet orchestration, tool access
2. **Analysis Layer** — fast scan, deep analysis, assessment pipeline
3. **Workflow Layer** — Temporal workflows for engagement lifecycle
4. **Infrastructure Layer** — SCM, state management, sync, config

See `build/architecture-v1.md` and `build/decisions/` for detailed design.

## Changelogs

Changelogs for each Wave of development are in `build/changelogs/`.

## License

Proprietary — internal use only.
