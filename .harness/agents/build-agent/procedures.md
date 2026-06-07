# Procedures — Build Agent

## Standard Operating Procedure
1. Implement features following the established architecture
2. Write tests alongside implementation (TDD if possible)
3. Handle failure cases, edge cases, and errors
4. Ensure all existing tests still pass
5. Run boundary test generation at application interfaces
6. Produce clean, well-structured code with named constants not magic literals
7. Run auto mode: build → test → critic review → converge → validate

## Memory Discipline
- Write to agents/build-agent/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
