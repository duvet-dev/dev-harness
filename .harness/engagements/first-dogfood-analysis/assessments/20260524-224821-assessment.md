## Analysis Summary

- 295 files, 448309 lines across 38 dirs — javascript: 1 files (733 lines), json: 1 files (1 lines), markdown: 3 files (723 lines), other: 85 files (391270 lines), python: 202 files (55434 lines), toml: 1 files (136 lines), yaml: 2 files (12 lines)
- Branch 'main': 1 files changed, +6/-6 lines
- Architecture conformance: 2/2 expected directories found, 1 issues
- Coverage: 41/110 source modules have tests (37%), 45 uncovered
- Dead code check: 28 potentially unused modules of 110 total

### Arch Conformance

- **[WARNING] `src/dev_harness.egg-info`** — Missing __init__.py in src/dev_harness.egg-info

### Coverage

- **[WARNING]** — Coverage 37% (41/110 modules) — below 80% threshold
- **[WARNING] `harness/_version.py`** — No test file for harness/_version.py (expected test__version.py)
- **[WARNING] `harness/cli.py`** — No test file for harness/cli.py (expected test_cli.py)
- **[WARNING] `harness/entry.py`** — No test file for harness/entry.py (expected test_entry.py)
- **[WARNING] `harness/context/loader.py`** — No test file for harness/context/loader.py (expected test_loader.py)
- **[WARNING] `harness/analysis/observer.py`** — No test file for harness/analysis/observer.py (expected test_observer.py)
- **[WARNING] `harness/analysis/assessment.py`** — No test file for harness/analysis/assessment.py (expected test_assessment.py)
- **[WARNING] `harness/analysis/fast.py`** — No test file for harness/analysis/fast.py (expected test_fast.py)
- **[WARNING] `harness/analysis/agents.py`** — No test file for harness/analysis/agents.py (expected test_agents.py)
- **[WARNING] `harness/analysis/summary.py`** — No test file for harness/analysis/summary.py (expected test_summary.py)
- **[WARNING] `harness/analysis/deep.py`** — No test file for harness/analysis/deep.py (expected test_deep.py)
- **[WARNING] `harness/analysis/base.py`** — No test file for harness/analysis/base.py (expected test_base.py)
- **[WARNING] `harness/config/manager.py`** — No test file for harness/config/manager.py (expected test_manager.py)
- **[WARNING] `harness/plan/wave_model.py`** — No test file for harness/plan/wave_model.py (expected test_wave_model.py)
- **[WARNING] `harness/workflows/activities.py`** — No test file for harness/workflows/activities.py (expected test_activities.py)
- **[WARNING] `harness/workflows/signals.py`** — No test file for harness/workflows/signals.py (expected test_signals.py)
- **[WARNING] `harness/workflows/engagement.py`** — No test file for harness/workflows/engagement.py (expected test_engagement.py)
- **[WARNING] `harness/workflows/phases/run_single_agent.py`** — No test file for harness/workflows/phases/run_single_agent.py (expected test_run_single_agent.py)
- **[WARNING] `harness/workflows/phases/phase_manager.py`** — No test file for harness/workflows/phases/phase_manager.py (expected test_phase_manager.py)
- **[WARNING] `harness/agents/runner.py`** — No test file for harness/agents/runner.py (expected test_runner.py)
- **[WARNING] `harness/agents/detectors.py`** — No test file for harness/agents/detectors.py (expected test_detectors.py)
- **[WARNING] `harness/agents/backends/editor_backend.py`** — No test file for harness/agents/backends/editor_backend.py (expected test_editor_backend.py)
- **[WARNING] `harness/agents/backends/api_backend.py`** — No test file for harness/agents/backends/api_backend.py (expected test_api_backend.py)
- **[WARNING] `harness/agents/backends/formatters.py`** — No test file for harness/agents/backends/formatters.py (expected test_formatters.py)
- **[WARNING] `harness/agents/backends/cli_backend.py`** — No test file for harness/agents/backends/cli_backend.py (expected test_cli_backend.py)
- **[WARNING] `harness/agents/backends/base.py`** — No test file for harness/agents/backends/base.py (expected test_base.py)
- **[WARNING] `harness/agents/builtin/sync_agent.py`** — No test file for harness/agents/builtin/sync_agent.py (expected test_sync_agent.py)
- **[WARNING] `harness/state/freshness.py`** — No test file for harness/state/freshness.py (expected test_freshness.py)
- **[WARNING] `harness/state/store.py`** — No test file for harness/state/store.py (expected test_store.py)
- **[WARNING] `harness/state/reconciliation.py`** — No test file for harness/state/reconciliation.py (expected test_reconciliation.py)
- **[WARNING] `harness/state/temporal_adapter.py`** — No test file for harness/state/temporal_adapter.py (expected test_temporal_adapter.py)
- **[WARNING] `harness/state/temporal_worker.py`** — No test file for harness/state/temporal_worker.py (expected test_temporal_worker.py)
- **[WARNING] `harness/state/temporal_server.py`** — No test file for harness/state/temporal_server.py (expected test_temporal_server.py)
- **[WARNING] `harness/state/snapshot.py`** — No test file for harness/state/snapshot.py (expected test_snapshot.py)
- **[WARNING] `harness/constitution/models.py`** — No test file for harness/constitution/models.py (expected test_models.py)
- **[WARNING] `harness/constitution/loader.py`** — No test file for harness/constitution/loader.py (expected test_loader.py)
- **[WARNING] `harness/constitution/templates/template_registry.py`** — No test file for harness/constitution/templates/template_registry.py (expected test_template_registry.py)
- **[WARNING] `harness/templates/agent_templates.py`** — No test file for harness/templates/agent_templates.py (expected test_agent_templates.py)
- **[WARNING] `harness/scm/git.py`** — No test file for harness/scm/git.py (expected test_git.py)
- **[WARNING] `harness/scm/gitignore.py`** — No test file for harness/scm/gitignore.py (expected test_gitignore.py)
- **[WARNING] `harness/sync/openclaw_extractor.py`** — No test file for harness/sync/openclaw_extractor.py (expected test_openclaw_extractor.py)
- **[WARNING] `harness/sync/mapper.py`** — No test file for harness/sync/mapper.py (expected test_mapper.py)
- **[WARNING] `harness/sync/applier.py`** — No test file for harness/sync/applier.py (expected test_applier.py)
- **[WARNING] `harness/sync/pipeline.py`** — No test file for harness/sync/pipeline.py (expected test_pipeline.py)
- **[WARNING] `harness/session/interactive.py`** — No test file for harness/session/interactive.py (expected test_interactive.py)
- **[WARNING] `harness/session/commands.py`** — No test file for harness/session/commands.py (expected test_commands.py)

