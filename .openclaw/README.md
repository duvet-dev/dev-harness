# `.openclaw/` — Project Non-Source Artifacts

This folder holds project artifacts generated and maintained by OpenClaw agents. It is **not project source code** — it's the agent's working context, parallel to what `.harness/` provides for the harness itself.

## Structure

```
.openclaw/
  README.md                       # This file
  engagements/
    <engagement-slug>/            # Per-engagement artifact folders
      assessments/
        assessment.md             # Combined codebase assessments
      requirements/
        requirements.md           # Combined requirements (all Rs)
      design/
        design.md                 # Evolving design document (single source of truth)
      waves/
        waves.md                  # Combined wave plan (completed + planned)
```

## Purpose-Bound, Not Agent-Bound

Each sub-folder is named for the **purpose** of its contents, not the agent that produced them. Agents come and go; the document structure remains consistent:

| Folder | What goes here |
|--------|---------------|
| `assessments/` | Analysis results, observer runs, review outputs, gap analyses |
| `requirements/` | Captured requirements — from voice notes through detailed specs |
| `design/` | Architecture and design — iterated through reviews |
| `waves/` | Build plan — completed, in-progress, and planned waves |

## Pattern

When working on another project with OpenClaw agents, follow the same pattern:

```
project-root/
  .openclaw/
    engagements/
      <engagement-slug>/
        assessments/
        requirements/
        design/
        waves/
```

This keeps agent artifacts clearly separate from project source code while maintaining a consistent organizational scheme across projects. The slug identifies the engagement; sub-folders identify the purpose.
