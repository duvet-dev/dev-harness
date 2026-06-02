# Procedures — Example Scenarios Agent

## Standard Operating Procedure
1. Design example scenarios that exercise features
2. Implement as versioned snapshots
3. Verify examples are runnable end-to-end
4. Maintain example documentation

## Memory Discipline
- Write to agents/example-scenarios-agent/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
