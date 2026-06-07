# Dev Harness — Assessment (Template Mirroring)

> **Purpose:** Single view of all codebase assessments, analysis runs, and review findings.
> **Engagement:** 006-template-mirroring
> **Updated:** 2026-06-07

---

## 1. Codebase Overview

The project has two parallel document systems with no overlap:

| System | Templates | Writes engagement docs | Used by |
|--------|-----------|----------------------|---------|
| `.openclaw/` | `.openclaw/templates/` (5 templates) | `.openclaw/engagements/` | OpenClaw agents |
| `.harness/` | `(none)` | `.harness/engagements/` (runtime artifacts only) | Harness agents |

The `.harness/` directory has `.harness/templates/` (runtime agent identity files) and `.harness/engagements/` (test engagement artifacts like `engagement.json`), but no document templates and no structured assessment/requirements/design output.

The harness's `/assess`, `/requirements`, `/design` commands produce stdout reports and interactive sessions — they don't write persistent engagement documents.

## 2. Key Findings

- **No `.harness/templates/` directory** exists for document templates
- **Harness commands don't write to `.harness/engagements/<slug>/`** — no persistent engagement documents from the harness itself
- **Template format mismatch risk** — if OpenClaw and harness write different formats, the two systems drift apart
- **AGENTS.md §6** states `.harness/` should only be modified by the harness itself — consistent with the boundary rule
- **CONVENTIONS.md** now documents the OpenClaw/harness boundary (§Boundary)

## 3. Prioritised Recommendations

1. Mirror `.openclaw/templates/` into `.harness/templates/` — assessment, requirements, design templates
2. Update `/assess`, `/requirements`, `/design` commands to write to `.harness/engagements/<slug>/` using template format
3. Add sync test ensuring template files stay consistent between `.openclaw/templates/` and `.harness/templates/`