### Dead Code

- **[INFO] `harness/agents/backends/api_backend.py`** — Module 'harness.agents.backends.api_backend' is never imported by other modules
- **[INFO] `harness/agents/backends/cli_backend.py`** — Module 'harness.agents.backends.cli_backend' is never imported by other modules
- **[INFO] `harness/agents/backends/editor_backend.py`** — Module 'harness.agents.backends.editor_backend' is never imported by other modules
- **[INFO] `harness/agents/conformance_reviewer.py`** — Module 'harness.agents.conformance_reviewer' is never imported by other modules
- **[INFO] `harness/agents/context_builder.py`** — Module 'harness.agents.context_builder' is never imported by other modules
- **[INFO] `harness/agents/domain_tester.py`** — Module 'harness.agents.domain_tester' is never imported by other modules
- **[INFO] `harness/agents/governance.py`** — Module 'harness.agents.governance' is never imported by other modules
- **[INFO] `harness/agents/pattern.py`** — Module 'harness.agents.pattern' is never imported by other modules
- **[INFO] `harness/agents/validator.py`** — Module 'harness.agents.validator' is never imported by other modules
- **[INFO] `harness/docs/changelog.py`** — Module 'harness.docs.changelog' is never imported by other modules
- **[INFO] `harness/docs/generator.py`** — Module 'harness.docs.generator' is never imported by other modules
- **[INFO] `harness/engagement/rename.py`** — Module 'harness.engagement.rename' is never imported by other modules
- **[INFO] `harness/entry.py`** — Module 'harness.entry' is never imported by other modules
- **[INFO] `harness/refactor/loop.py`** — Module 'harness.refactor.loop' is never imported by other modules
- **[INFO] `harness/refactor/suggestions.py`** — Module 'harness.refactor.suggestions' is never imported by other modules
- **[INFO] `harness/refactor/verification.py`** — Module 'harness.refactor.verification' is never imported by other modules
- **[INFO] `harness/session/interactive.py`** — Module 'harness.session.interactive' is never imported by other modules
- **[INFO] `harness/shell/repl.py`** — Module 'harness.shell.repl' is never imported by other modules
- **[INFO] `harness/state/reconciliation.py`** — Module 'harness.state.reconciliation' is never imported by other modules
- **[INFO] `harness/state/store.py`** — Module 'harness.state.store' is never imported by other modules
- **[INFO] `harness/state/temporal_adapter.py`** — Module 'harness.state.temporal_adapter' is never imported by other modules
- **[INFO] `harness/tools/web_search.py`** — Module 'harness.tools.web_search' is never imported by other modules
- **[INFO] `harness/wave/wave_cycle.py`** — Module 'harness.wave.wave_cycle' is never imported by other modules
- **[INFO] `harness/workflows/activities.py`** — Module 'harness.workflows.activities' is never imported by other modules
- **[INFO] `harness/workflows/engagement.py`** — Module 'harness.workflows.engagement' is never imported by other modules
- **[INFO] `harness/workflows/phases/phase_manager.py`** — Module 'harness.workflows.phases.phase_manager' is never imported by other modules
- **[INFO] `harness/workflows/phases/run_single_agent.py`** — Module 'harness.workflows.phases.run_single_agent' is never imported by other modules
- **[INFO] `harness/workflows/signals.py`** — Module 'harness.workflows.signals' is never imported by other modules

