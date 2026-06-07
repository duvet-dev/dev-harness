# Procedures — Dependency Analyser

## Standard Operating Procedure
1. Examine project dependencies and their transitive closure
2. Detect version conflicts and incompatible combinations
3. Flag circular dependencies between modules
4. Identify outdated or deprecated dependency versions

## Memory Discipline
- Write to agents/dependency-analyser/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
