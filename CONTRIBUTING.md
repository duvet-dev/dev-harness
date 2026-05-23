# Contributing to Dev Harness

## Development Setup

### Prerequisites

- **Python ≥3.9** — [pyenv](https://github.com/pyenv/pyenv) recommended
- **Git** — for SCM integration
- **Temporal CLI** (optional) — auto-downloaded on first use if absent
- **LLM API key** (optional) — DeepSeek, OpenAI, or Anthropic for
  development work (not needed to run tests)

### Clone and install

```bash
git clone https://github.com/your-org/dev-harness.git
cd dev-harness

# Quick install (creates .venv, installs deps, downloads Temporal)
make install

# Add to PATH for convenience
export PATH=".venv/bin:$PATH"

# Verify
.venv/bin/harness --help
# or after PATH: harness --help
```

`make install` creates a Python virtual environment in `.venv/`,
upgrades pip inside it, then installs the package and all dev
dependencies (pytest, ruff, build, temporalio, etc.).

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
├── tests/                # Functional and feature tests (1826+)
│   ├── analysis/         # Code analysis tests
│   ├── docs/             # Documentation generation tests
│   ├── engagement/       # Engagement lifecycle tests
│   ├── refactor/         # Refactoring tests
│   ├── session/          # Session tests
│   └── ...
├── tests_e2e/            # End-to-end/integration tests (on-demand)
├── scripts/_temporal/    # Auto-downloaded Temporal CLI binary
├── Makefile              # Build, test, lint, package targets
├── pyproject.toml        # Project metadata, dependencies, tool config
├── README.md
└── CONTRIBUTING.md
```

---

## Makefile targets (quick reference)

| Target | What it does |
|---|---|
| `make install` | Create .venv, install deps, download Temporal |
| `make test` | Run full suite: `pytest tests/ -W error::RuntimeWarning` |
| `make ci` | Full CI pipeline: lint → test → coverage (≥70%) |
| `make test-coverage` | Tests + coverage report + HTML |
| `make test-e2e` | On-demand end-to-end tests |
| `make test-verbose` | Tests with verbose output + top 10 slowest |
| `make lint` | Run ruff linter (src/harness/ + tests/) |
| `make version` | Show current version (e.g. 0.1.0.003) |
| `make version-full` | Show version, build number, and build date |
| `make version-bump` | Increment build number |
| `make check-types` | Run mypy (if installed) |
| `make build` | Bump build + build Python wheel in `dist/` |
| `make build-exe` | Single-file executable (requires PyInstaller) |
| `make download-temporal` | Download Temporal CLI for current platform |
| `make clean` | Remove build artifacts, coverage/ |
| `make publish` | Build + publish to internal registry |

Run `make help` for a full list.

---

## Running tests

### Using Make

```bash
make test              # Full suite — 1826 tests, ~10s
make test-coverage     # Tests + coverage with HTML report
make test-verbose      # Verbose with slowest durations
make test-e2e          # On-demand e2e tests (live services)
make ci                # CI pipeline (lint → test → coverage)
```

### Directly with pytest

```bash
# Run everything
pytest tests/

# CI mode (warnings as errors)
pytest tests/ -W error::RuntimeWarning

# With coverage
pytest --cov=src/harness tests/

# With coverage + HTML report
pytest --cov=src/harness --cov-report=html:coverage tests/

# Run a specific area
pytest tests/analysis/
pytest tests/test_cycle.py
pytest tests/analysis/test_analysis_observer.py::TestAnalyse
pytest tests/test_validator.py -k "interface"

# End-to-end tests (require live services)
pytest -m e2e
pytest tests_e2e/
```

### Performance

The full core suite (1826 tests) runs in under 10 seconds with
**zero external dependencies**. All LLM calls, Temporal server
operations, and external services are mocked or patched.

---

## Linting

```bash
make lint       # Run ruff check on src/harness/ and tests/
ruff check .    # Lint the whole repository (alt)
```

Configuration is in `pyproject.toml` under `[tool.ruff]`. Per-file
ignores are set for test files (cosmetic rules suppressed) and
source files (pre-existing issues gradually resolved).

### Coverage

Coverage HTML reports are generated to `coverage/index.html`.
The threshold is **70%** — CI fails below this.

```bash
make test-coverage               # Run + generate HTML
open coverage/index.html         # Browse in browser
```

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
    result = my_function()  # Depends on /some/external/path existing
```

### Mock patterns

For async functions (like `assess()` in `harness.analysis.assessment`):

```python
# Patch at the import source — the lazy import in the function body
# picks up the patched version at call time.
with patch("harness.analysis.assessment.assess",
           return_value=_mock_report()):
    result = my_function(deep=True)
```

For `patch()` on async functions, Python 3.9 auto-creates an `AsyncMock`.
If you need a plain `MagicMock`, pass `new_callable=MagicMock`.

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
- **Linting:** Enforced by ruff — run `make lint` before committing

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
4. **Run the full suite:** `make ci` — must pass cleanly
5. **Commit** with a descriptive message
6. **Push** to your fork
7. **Open a pull request**

### Before submitting a PR

- [ ] `make ci` passes (lint → tests → coverage ≥70%)
- [ ] No new warnings introduced (`pytest tests/ -W error::RuntimeWarning`)
- [ ] Code is type-annotated
- [ ] New features have tests
- [ ] Documentation updated (README, CLI help, or docstrings)
- [ ] Changes are backward-compatible or documented as breaking
- [ ] Remote is set up and changes pushed (never work on a local-only repo)

---

## Versioning

Builds use semantic versioning with a monotonically incrementing
build number: **`X.Y.Z.BBB`** (e.g. `0.1.0.003`).

- `__version__` comes from `pyproject.toml` (`X.Y.Z`)
- `__build__` is read from `BUILD_NUMBER` (local file, gitignored)
- `__build_date__` is an ISO-8601 timestamp of the build

```bash
make version          # 0.1.0.003
make version-full     # Full details (version, build, date)
make version-bump     # Increment build number manually
```

`make build` and `make build-exe` automatically run `version-bump`
before packaging, so every wheel/executable has a unique build
number and timestamp embedded.

The version is accessible at runtime:
```bash
.venv/bin/harness --version        # 0.1.0.003
.venv/bin/harness --version-full   # Full build info
```

In development (no build run), the version shows `0.1.0.000` with
an empty date.

---

## Build system

### Building the package

```bash
make clean       # Remove old artifacts, reset build counter
make build       # Bump build + build wheel → dist/dev_harness-*.whl
```

### Building a single executable (alpha)

```bash
make build-exe   # Requires PyInstaller
```

Output: `dist/harness` (macOS/Linux) or `dist/harness.exe` (Windows).
The binary bundles the Temporal CLI dev server — no separate install needed.

### Publishing

```bash
make publish     # Build + upload to internal PyPI registry
```

Configure your registry URL in the `Makefile`'s `publish` target.

---

## Questions?

Open an issue or ask in the project channel. For architecture decisions,
see the `build/decisions/` directory.

---

*Last updated: 2026-05-23*
