# Community Standards — Shared Governance

All agents in this project inherit these rules.

## Principles
- Prefer deterministic logic over LLM judgement where possible
- Surface discrepancies by exception — don't report what's fine
- Output structured documents (per phase contract), not free-form text

## Privacy
- Never exfiltrate project data
- All agent outputs remain in the project repository

## Quality
- **Test Regression Principle:** Tests may fail before implementation (TDD red
  phase — by design) but MUST NOT fail after implementation is complete.
  Zero test failures is the only acceptable state for "done". If a change
  deliberately alters behaviour, update the affected tests in the same
  commit. A suite regression has priority over any other work in progress.
- Tests at business/feature level are highest priority
- Dead code is suspect — flag for review
- Review by exception: only surface problems and decisions that depart from defaults
- Code should be beautiful on the inside — clean architecture and clear
  separation of concerns are structural priorities, not cosmetics
- Never guess, never hope: research, model, verify
- Critically analyse everything — every design, every decision, every line
- **Tests must be order-independent** — they must work in any order (random,
  reversed, alphabetical, or parallel), with no shared mutable state and
  deterministic teardown even on failure
- **Multi-tenant database isolation** — when tests share a real database,
  each test runs as a different tenant so isolation is enforced by the
  application's multi-tenancy layer, not by test orchestration

## Encapsulation — Zero Magic Anything
- **No magic strings, numbers, or values, ever.** Every literal value
  must be a named constant, enum, or resolver function. This is not
  aspirational — it is a hard rule with zero exceptions.
- **Define once, use everywhere.** Constants are grouped by domain or
  component (e.g. a ``constants.py`` or a dataclass of related values),
  not scattered in-line. Even single-use literals must be named.
- **No raw path/directory strings.** Every directory, file path,
  configuration key, and resource identifier must be resolved through a
  named function in a dedicated path module (e.g. ``paths.py``).
  Strings like ``".harness"``, ``"config.yaml"``, ``"engagements/"`` are
  never written inline.
- **No raw enums/identifiers.** Prefer ``Enum``, ``StrEnum``, or constant
  dicts over bare strings like ``"architecture"`` or ``"planning"`` when
  used as config keys, tags, or identifiers.
- **No bare numbers.** Every numeric literal (timeout, threshold, limit,
  port) must be a named constant with a comment explaining its purpose.
- **Review pattern: flag every literal** — code reviews, architecture
  analyses, and all automated quality checks MUST flag any hardcoded
  literal that should be a named constant. A single inline
  ``".harness"`` or ``60`` or ``"requirements"`` is grounds for
  an immediate review finding and must be resolved before merge.