### Structure

✅ No issues found.

### Git Diff

✅ No issues found.


---

# Dev‑Harness Codebase Analysis — Unified Report

## Executive Summary

Dev‑Harness is an ambitious agent‑orchestration CLI tool that coordinates AI‑backed development workflows across multiple phases, engagement tracking, and fleet‑based agent teams. The codebase demonstrates mature domain modelling, strong documentation (excellent README and CONTRIBUTING, thorough docstrings), and a well‑intentioned layered/hexagonal architecture. However, the implementation has not kept pace with the design intent. A **critical run‑time bug** (provider key mismatch) silently breaks Anthropic and Google tool calling, rendering those backends non‑functional. Structural fissures are widespread: a monolithic 2800‑line CLI, a 1200‑line session loop, duplicated provider‑config parsing in three places, and bare `except: pass` blocks that swallow errors without logging. Test coverage of the core orchestration logic is almost non‑existent — the CLI and the main agent‑runner critic loop are untested, and the project has zero end‑to‑end or business‑feature tests. Security‑wise, the Temporal binary download lacks checksum verification and the binary‑resolution logic scans the current working directory, creating an arbitrary‑code‑execution vector. While the project correctly self‑identifies many of its own limitations (via deprecated constants, TODO markers, and “simplification” stubs), fixing the critical serialisation asymmetry and addressing the most entangled, untested modules should be the immediate priority before adding further features.

---

## Cross‑Cutting Findings: Connecting the Dots

Multiple analysis dimensions expose the same root weaknesses when viewed together:

