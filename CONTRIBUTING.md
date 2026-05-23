# Contributing to Dev Harness

## Development Setup

### Prerequisites

- **Python ≥3.9** — [pyenv](https://github.com/pyenv/pyenv) recommended
- **Git** — for SCM integration
- **Temporal CLI** (optional) — for workflow durability; auto-downloaded
  on first use if absent
- **LLM API key** (optional) — at least one of DeepSeek, OpenAI, or Anthropic
  for development work (not needed to run tests)

### Clone and install

```bash
git clone https://github.com/your-org/dev-harness.git
cd dev-harness

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev extras
pip install -e ".[dev]"

# Verify
harness --help
```

### Configure LLM providers (optional, for real agent work)

```bash
export DEEPSEEK_API_KEY="sk-..."
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-..."
```

Or create `.harness/providers.yaml`:

```yaml
api_key: "${DEEPSEEK_API_KEY}"
api_backend: "deepseek"
```

---

## Repository structure

```
dev-harness/
├── src/harness/          # Source code
│   ├── agents/           # Agent runner, backends, fleet, consultation
│   ├── analysis/         # Code scanning, LLM assessment
│   ├── cli.py            # Click-based CLI
│   ├── config/           # Provider configuration
│   ├── constitution/     # Development constitution
│   ├── context/          # Context loading
│   ├── docs/             # Documentation generation
│   ├── engagement/       # Engagement lifecycle
│   ├── plan/             # Wave planning
│   ├── refactor/         # Refactoring, debt detection
│   ├── scm/              # Git operations
│   ├── session/          # Interactive sessions
│   ├── shell/            # REPL
│   ├── state/            # Temporal server, state management
│   ├── sync/             # OpenClaw vault sync
│   ├── templates/        # Agent templates
│   ├── tools/            # Web search
│   └── workflows/        # Temporal workflows
├── tests/                # Functional and feature tests (~1700+)
├── tests_e2e/            # End-to-end/integration tests (on-demand only)
├── scripts/              # Build and utility scripts
├── Makefile              # Build, test, lint targets
├── pyproject.toml        # Project metadata and dependencies
└── setup.py              # Legacy setup script
```

---

## Running tests

### Core test suite (no external dependencies)

```bash
# Run everything
pytest tests/

# Run with warnings as errors (CI does this)
pytest tests/ -W error::RuntimeWarning

# Run with coverage
pytest --cov=src/harness tests/

# Run a specific test file
pytest tests/test_cycle.py

# Run a specific test class
pytest tests/analysis/test_analysis_observer.py::TestAnalyse

# Run a specific test
pytest tests/test_paths.py::TestPaths::test_project_root
```

### End-to-end tests (require live services)

These tests make real API calls to LLM providers or need a running
Temporal server. They are **excluded by default** and must be run
explicitly:

```bash
pytest -m e2e              # only e2e tests
pytest -m ''               # all tests including e2e
pytest tests_e2e/          # the e2e test directory
```

### Performance

The core test suite (~1700 tests) runs in under 10 seconds on a modern
machine. There are no slow integration tests in the core suite.

---

## Test conventions

### Golden rules

1. **No external dependencies.** All tests must mock or patch LLM APIs,
   the Temporal server, file system operations, and any other external
   service. The one exception is `tmp_path` from pytest's built-in
   fixtures.

2. **Test order independence.** Any test can run in any order with any
   other test. Using `tmp_path` for file operations ensures isolation.

3. **Zero regression.** After a change is committed, the full test suite
   must pass with zero failures. Tests may fail before implementation
   (TDD red phase) but never after.

### Writing new tests

```python
# ✅ Good — full isolation, no external deps
def test_my_feature(self, tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("key: value\n")
    result = my_function(config)
    assert result == expected_value

# ✅ Good — mocking external services
def test_with_llm_mock(self):
    with patch("harness.agents.runner.AgentRunner.run_simple") as mock_run:
        mock_run.return_value = '{"result": "ok"}'
        result = my_function()
        assert result == expected_value

# ❌ Bad — real LLM calls
def test_bad_example(self):
    result = my_function()  # This calls a real API!

# ❌ Bad — depends on external state
def test_also_bad(self):
    os.chdir("/some/external/path")
    result = my_function()  # This depends on /some/external/path existing
```

### Mock patterns

For async functions (like `assess()` in `harness.analysis.assessment`):

```python
# Patch at the import source — the lazy import in the function body
# will pick up the patched version at call time.
with patch("harness.analysis.assessment.assess",
           return_value=_mock_report()):
    result = my_function(deep=True)
```

For `patch()` on async functions, Python 3.9 auto-creates an `AsyncMock`.
If you don't want that behaviour, use `new_callable=MagicMock`.

### Markers

| Marker | Purpose |
|---|---|
| `@pytest.mark.asyncio` | For async test functions |
| `@pytest.mark.e2e` | Tests requiring external dependencies (excluded from CI) |

---

## Coding standards

### Style

- **Python:** Follow [PEP 8](https://peps.python.org/pep-0008/) with
  4-space indentation
- **Imports:** Standard library → third-party → local, one blank line
  between groups
- **Type hints:** Use `from __future__ import annotations` and annotate
  all function signatures
- **Docstrings:** Google-style with `Args:`, `Returns:`, `Raises:`
- **Line length:** 90 characters soft limit

### Commit messages

Use semantic prefixes:

```
feat: add web search tool to agent toolkit

- Integrate httpx-based web search via duckduckgo
- Add WebSearchResult model and error handling
- Wire into agent tool permissions

fix: patch assess() in observer deep tests

Resolves 10-minute hang when API keys are configured.
```

Prefixes: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`,
`build:`, `ci:`, `perf:`, `style:`.

Never leave a local repo without a remote. Push changes early and often.

### Branch naming

```
feat/web-search-tool
fix/observer-test-hang
docs/contributing-guide
refactor/agent-runner
```

---

## Making changes

### Workflow

1. **Pick or create a GitHub issue** describing the problem
2. **Create a branch:** `git checkout -b type/short-description`
3. **Write the code** with tests
4. **Run the full suite:** `pytest tests/` — must pass
5. **Commit** with a descriptive message
6. **Push** to your fork
7. **Open a pull request**

### Before submitting a PR

- [ ] Full test suite passes (`pytest tests/ -W error::RuntimeWarning`)
- [ ] No new warnings introduced
- [ ] Code is type-annotated
- [ ] New features have tests
- [ ] Documentation updated (README, CLI help, or docstrings as appropriate)
- [ ] Changes are backward-compatible or clearly documented as breaking

---

## Build system

### Building the package

```bash
# Build a wheel
make build

# The resulting wheel is at dist/dev_harness-*.whl
```

### Building a single executable (alpha)

```bash
make build-exe

# Output: dist/harness (macOS/Linux) or dist/harness.exe (Windows)
```

The single executable bundles the Temporal CLI dev server binary,
so no separate Temporal installation is needed. See `Makefile` for
details.

### Publishing

```bash
make publish    # Build and upload to internal registry
```

---

## Questions?

Open an issue or ask in the project channel. For architecture decisions,
see the `build/decisions/` directory.

---

*Last updated: 2026-05-23*
