# Engagement Conventions

**File:** `.openclaw/engagements/<slug>/CONVENTIONS.md`
**Purpose:** Standard formats for all engagement artifacts. Used by both OpenClaw agents and harness agents.

## Directory Structure

```
.openclaw/
  README.md                          # Top-level pattern guide
  templates/                         # Reusable document templates
  engagements/
    NNN-<slug>/                      # Index-prefixed for ordering
      CONVENTIONS.md                 # This file
      assessments/
        assessment.md                # Combined assessment
      requirements/
        requirements.md              # Combined requirements
      design/
        design.md                    # Evolving design document
      waves/
        waves.md                     # Wave overview plan
        (task template in `.openclaw/templates/wave-task.md`)
        <nnn>-<wave-name>/
          README.md                  # Wave summary + task table
          tasks/
            <nn>-<task-name>.md     # Individual task file
          artifacts/                 # Build outputs, reports
      findings/
        findings.yaml                # Findings Registry (Wave 31+)
```

## Index-Prefixing

Both vault and `.openclaw/` engagement folders use index prefixes for ordering:
- `001-consolidated-phase-refactor`
- `002-<next-engagement>`
- etc.

This makes `ls` show engagements in logical order regardless of when they were created.

## Document Conventions

### Task Files
Each task file follows `.openclaw/templates/wave-task.md` with: Status, Description, Acceptance Criteria, Files Affected, Verification.

### Status Values
- **Waves:** ✅ Complete | 🔧 In Progress | 📋 Pending | ❌ Blocked
- **Tasks:** ✅ Complete | 🔧 In Progress | 📋 Pending | ❌ Blocked

### Wave Folder Naming
`<number>-<kebab-case-name>` — e.g. `21-fleet-team-migration`

### Task File Naming
`<number>-<kebab-case-name>.md` — e.g. `01-helpers-rename.md`

## Creating a New Engagement

1. Copy slug folder structure from an existing engagement
2. Populate assessments, requirements, design from source material
3. Create wave plan with wave folders + task files
4. Build coordinator executes waves, updating task statuses

## Multi-Agent Coordination

- **Agent (me):** Creates/updates assessment, requirements, design, wave plan docs
- **Crichton:** Reviews designs, finds gaps, produces worksheets
- **Build Coordinator:** Executes waves, updates task statuses, generates artifacts
- **All agents:** Follow this convention document
