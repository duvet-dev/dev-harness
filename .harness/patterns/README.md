# Patterns Directory

Place reusable agent patterns here. Patterns define structured
approaches to common development tasks.

Pattern format: YAML files with steps, tools, and expected outputs.

See also: `src/harness/agents/pattern.py`

## Session Type Example Walkthroughs

Concrete, end-to-end command sequences for each development session type.
These show the full lifecycle — from init to finish — on realistic projects.

| Session Type | When To Use | Doc |
|-------------|-------------|-----|
| **Greenfield** 🆕 | Build from scratch — new projects, services, prototypes | [`docs/examples/greenfield-session.md`](../../docs/examples/greenfield-session.md) |
| **Brownfield** 🏗️ | Work within existing code — add features, extend APIs | [`docs/examples/brownfield-session.md`](../../docs/examples/brownfield-session.md) |
| **Refactoring** 🔨 | Restructure existing code toward ideal architecture | [`docs/examples/refactoring-session.md`](../../docs/examples/refactoring-session.md) |
| **Get-Well** 🩺 | Fix a broken codebase — failing tests, compilation errors, regressions | [`docs/examples/get-well-session.md`](../../docs/examples/get-well-session.md) |

### Quick Decision Guide

```
Is the codebase broken?
  ├─ Yes → Get-Well session (fix first, improve later)
  └─ No →
       ├─ Is there existing code?
       │   ├─ No  → Greenfield session (build from scratch)
       │   └─ Yes →
       │        ├─ Adding features? → Brownfield session
       │        └─ Restructuring?    → Refactoring session
       └─ (also read the `workflow` flag detection prompt)
```

## Existing Patterns

| Pattern | File |
|---------|------|
| Self-Improving Workflow | [`self-improving-workflow.md`](self-improving-workflow.md) |
| Refactoring Workflow | [`refactoring-workflow.md`](refactoring-workflow.md) |

