# Procedures — Boundary Test Agent

## Standard Operating Procedure
1. Identify boundaries: examine structure for public APIs, module boundaries, entry points
2. Present boundaries to user for confirmation and correction
3. Generate behaviour-capturing tests at each confirmed boundary
4. Mark tests IMMUTABLE — they capture current behaviour, not desired
5. Register boundary test metadata in .harness/boundaries.yaml

## Memory Discipline
- Write to agents/boundary-test-agent/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
