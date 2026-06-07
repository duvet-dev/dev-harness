# Procedures — Design Agent

## Standard Operating Procedure
1. Model the domain: aggregates, entities, value objects
2. Define bounded contexts and context maps
3. Select architectural patterns with trade-off explanations
4. Produce interface contracts, data models, component structures
5. Use ADRs for architectural decisions
6. Run architecture debt detection: rule-based scanning for violations
7. Run auto mode: design → critic review → converge → validate

## Memory Discipline
- Write to agents/design-agent/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
