# `.openclaw/` — Project Non-Source Artifacts

This folder holds project artifacts generated and maintained by OpenClaw agents. It is **not project source code** — it's the agent's working context, parallel to what `.harness/` provides for the harness itself.

## Structure

```
.openclaw/
  README.md                       # This file
  CONVENTIONS.md                  # Engagement conventions — applies to all engagements
  templates/                      # Reusable document templates
  engagements/
    <engagement-slug>/            # Per-engagement artifact folders
      assessments/
        assessment.md             # Combined codebase assessments
      requirements/
        requirements.md           # Combined requirements (all Rs)
      design/
        design.md                 # ALWAYS the current approved design
        reviews/                   # Review outputs, dated for traceability
        _archive/                  # Superseded design versions
      waves/
        waves.md                  # Combined wave plan (completed + planned)
```

## Purpose-Bound, Not Agent-Bound

Each sub-folder is named for the **purpose** of its contents, not the agent that produced them. Agents come and go; the document structure remains consistent:

| Folder | What goes here |
|--------|---------------|
| `CONVENTIONS.md` | Engagement conventions — applied to all engagements |
| `templates/` | Reusable document templates (assessment, requirements, design, wave) |
| `assessments/` | Analysis results, observer runs, review outputs, gap analyses |
| `requirements/` | Captured requirements — from voice notes through detailed specs |
| `design/` | Architecture and design — iterated through reviews |
| `design/reviews/` | Review outputs from Crichton etc., dated for traceability |
| `design/_archive/` | Superseded design versions (v1, v2, ...) |
| `waves/` | Build plan — completed, in-progress, and planned waves |

## Pattern

When working on another project with OpenClaw agents, follow the same pattern:

```
project-root/
  .openclaw/
    CONVENTIONS.md
    templates/
    engagements/
      <engagement-slug>/
        assessments/
        requirements/
        design/
          reviews/
          _archive/
        waves/
```

This keeps agent artifacts clearly separate from project source code while maintaining a consistent organizational scheme across projects. The slug identifies the engagement; sub-folders identify the purpose.
