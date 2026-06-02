# Procedures — Component Analyser

## Standard Operating Procedure
1. Identify all public interfaces, classes, modules, and entry points
2. Measure method count, parameter count, dependency count per component
3. Check cohesion: do methods operate on shared state?
4. Check coupling: how many external modules does each reference?
5. Flag god objects, shotgun surgery, mixed concerns
6. Flag anemic models and missing abstractions
7. Compare against language-specific norms for right-sizing
8. Produce coupling metrics, cohesion scores, and recommendations
9. Zero magic: flag EVERY inline literal (string, number, value) that should be a named constant, enum, or resolver function. No exceptions.

## Memory Discipline
- Write to agents/component-analyser/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
