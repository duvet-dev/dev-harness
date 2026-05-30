# Procedures — Sync Agent

## Standard Operating Procedure
1. Discover OpenClaw source files (SOUL.md, AGENTS.md, etc.)
2. Extract identity, procedures, and standards from source
3. Map OpenClaw concepts to harness template format
4. Generate template files in target directory
5. Report changes from previous release

## Memory Discipline
- Write to agents/sync/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
