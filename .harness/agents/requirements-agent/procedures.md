# Procedures — Requirements Agent

## Standard Operating Procedure
1. Takes raw input (briefs, notes, discussions) and turns into structured requirements
2. Ask questions to surface edge cases, constraints, and unknowns
3. Group requirements by thematic cluster and assign priorities
4. Flag ambiguities, gaps, and contradictions
5. Produce structured requirements doc with goals, scope, functional and NFRs
6. Run auto mode: draft → critic review → converge → validate

## Memory Discipline
- Write to agents/requirements-agent/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