| Theme | Related Findings | Impact |
|-------|------------------|--------|
| **Provider configuration fragmentation** | `session/loop.py` and `session/client.py` bypass the canonical `config/provider_registry.py` and parse `providers.yaml` directly. `ApiBackend` expects a `provider` key but `ProviderConfig.to_resolved_dict()` only emits `type`. This duplication and mismatch causes a **runtime bug** (critical‑reviewer #1) and violates architecture boundaries (architecture‑critic boundary violation #5, #6). | Anthropic/Google backends broken silently; provider switching unreliable. |
| **Monolithic core modules** | `cli.py` (2800 lines) and `session/loop.py` (1200 lines) hold massive, deeply nested command handlers. These modules are the biggest coverage gaps (CLI 17%, loop 38%) and are the hardest to test. Their size forces lazy imports, repeated lazy‑import patterns, and duplicate logic (e.g., `switch_provider` vs `list_providers`). Code‑critic reports six related structure/complexity errors. | Every change to user interaction carries high risk; new contributors are overwhelmed. |
| **Untested orchestration heart** | `AgentRunner.critic_loop()` (the core multi‑agent workflow), `CycleRunner.run()`, the session main loop, and all Click commands have virtually no test coverage. This leaves the primary value proposition — autonomous multi‑agent coordination — completely unverified by automated checks. The 74% coverage stat is inflated by trivial struct‑validation tests. (test‑auditor) | Defects in the agent pipeline go undetected until a user reports them. |
| **Infrastructure leakage into domain/application** | `agents/cycle.py` invokes subprocess directly for test execution; `analysis/assessment.py` calls `click.echo`; `agents/runner.py` uses `shutil.rmtree`. These violate the port/adapter seams and make the domain logic hard to test and to swap for different environments. (architecture‑critic boundary violations, code‑critic complexity) | Domain purity is compromised; refactoring the backends becomes riskier. |
| **Error swallowing epidemic** | Barn‑exception `except Exception: pass` appears in `cli.py` (git commit reconciliation), `session/loop.py` (context loading), `engagement/lifecycle.py` (YAML parsing), and `agents/governance.py` (YAML loading). These mask real failures and make debugging production issues extremely difficult. (code‑critic error handling) | Silent data corruption or missing context degrades user experience. |
| **Security gaps in Temporal workflow setup** | `temporal_server.py` downloads a binary without checksum verification and searches `Path.cwd()` for the binary, enabling a trojan‑binary attack. These are directly exploitable in the default `harness session` workflow when Temporal is auto‑started. (security‑auditor) | Remote code execution if a user runs `harness` from a directory containing a malicious `temporal` binary. |

The architecture‑critic’s recommendation to extract backends into an `adapters/` package, introduce a `TestRunner` port, and centralise provider access directly addresses several of these cross‑cutting issues. The critical‑reviewer’s “fix immediately” list provides the least‑effort, highest‑impact steps.

---

## Prioritised Findings by Severity & Impact

### Critical (must fix now)

1. **Provider key serialisation asymmetry (runtime bug)**  
   *Finding:* `ProviderConfig.to_resolved_dict()` emits `'type': 'anthropic'` but `ApiBackend` reads `invocation.resolved_config.get('provider', '')`. The key never matches; Anthropic and Google tool formatting falls through to OpenAI‑compatible, producing invalid API calls.  
   *Effort:* 1 hour  
   *Fix:* Add `'provider': self.type` alongside the existing `'type'` in `to_resolved_dict()`. Immediately add a contract test to prevent regression.

2. **Temporal binary download without integrity check**  
   *Finding:* `download_temporal()` fetches from GitHub with no SHA256 or GPG verification. A compromised release or MITM could inject malware.  
   *Effort:* 1 hour  
   *Fix:* Pin known‑good checksums and verify post‑download.

3. **CWD‑relative binary resolution in `_resolve_binary()`**  
   *Finding:* The function searches `Path.cwd()` for the temporal binary; a malicious `scripts/_temporal/temporal` in the working directory would be executed as a subprocess.  
   *Effort:* 30 minutes  
   *Fix:* Remove `Path.cwd()` from the candidate list; only use `__file__`‑relative and bundled paths.

### High (fix in next sprint)

4. **Monolithic CLI and session loop**  
   *Findings:* `cli.py` 2800 lines, `session/loop.py` 1200 lines, deeply nested handlers, 17‑38% test coverage.  
   *Effort:* 3–5 days  
   *Fix:* Split CLI commands into per‑domain modules (`cli/engagement.py`, `cli/fleet.py`, …). Decompose `session_loop` into setup, phase‑driver, and teardown methods. Use Click groups already present.

5. **Duplicate provider loading everywhere**  
   *Findings:* `session/loop.py`, `session/client.py` independently parse `providers.yaml` instead of using `config/provider_registry.py`.  
   *Effort:* 3 hours  
   *Fix:* Refactor all provider access to go through `ProviderConfigSet.load_providers()`. Remove direct YAML reads.

6. **Zero end‑to‑end or business‑feature tests**  
   *Findings:* No tests exercise the full agent pipeline, CLI commands, or Temporal integration. Coverage inflated by struct tests.  
   *Effort:* 2 weeks initially, then incremental  
   *Fix:* Add at least smoke tests for `harness --help`, `harness init`, and a mock‑backend integration test of the critic loop using existing `MockBackend`.

7. **Error swallowing (`except Exception: pass`) plague**  
   *Findings:* 7+ locations silently drop exceptions during git ops, context loading, YAML parsing.  
   *Effort:* 4 hours  
   *Fix:* Replace all bare exceptions with specific exception types and `log.warning()` at minimum.

### Medium (address in next few weeks)

8. **Duplicated `analyse()` / `analyse_async()` and `run()` / `run_stream()` methods**  
   *Findings:* 95% identical code in `observer.py` and `api_backend.py`.  
   *Effort:* 4 hours  
   *Fix:* Extract shared logic into private helpers.

9. **Phantom agent roles not validated**  
   *Finding:* Strings like `'coder'`, `'tester'` used throughout but not backed by `AgentRole` enum. Typo would silently fail.  
   *Effort:* 3 hours  
   *Fix:* Introduce a canonical role‑name resolver and enforce validation.

10. **YAML write‑safety (comments destroyed)**  
    *Findings:* `yaml.dump()` in fleet registry, engagement lifecycle, freshness overwrite user‑edited files and drop all comments.  
    *Effort:* 3 hours  
    *Fix:* Use `ruamel.yaml` for user‑editable files; add an “auto‑generated” header otherwise.

11. **Concurrency races in `PhaseStateManager` and `CheckpointManager`**  
    *Findings:* Load‑modify‑save without file locking; TOCTOU in checkpoint ID generation.  
    *Effort:* 4 hours  
    *Fix:* Add advisory file locking (e.g., `portalocker`) and atomic directory creation with retry.

---

## Top‑5 Prioritised Recommendations

1. **Fix the critical provider‑key bug and add contract tests.**  
   This one‑line change in `provider_models.py` restores Anthropic/Google functionality. Pair it with a contract test that verifies the round‑trip from `ProviderConfig` → `Invocation` → `ApiBackend` tool formatting. This is the highest‑impact, lowest‑effort fix in the report.

2. **Split `cli.py` and `session/loop.py` into focused, testable modules.**  
   Decompose the monolithic 2800‑line CLI into `cli/engagement_commands.py`, `cli/fleet_commands.py`, etc., following the existing Click group pattern. Break `session_loop()` into smaller orchestration steps. This dramatically reduces regression risk and enables isolated testing of user‑facing flows.

3. **Centralise all provider‑config access through `config/provider_registry.py`.**  
   Remove the three independent YAML parsers in session modules and make `ProviderConfigSet` the single source of truth. This eliminates provider‑resolution inconsistencies and reduces duplication.

4. **Establish a testing safety net for the core agent orchestration.**  
   Start with CLI smoke tests (using `CliRunner`) and an integration test of `AgentRunner.critic_loop()` with a fake backend. Add a `pytest.mark.e2e` marker that can be run optionally. Raise the coverage threshold only *after* the untested orchestration paths are covered, so the metric reflects real confidence.

5. **Harden the Temporal binary acquisition.**  
   Pin SHA256 checksums for the downloaded binary and remove `Path.cwd()` from the binary resolution path. These are simple, high‑security‑impact changes that close a remote‑code‑execution vector.

Addressing these five items will transform the codebase from a clever prototype with hidden fragility into a robust, maintainable tool that can safely evolve.