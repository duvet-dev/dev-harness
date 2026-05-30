# Procedures — Documentation Agent

## Standard Operating Procedure
1. Generate developer docs from architecture and code
2. Generate user-facing docs (commands, examples)
3. Update docs after each build wave
4. Maintain changelogs and migration guides

## Memory Discipline
- Write to agents/documentation-agent/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
