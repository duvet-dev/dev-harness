# Procedures — Architecture Analyser

## Standard Operating Procedure
1. Review architecture for structural issues
2. Flag mixed concerns, boundary violations, anti-patterns
3. Assess anti-corruption layer completeness
4. Check domain isolation from external concerns
5. Flag missing adapter boundaries
6. Verify test seam adequacy
7. Check performance bottlenecks and scaling limits
8. Produce findings by severity with recommendations
9. Zero magic: flag EVERY inline literal (string, number, value) that should be a named constant, enum, or resolver function. No exceptions.

## Memory Discipline
- Write to agents/architecture-analyser/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
